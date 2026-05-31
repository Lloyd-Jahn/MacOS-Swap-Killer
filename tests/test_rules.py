from pathlib import Path

from macos_swap_killer.models import DecisionAction, LLMDecision, ProcessInfo, RiskLevel
from macos_swap_killer.policy import local_veto
from macos_swap_killer.rules import UserRules, load_rules


def process(**overrides: object) -> ProcessInfo:
    base = {
        "pid": 23456,
        "ppid": 100,
        "user": "jiangyi",
        "name": "node",
        "exe": "/usr/local/bin/node",
        "cmdline": ["node", "node_modules/.bin/vite"],
        "rss_bytes": 1024 * 1024 * 1024,
        "memory_percent": 5.0,
        "create_time": 1.0,
        "status": "running",
        "parent_name": "zsh",
        "is_gui_main": False,
        "executable_category": "background_or_cli",
    }
    base.update(overrides)
    return ProcessInfo(**base)


def decision(pid: int) -> LLMDecision:
    return LLMDecision(
        pid=pid,
        process_name="node",
        action=DecisionAction.TERMINATE,
        risk=RiskLevel.LOW,
        reason="restartable dev worker",
    )


def test_load_rules_from_toml(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text(
        """
        [protected]
        names = ["WeChat"]
        path_prefixes = ["/secret"]

        [ask_confirm]
        names = ["Python"]
        cmdline_contains = ["ipykernel"]

        [auto_terminate]
        names = ["node"]
        cmdline_contains = ["vite"]
        """,
        encoding="utf-8",
    )
    rules = load_rules(rules_file)
    assert "wechat" in rules.protected_names
    assert rules.protected_path_prefixes == ("/secret",)
    assert rules.is_auto_allowed(process())


def test_user_rules_can_protect_process_even_manually() -> None:
    target = process(name="WeChat", cmdline=["WeChat"])
    rules = UserRules(protected_names={"wechat"})
    veto = local_veto(target, decision(target.pid), rules=rules, mode="manual")
    assert not veto.allowed
    assert "user rules" in veto.reason


def test_user_auto_rule_still_requires_low_risk_llm() -> None:
    target = process()
    rules = UserRules(auto_terminate_names={"node"})
    llm_decision = decision(target.pid)
    llm_decision.risk = RiskLevel.MEDIUM
    veto = local_veto(target, llm_decision, rules=rules)
    assert not veto.allowed
    assert "llm risk" in veto.reason
