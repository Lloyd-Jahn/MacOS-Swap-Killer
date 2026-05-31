import os

from macos_swap_killer.models import DecisionAction, LLMDecision, ProcessInfo, RiskLevel
from macos_swap_killer.policy import NEVER_KILL_NAMES, local_veto


def decision(pid: int) -> LLMDecision:
    return LLMDecision(
        pid=pid,
        process_name="Code Helper (Renderer)",
        action=DecisionAction.TERMINATE,
        risk=RiskLevel.LOW,
        reason="low-risk helper",
        expected_memory_mb=1024,
    )


def process(**overrides: object) -> ProcessInfo:
    base = {
        "pid": 12345,
        "ppid": 100,
        "user": os.getenv("USER") or "user",
        "name": "Code Helper (Renderer)",
        "exe": "/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper.app/Contents/MacOS/Code Helper",
        "cmdline": ["Code Helper", "--type=renderer"],
        "rss_bytes": 1024 * 1024 * 1024,
        "memory_percent": 5.0,
        "create_time": 1.0,
        "status": "running",
        "parent_name": "Code",
        "is_gui_main": False,
        "executable_category": "gui_app",
    }
    base.update(overrides)
    return ProcessInfo(**base)


def test_never_kill_names_are_vetoed() -> None:
    for name in NEVER_KILL_NAMES:
        target = process(name=name)
        veto = local_veto(target, decision(target.pid))
        assert not veto.allowed


def test_root_process_is_vetoed() -> None:
    target = process(user="root")
    assert not local_veto(target, decision(target.pid)).allowed


def test_system_path_is_vetoed() -> None:
    target = process(exe="/System/Library/CoreServices/Dock.app/Contents/MacOS/Dock")
    assert not local_veto(target, decision(target.pid)).allowed


def test_main_gui_app_is_vetoed() -> None:
    target = process(name="Google Chrome", is_gui_main=True, cmdline=["Google Chrome"])
    veto = local_veto(target, decision(target.pid))
    assert not veto.allowed
    assert "main GUI" in veto.reason


def test_low_risk_helper_is_allowed() -> None:
    target = process()
    veto = local_veto(target, decision(target.pid))
    assert veto.allowed


def test_non_terminate_llm_action_is_vetoed() -> None:
    target = process()
    llm_decision = decision(target.pid)
    llm_decision.action = DecisionAction.ASK_CONFIRM
    assert not local_veto(target, llm_decision).allowed
