from __future__ import annotations

from dataclasses import dataclass

from .models import ProcessInfo


@dataclass(frozen=True, slots=True)
class PlaybookAdvice:
    app_family: str
    role: str
    recommendation: str
    reason: str
    auto_eligible: bool = False


def advise_process(process: ProcessInfo) -> PlaybookAdvice:
    combined = " ".join([process.name, process.exe or "", *process.cmdline]).lower()

    if any(name in combined for name in ("google chrome", "microsoft edge", "chromium", "safari")):
        if process.is_gui_main:
            return PlaybookAdvice("browser", "main_app", "ignore", "browser main app may contain user state")
        if any(token in combined for token in ("renderer", "gpu", "utility", "helper")):
            return PlaybookAdvice("browser", "helper", "terminate_if_low_risk", "browser helper process is usually recoverable", True)
        return PlaybookAdvice("browser", "background", "ask_confirm", "browser background process needs confirmation")

    if "visual studio code" in combined or process.name.lower().startswith("code"):
        if process.is_gui_main or process.name.lower() == "code":
            return PlaybookAdvice("vscode", "main_app", "ignore", "editor main app may contain unsaved files")
        if "plugin" in combined or "extension" in combined:
            return PlaybookAdvice("vscode", "extension_host", "ask_confirm", "extension host may be running active work")
        if any(token in combined for token in ("renderer", "gpu", "utility", "helper")):
            return PlaybookAdvice("vscode", "helper", "terminate_if_low_risk", "VS Code helper process is usually recoverable", True)
        return PlaybookAdvice("vscode", "background", "ask_confirm", "VS Code child process needs confirmation")

    if any(token in combined for token in ("wechat", "qq", "notes")):
        return PlaybookAdvice("user_state_app", "main_or_helper", "protect", "messaging/notes apps may contain unsaved user state")

    if "docker" in combined or "com.docker" in combined:
        return PlaybookAdvice("docker", "service", "ask_confirm", "Docker processes may own running containers")

    if any(token in combined for token in ("jupyter", "ipykernel", "notebook", "python")):
        if any(token in combined for token in ("pytest", "tox", "nox", "coverage")):
            return PlaybookAdvice("python", "test_worker", "terminate_if_low_risk", "test workers are usually restartable", True)
        if any(token in combined for token in ("jupyter", "ipykernel", "notebook")):
            return PlaybookAdvice("python", "notebook_kernel", "ask_confirm", "notebook kernels can hold unsaved in-memory state")
        return PlaybookAdvice("python", "worker", "ask_confirm", "Python process needs user context before termination")

    if "node" in combined:
        if any(token in combined for token in ("jest", "vitest", "webpack", "vite", "tsserver", "eslint")):
            return PlaybookAdvice("node", "dev_worker", "terminate_if_low_risk", "development worker is usually restartable", True)
        return PlaybookAdvice("node", "service", "ask_confirm", "Node process may be a user service")

    if any(token in combined for token in ("ollama", "vllm", "mlx", "llama.cpp")):
        return PlaybookAdvice("local_ai", "model_service", "ask_confirm", "local AI jobs may be expensive to restart")

    return PlaybookAdvice("unknown", "unknown", "ask_confirm", "no app-specific playbook matched")
