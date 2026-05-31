from __future__ import annotations

import logging
import time
from collections.abc import Callable

from .actuator import terminate_process
from .config import AppConfig
from .llm import LLMClient
from .models import IncidentResult, LLMResponse, ProcessInfo, SwapInfo
from .policy import decision_for_pid, local_veto
from .privacy import summarize_processes
from .processes import collect_processes, select_candidates
from .swap import get_swap_info
from .logging_utils import write_event


SwapProvider = Callable[[], SwapInfo]
ProcessProvider = Callable[[], list[ProcessInfo]]


class SwapKiller:
    def __init__(
        self,
        config: AppConfig,
        *,
        logger: logging.Logger,
        swap_provider: SwapProvider = get_swap_info,
        process_provider: ProcessProvider = collect_processes,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.swap_provider = swap_provider
        self.process_provider = process_provider
        self.llm_client = llm_client or LLMClient(config)
        self._last_incident_at = 0.0

    def run_once(self, *, dry_run: bool, threshold_gib: float | None = None) -> IncidentResult:
        threshold = threshold_gib if threshold_gib is not None else self.config.swap_threshold_gib
        swap = self.swap_provider()

        if swap.used_gib is None:
            message = f"swap usage unavailable from {swap.source}; skipping actions"
            self.logger.warning(message)
            result = IncidentResult(triggered=False, swap=swap, dry_run=dry_run, message=message)
            self._record(result)
            return result

        if swap.used_gib < threshold:
            message = f"swap {swap.used_gib:.2f} GiB below threshold {threshold:.2f} GiB"
            self.logger.info(message)
            return IncidentResult(triggered=False, swap=swap, dry_run=dry_run, message=message)

        now = time.monotonic()
        if now - self._last_incident_at < self.config.cooldown_sec:
            message = "swap threshold crossed, but incident is in cooldown"
            self.logger.info(message)
            result = IncidentResult(triggered=True, swap=swap, dry_run=dry_run, message=message)
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
            result = IncidentResult(triggered=True, swap=swap, dry_run=dry_run, message=message)
            self._record(result)
            return result

        if not self.config.api_key:
            message = "MSK_API_KEY is not configured; no LLM decision or action was taken"
            self.logger.warning(message)
            result = IncidentResult(triggered=True, swap=swap, dry_run=dry_run, message=message)
            self._record(result, candidates=candidates)
            return result

        try:
            llm_response = self.llm_client.classify(swap, summarize_processes(candidates))
        except Exception as exc:  # noqa: BLE001 - bad LLM/API state must fail closed.
            message = f"LLM classification failed closed: {exc}"
            self.logger.error(message)
            result = IncidentResult(triggered=True, swap=swap, dry_run=dry_run, message=message)
            self._record(result, candidates=candidates)
            return result

        result = self._apply_llm_response(
            swap=swap,
            candidates=candidates,
            llm_response=llm_response,
            dry_run=dry_run,
        )
        self._record(result, candidates=candidates, llm_response=llm_response)
        return result

    def watch(self, *, dry_run: bool, threshold_gib: float | None = None) -> None:
        self.logger.info(
            "watch started threshold=%s dry_run=%s interval=%ss",
            threshold_gib if threshold_gib is not None else self.config.swap_threshold_gib,
            dry_run,
            self.config.poll_interval_sec,
        )
        while True:
            self.run_once(dry_run=dry_run, threshold_gib=threshold_gib)
            time.sleep(self.config.poll_interval_sec)

    def _apply_llm_response(
        self,
        *,
        swap: SwapInfo,
        candidates: list[ProcessInfo],
        llm_response: LLMResponse,
        dry_run: bool,
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

            veto = local_veto(process, decision)
            if not veto.allowed:
                vetoes.append({"pid": process.pid, "name": process.name, "reason": veto.reason})
                continue

            if executed_count >= self.config.max_auto_terminations_per_incident:
                vetoes.append({"pid": process.pid, "name": process.name, "reason": "incident action limit reached"})
                continue

            action = terminate_process(process, decision, dry_run=dry_run)
            actions.append(action)
            if action.status in {"dry_run", "terminated", "timeout", "denied"}:
                executed_count += 1

        ask_confirm = [
            decision for decision in llm_response.decisions if decision.action.value == "ASK_CONFIRM"
        ]
        for decision in ask_confirm:
            if decision_for_pid(llm_response.decisions, decision.pid):
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
            decisions=llm_response.decisions,
            actions=actions,
            vetoes=vetoes,
        )

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
