from macos_swap_killer.actuator import terminate_process
from macos_swap_killer.models import DecisionAction, LLMDecision, ProcessInfo, RiskLevel


def test_dry_run_does_not_require_live_process_for_policy_veto() -> None:
    target = ProcessInfo(
        pid=1,
        ppid=0,
        user="root",
        name="launchd",
        exe="/sbin/launchd",
        cmdline=["/sbin/launchd"],
        rss_bytes=1,
    )
    decision = LLMDecision(
        pid=1,
        process_name="launchd",
        action=DecisionAction.TERMINATE,
        risk=RiskLevel.LOW,
        reason="bad recommendation",
    )
    result = terminate_process(target, decision, dry_run=True)
    assert result.status == "vetoed"
