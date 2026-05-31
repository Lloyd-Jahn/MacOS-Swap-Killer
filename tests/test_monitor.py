import logging

from macos_swap_killer.config import AppConfig
from macos_swap_killer.models import ActionResult, DecisionAction, LLMDecision, LLMResponse, ProcessInfo, RiskLevel, SwapInfo
from macos_swap_killer.monitor import SwapKiller
from macos_swap_killer.rules import UserRules
from macos_swap_killer.trends import TrendStore


class FakeLLM:
    def classify(self, swap, candidates):  # noqa: ANN001
        return LLMResponse(
            overall_risk=RiskLevel.MEDIUM,
            decisions=[
                LLMDecision(
                    pid=22222,
                    process_name="Code Helper (Plugin)",
                    action=DecisionAction.ASK_CONFIRM,
                    risk=RiskLevel.MEDIUM,
                    reason="needs user confirmation",
                )
            ],
        )


def test_interactive_confirmation_path(monkeypatch, tmp_path) -> None:
    config = AppConfig(
        api_key="test",
        notifications_enabled=False,
        history_path=tmp_path / "history.jsonl",
        rules_path=tmp_path / "missing-rules.toml",
    )
    process = ProcessInfo(
        pid=22222,
        ppid=100,
        user="jiangyi",
        name="Code Helper (Plugin)",
        exe="/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper.app/Contents/MacOS/Code Helper",
        cmdline=["Code Helper", "--type=utility"],
        rss_bytes=512 * 1024 * 1024,
        is_gui_main=False,
    )

    def fake_terminate(target, decision, *, dry_run, rules, policy_mode="auto", wait_sec=8.0):  # noqa: ANN001
        return ActionResult(
            pid=target.pid,
            process_name=target.name,
            action="terminate",
            status="dry_run",
            reason=policy_mode,
            dry_run=dry_run,
        )

    monkeypatch.setattr("macos_swap_killer.monitor.terminate_process", fake_terminate)
    monkeypatch.setattr("macos_swap_killer.logging_utils.EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr("macos_swap_killer.logging_utils.CONFIG_DIR", tmp_path)

    killer = SwapKiller(
        config,
        logger=logging.getLogger("test"),
        swap_provider=lambda: SwapInfo(used_gib=12.0, total_gib=16.0, free_gib=4.0, source="test"),
        process_provider=lambda: [process],
        llm_client=FakeLLM(),
        rules=UserRules(protected_names=set(), ask_confirm_names=set(), ask_confirm_cmdline_contains=()),
        trend_store=TrendStore(tmp_path / "history.jsonl", window_sec=600, growth_threshold_gib=2.0, max_samples=10),
    )
    result = killer.run_once(
        dry_run=True,
        threshold_gib=10,
        interactive=True,
        confirm_callback=lambda *_args: True,
    )

    assert result.triggered
    assert result.actions[0].status == "dry_run"
    assert result.actions[0].reason == "manual"
