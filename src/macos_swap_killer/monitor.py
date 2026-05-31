from __future__ import annotations

import logging
import time
from collections.abc import Callable

from .actuator import terminate_process
from .config import AppConfig
from .llm import LLMClient
from .models import ActionResult, IncidentResult, LLMDecision, LLMResponse, ProcessInfo, SwapInfo, TrendInfo
from .notifications import send_notification
from .policy import decision_for_pid, local_veto
from .privacy import summarize_processes
from .processes import collect_processes, select_candidates
from .rules import UserRules, load_rules
from .swap import get_swap_info
from .trends import TrendStore
from .logging_utils import write_event


SwapProvider = Callable[[], SwapInfo]
ProcessProvider = Callable[[], list[ProcessInfo]]
ConfirmCallback = Callable[[ProcessInfo, LLMDecision, str], bool]


class SwapKiller:
    def __init__(
        self,
        config: AppConfig,
        *,
        logger: logging.Logger,
        swap_provider: SwapProvider = get_swap_info,
        process_provider: ProcessProvider = collect_processes,
        llm_client: LLMClient | None = None,
        rules: UserRules | None = None,
        trend_store: TrendStore | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.swap_provider = swap_provider
        self.process_provider = process_provider
        self.llm_client = llm_client or LLMClient(config)
        self.rules = rules or load_rules(config.rules_path)
        self.trend_store = trend_store or TrendStore(
            config.history_path,
            window_sec=config.trend_window_sec,
            growth_threshold_gib=config.swap_growth_threshold_gib,
            max_samples=config.trend_history_limit,
        )
        self._last_incident_at = 0.0

    def run_once(
        self,
        *,
        dry_run: bool,
        threshold_gib: float | None = None,
        interactive: bool = False,
        confirm_callback: ConfirmCallback | None = None,
    ) -> IncidentResult:
        threshold = threshold_gib if threshold_gib is not None else self.config.swap_threshold_gib
        swap = self.swap_provider()
        trend = self._record_trend(swap)

        pressure_trigger = (
            self.config.enable_memory_free_trigger
            and swap.used_gib is None
            and swap.memory_free_percent is not None
            and swap.memory_free_percent <= self.config.memory_free_percent_threshold
        )
        if swap.used_gib is None and not pressure_trigger:
            message = f"swap usage unavailable from {swap.source}; skipping actions"
            self.logger.warning(message)
            result = IncidentResult(triggered=False, swap=swap, dry_run=dry_run, message=message, trend=trend)
            self._record(result)
            return result

        absolute_trigger = swap.used_gib is not None and swap.used_gib >= threshold
        trend_trigger = self.config.enable_trend_trigger and trend is not None and trend.triggered
        triggered = absolute_trigger or trend_trigger or pressure_trigger
        trigger_reason = self._trigger_reason(
            absolute_trigger=absolute_trigger,
            trend_trigger=trend_trigger,
            pressure_trigger=pressure_trigger,
        )

        if not triggered:
            message = self._below_threshold_message(swap, threshold, trend)
            self.logger.info(message)
            return IncidentResult(triggered=False, swap=swap, dry_run=dry_run, message=message, trend=trend)

        now = time.monotonic()
        if now - self._last_incident_at < self.config.cooldown_sec:
            message = "swap threshold crossed, but incident is in cooldown"
            self.logger.info(message)
            result = IncidentResult(
                triggered=True,
                swap=swap,
                dry_run=dry_run,
                message=message,
                trigger_reason=trigger_reason,
                trend=trend,
            )
            self._record(result)
            return result

        self._last_incident_at = now
        processes = self.process_provider()
        candidates = select_candidates(
            processes,
            min_rss_mb=self.config.min_candidate_rss_mb,
            max_candidates=self.config.max_candidates_for_llm,
        )

        if not candidates:
            message = "swap threshold crossed, but no memory-heavy candidates were found"
            self.logger.info(message)
            result = IncidentResult(
                triggered=True,
                swap=swap,
                dry_run=dry_run,
                message=message,
                trigger_reason=trigger_reason,
                trend=trend,
            )
            self._record(result)
            self._notify(result)
            return result

        if not self.config.api_key:
            message = "MSK_API_KEY is not configured; no LLM decision or action was taken"
            self.logger.warning(message)
            result = IncidentResult(
                triggered=True,
                swap=swap,
                dry_run=dry_run,
                message=message,
                trigger_reason=trigger_reason,
                trend=trend,
            )
            self._record(result, candidates=candidates)
            self._notify(result)
            return result

        try:
            llm_response = self.llm_client.classify(swap, summarize_processes(candidates))
        except Exception as exc:  # noqa: BLE001 - bad LLM/API state must fail closed.
            message = f"LLM classification failed closed: {exc}"
            self.logger.error(message)
            result = IncidentResult(
                triggered=True,
                swap=swap,
                dry_run=dry_run,
                message=message,
                trigger_reason=trigger_reason,
                trend=trend,
            )
            self._record(result, candidates=candidates)
            self._notify(result)
            return result

        result = self._apply_llm_response(
            swap=swap,
            trigger_reason=trigger_reason,
            trend=trend,
            candidates=candidates,
            llm_response=llm_response,
            dry_run=dry_run,
            interactive=interactive,
            confirm_callback=confirm_callback,
        )
        self._record(result, candidates=candidates, llm_response=llm_response)
        self._notify(result)
        return result

    def watch(
        self,
        *,
        dry_run: bool,
        threshold_gib: float | None = None,
        interactive: bool = False,
        confirm_callback: ConfirmCallback | None = None,
    ) -> None:
        self.logger.info(
            "watch started threshold=%s dry_run=%s interval=%ss",
            threshold_gib if threshold_gib is not None else self.config.swap_threshold_gib,
            dry_run,
            self.config.poll_interval_sec,
        )
        while True:
            self.run_once(
                dry_run=dry_run,
                threshold_gib=threshold_gib,
                interactive=interactive,
                confirm_callback=confirm_callback,
            )
            time.sleep(self.config.poll_interval_sec)

    def _apply_llm_response(
        self,
        *,
        swap: SwapInfo,
        trigger_reason: str,
        trend: TrendInfo | None,
        candidates: list[ProcessInfo],
        llm_response: LLMResponse,
        dry_run: bool,
        interactive: bool,
        confirm_callback: ConfirmCallback | None,
    ) -> IncidentResult:
        candidate_by_pid = {candidate.pid: candidate for candidate in candidates}
        actions = []
        vetoes = []

        sorted_decisions = sorted(
            llm_response.decisions,
            key=lambda decision: decision.expected_memory_mb or 0,
            reverse=True,
        )

        executed_count = 0
        for decision in sorted_decisions:
            process = candidate_by_pid.get(decision.pid)
            if process is None:
                vetoes.append({"pid": decision.pid, "reason": "pid was not in candidate snapshot"})
                continue

            veto = local_veto(process, decision, rules=self.rules)
            if not veto.allowed:
                if interactive and self._can_offer_manual_confirmation(process, decision):
                    action = self._maybe_confirm_and_terminate(
                        process,
                        decision,
                        reason=veto.reason,
                        dry_run=dry_run,
                        confirm_callback=confirm_callback,
                    )
                    actions.append(action)
                    continue
                vetoes.append({"pid": process.pid, "name": process.name, "reason": veto.reason})
                continue

            if executed_count >= self.config.max_auto_terminations_per_incident:
                vetoes.append({"pid": process.pid, "name": process.name, "reason": "incident action limit reached"})
                continue

            action = terminate_process(process, decision, dry_run=dry_run, rules=self.rules)
            actions.append(action)
            if action.status in {"dry_run", "terminated", "timeout", "denied"}:
                executed_count += 1

        ask_confirm = [
            decision for decision in llm_response.decisions if decision.action.value == "ASK_CONFIRM"
        ]
        for decision in ask_confirm:
            if not interactive and decision_for_pid(llm_response.decisions, decision.pid):
                self.logger.info(
                    "manual confirmation suggested pid=%s name=%s reason=%s",
                    decision.pid,
                    decision.process_name,
                    decision.reason,
                )

        message = (
            f"swap {swap.used_gib:.2f} GiB crossed threshold; "
            f"{len(actions)} action(s), {len(vetoes)} veto(es)"
            if swap.used_gib is not None
            else f"swap crossed threshold; {len(actions)} action(s), {len(vetoes)} veto(es)"
        )
        self.logger.info(message)
        return IncidentResult(
            triggered=True,
            swap=swap,
            dry_run=dry_run,
            message=message,
            trigger_reason=trigger_reason,
            trend=trend,
            decisions=llm_response.decisions,
            actions=actions,
            vetoes=vetoes,
        )

    def _record_trend(self, swap: SwapInfo) -> TrendInfo | None:
        if not self.config.enable_trend_trigger and swap.used_gib is None:
            return None
        return self.trend_store.record(swap)

    def _below_threshold_message(self, swap: SwapInfo, threshold: float, trend: TrendInfo | None) -> str:
        if swap.used_gib is None:
            return f"memory free {swap.memory_free_percent}% above pressure threshold"
        trend_text = f"; {trend.reason}" if trend else ""
        return f"swap {swap.used_gib:.2f} GiB below threshold {threshold:.2f} GiB{trend_text}"

    @staticmethod
    def _trigger_reason(*, absolute_trigger: bool, trend_trigger: bool, pressure_trigger: bool) -> str:
        reasons = []
        if absolute_trigger:
            reasons.append("absolute_threshold")
        if trend_trigger:
            reasons.append("trend_growth")
        if pressure_trigger:
            reasons.append("memory_free_percent")
        return ",".join(reasons)

    def _can_offer_manual_confirmation(self, process: ProcessInfo, decision: LLMDecision) -> bool:
        return local_veto(process, decision, rules=self.rules, mode="manual").allowed

    def _maybe_confirm_and_terminate(
        self,
        process: ProcessInfo,
        decision: LLMDecision,
        *,
        reason: str,
        dry_run: bool,
        confirm_callback: ConfirmCallback | None,
    ) -> ActionResult:
        if confirm_callback is None:
            return ActionResult(
                pid=process.pid,
                process_name=process.name,
                action="manual_confirm",
                status="skipped",
                reason="manual confirmation is unavailable",
                dry_run=dry_run,
            )

        if not confirm_callback(process, decision, reason):
            return ActionResult(
                pid=process.pid,
                process_name=process.name,
                action="manual_confirm",
                status="declined",
                reason="user declined manual termination",
                dry_run=dry_run,
            )

        return terminate_process(process, decision, dry_run=dry_run, rules=self.rules, policy_mode="manual")

    def _notify(self, result: IncidentResult) -> None:
        if not result.triggered:
            return
        title = "MacOS Swap Killer"
        mode = "dry-run" if result.dry_run else "execute"
        message = f"{result.message} ({mode}; {result.trigger_reason or 'triggered'})"
        send_notification(title, message, enabled=self.config.notifications_enabled)

    @staticmethod
    def _record(
        result: IncidentResult,
        *,
        candidates: list[ProcessInfo] | None = None,
        llm_response: LLMResponse | None = None,
    ) -> None:
        write_event(
            {
                "event": "incident" if result.triggered else "scan",
                "result": result.model_dump(mode="json"),
                "candidate_count": len(candidates or []),
                "llm_response": llm_response.model_dump(mode="json") if llm_response else None,
            }
        )
