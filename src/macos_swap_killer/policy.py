from __future__ import annotations

import os
from dataclasses import dataclass

from .models import DecisionAction, LLMDecision, ProcessInfo
from .playbooks import advise_process
from .rules import UserRules


NEVER_KILL_NAMES = {
    "WindowServer",
    "kernel_task",
    "launchd",
    "loginwindow",
    "Finder",
    "Dock",
    "SystemUIServer",
}

SYSTEM_PATH_PREFIXES = (
    "/System/",
    "/usr/libexec/",
    "/sbin/",
    "/usr/sbin/",
)

LOW_RISK_HELPER_TOKENS = (
    "helper",
    "renderer",
    "gpu",
    "plugin",
    "extension",
    "worker",
    "utility",
    "cache",
    "build",
    "test",
    "node",
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


def is_protected_name(name: str) -> bool:
    lowered = name.lower()
    return any(lowered == protected.lower() for protected in NEVER_KILL_NAMES)


def local_veto(
    process: ProcessInfo,
    llm_decision: LLMDecision | None = None,
    *,
    rules: UserRules | None = None,
    mode: str = "auto",
) -> PolicyDecision:
    if mode not in {"auto", "manual"}:
        return PolicyDecision(False, f"unknown policy mode {mode}")

    if mode == "auto" and llm_decision and llm_decision.action != DecisionAction.TERMINATE:
        return PolicyDecision(False, f"llm action is {llm_decision.action.value}")

    if process.pid in {0, 1, os.getpid(), os.getppid()}:
        return PolicyDecision(False, "pid is protected")

    if is_protected_name(process.name):
        return PolicyDecision(False, "process name is hard-protected")

    if rules and rules.is_protected(process):
        return PolicyDecision(False, "process is protected by user rules")

    if process.user is None:
        return PolicyDecision(False, "process owner is unknown")

    if process.user == "root" or process.user.startswith("_"):
        return PolicyDecision(False, "root or system-owned process")

    exe = process.exe or ""
    if exe.startswith(SYSTEM_PATH_PREFIXES):
        return PolicyDecision(False, "process executable is in a critical system path")

    if mode == "manual":
        if llm_decision and llm_decision.action == DecisionAction.IGNORE:
            return PolicyDecision(False, "llm action is IGNORE")
        return PolicyDecision(True, "manual confirmation can terminate this user process")

    advice = advise_process(process)

    if process.is_gui_main:
        return PolicyDecision(False, "main GUI application process requires manual confirmation")

    if rules and rules.requires_confirmation(process):
        return PolicyDecision(False, "user rules require manual confirmation")

    if advice.recommendation == "protect":
        return PolicyDecision(False, f"app playbook protects this process: {advice.reason}")

    if advice.recommendation == "ask_confirm":
        return PolicyDecision(False, f"app playbook requires manual confirmation: {advice.reason}")

    if llm_decision and llm_decision.risk.value != "low":
        return PolicyDecision(False, f"llm risk is {llm_decision.risk.value}")

    combined = " ".join([process.name, exe, *process.cmdline]).lower()
    rules_allow_auto = rules.is_auto_allowed(process) if rules else False
    if not (rules_allow_auto or advice.auto_eligible or any(token in combined for token in LOW_RISK_HELPER_TOKENS)):
        return PolicyDecision(False, "process does not look like a low-risk helper/background worker")

    return PolicyDecision(True, "local policy allows conservative termination")


def decision_for_pid(decisions: list[LLMDecision], pid: int) -> LLMDecision | None:
    for decision in decisions:
        if decision.pid == pid:
            return decision
    return None
