from __future__ import annotations

import os
from dataclasses import dataclass

from .models import DecisionAction, LLMDecision, ProcessInfo


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


def local_veto(process: ProcessInfo, llm_decision: LLMDecision | None = None) -> PolicyDecision:
    if llm_decision and llm_decision.action != DecisionAction.TERMINATE:
        return PolicyDecision(False, f"llm action is {llm_decision.action.value}")

    if process.pid in {0, 1, os.getpid(), os.getppid()}:
        return PolicyDecision(False, "pid is protected")

    if is_protected_name(process.name):
        return PolicyDecision(False, "process name is hard-protected")

    if process.user is None:
        return PolicyDecision(False, "process owner is unknown")

    if process.user == "root" or process.user.startswith("_"):
        return PolicyDecision(False, "root or system-owned process")

    exe = process.exe or ""
    if exe.startswith(SYSTEM_PATH_PREFIXES):
        return PolicyDecision(False, "process executable is in a critical system path")

    if process.is_gui_main:
        return PolicyDecision(False, "main GUI application process requires manual confirmation")

    combined = " ".join([process.name, exe, *process.cmdline]).lower()
    if not any(token in combined for token in LOW_RISK_HELPER_TOKENS):
        return PolicyDecision(False, "process does not look like a low-risk helper/background worker")

    if llm_decision and llm_decision.risk.value != "low":
        return PolicyDecision(False, f"llm risk is {llm_decision.risk.value}")

    return PolicyDecision(True, "local policy allows conservative termination")


def decision_for_pid(decisions: list[LLMDecision], pid: int) -> LLMDecision | None:
    for decision in decisions:
        if decision.pid == pid:
            return decision
    return None
