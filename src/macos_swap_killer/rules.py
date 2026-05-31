from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .config import DEFAULT_RULES_TEXT, RULES_FILE
from .models import ProcessInfo


def _lower_set(values: list[str] | tuple[str, ...]) -> set[str]:
    return {value.lower() for value in values}


@dataclass(slots=True)
class UserRules:
    protected_names: set[str] = field(default_factory=lambda: {"wechat", "qq", "notes"})
    protected_path_prefixes: tuple[str, ...] = ()
    ask_confirm_names: set[str] = field(
        default_factory=lambda: {
            "google chrome",
            "microsoft edge",
            "safari",
            "code",
            "visual studio code",
            "docker desktop",
        }
    )
    ask_confirm_cmdline_contains: tuple[str, ...] = ("jupyter", "ipykernel", "ollama", "vllm", "mlx")
    auto_terminate_names: set[str] = field(default_factory=set)
    auto_terminate_cmdline_contains: tuple[str, ...] = (
        "pytest",
        "jest",
        "vitest",
        "tsserver",
        "eslint",
        "webpack",
        "vite",
    )

    def is_protected(self, process: ProcessInfo) -> bool:
        name = process.name.lower()
        exe = process.exe or ""
        return name in self.protected_names or any(exe.startswith(prefix) for prefix in self.protected_path_prefixes)

    def requires_confirmation(self, process: ProcessInfo) -> bool:
        name = process.name.lower()
        combined = " ".join([process.name, process.exe or "", *process.cmdline]).lower()
        return name in self.ask_confirm_names or any(token in combined for token in self.ask_confirm_cmdline_contains)

    def is_auto_allowed(self, process: ProcessInfo) -> bool:
        name = process.name.lower()
        combined = " ".join([process.name, process.exe or "", *process.cmdline]).lower()
        return name in self.auto_terminate_names or any(token in combined for token in self.auto_terminate_cmdline_contains)


def ensure_rules_file(force: bool = False, path: Path = RULES_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if force or not path.exists():
        path.write_text(DEFAULT_RULES_TEXT, encoding="utf-8")
    return path


def load_rules(path: Path = RULES_FILE) -> UserRules:
    if not path.exists():
        return UserRules()

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    protected = data.get("protected", {})
    ask_confirm = data.get("ask_confirm", {})
    auto_terminate = data.get("auto_terminate", {})
    defaults = UserRules()

    return UserRules(
        protected_names=_lower_set(protected.get("names", list(defaults.protected_names))),
        protected_path_prefixes=tuple(str(item) for item in protected.get("path_prefixes", [])),
        ask_confirm_names=_lower_set(ask_confirm.get("names", list(defaults.ask_confirm_names))),
        ask_confirm_cmdline_contains=tuple(
            str(item).lower() for item in ask_confirm.get("cmdline_contains", defaults.ask_confirm_cmdline_contains)
        ),
        auto_terminate_names=_lower_set(auto_terminate.get("names", [])),
        auto_terminate_cmdline_contains=tuple(
            str(item).lower()
            for item in auto_terminate.get("cmdline_contains", defaults.auto_terminate_cmdline_contains)
        ),
    )
