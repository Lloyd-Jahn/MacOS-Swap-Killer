from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_NAME = "MacOS Swap Killer"
CONFIG_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
LOG_DIR = Path.home() / "Library" / "Logs" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.toml"
ENV_FILE = CONFIG_DIR / ".env"
RULES_FILE = CONFIG_DIR / "rules.toml"
EVENTS_FILE = CONFIG_DIR / "events.jsonl"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"
LOG_FILE = LOG_DIR / "swap-killer.log"
LAUNCH_AGENT_LABEL = "com.lloyd-jahn.macos-swap-killer"
LAUNCH_AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


@dataclass(slots=True)
class AppConfig:
    swap_threshold_gib: float = 10.0
    poll_interval_sec: int = 60
    cooldown_sec: int = 900
    max_auto_terminations_per_incident: int = 2
    min_candidate_rss_mb: float = 128.0
    max_candidates_for_llm: int = 25
    llm_timeout_sec: float = 30.0
    enable_trend_trigger: bool = True
    trend_window_sec: int = 600
    swap_growth_threshold_gib: float = 2.0
    trend_history_limit: int = 500
    enable_memory_free_trigger: bool = True
    memory_free_percent_threshold: int = 10
    notifications_enabled: bool = True
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    api_key: str | None = None
    config_path: Path = CONFIG_FILE
    rules_path: Path = RULES_FILE
    history_path: Path = HISTORY_FILE


DEFAULT_CONFIG_TEXT = """# MacOS Swap Killer config
swap_threshold_gib = 10
poll_interval_sec = 60
cooldown_sec = 900
max_auto_terminations_per_incident = 2
min_candidate_rss_mb = 128
max_candidates_for_llm = 25
llm_timeout_sec = 30
enable_trend_trigger = true
trend_window_sec = 600
swap_growth_threshold_gib = 2.0
trend_history_limit = 500
enable_memory_free_trigger = true
memory_free_percent_threshold = 10
notifications_enabled = true
rules_path = ""
history_path = ""

# LLM values can also be set in .env.
base_url = "https://api.deepseek.com"
model = "deepseek-v4-flash"
"""


DEFAULT_ENV_TEXT = """# Fill these values before enabling LLM decisions.
MSK_API_KEY=
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
"""


DEFAULT_RULES_TEXT = """# MacOS Swap Killer user rules.
# These rules are local-only and are never sent to the LLM except as process-level hints.

[protected]
# Never terminate these process names, even after manual confirmation.
names = ["WeChat", "QQ", "Notes"]
path_prefixes = []

[ask_confirm]
# These process names can be suggested, but require explicit terminal confirmation.
names = ["Google Chrome", "Microsoft Edge", "Safari", "Code", "Visual Studio Code", "Docker Desktop"]
cmdline_contains = ["jupyter", "ipykernel", "ollama", "vllm", "mlx"]

[auto_terminate]
# Automatic termination still requires LLM action=TERMINATE, LLM risk=low, and all hard safety checks.
names = []
cmdline_contains = ["pytest", "jest", "vitest", "tsserver", "eslint", "webpack", "vite"]
"""


def ensure_user_files(force: bool = False) -> list[Path]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if force or not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
        written.append(CONFIG_FILE)

    if force or not ENV_FILE.exists():
        ENV_FILE.write_text(DEFAULT_ENV_TEXT, encoding="utf-8")
        ENV_FILE.chmod(0o600)
        written.append(ENV_FILE)

    if force or not RULES_FILE.exists():
        RULES_FILE.write_text(DEFAULT_RULES_TEXT, encoding="utf-8")
        written.append(RULES_FILE)

    return written


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or CONFIG_FILE
    data: dict[str, object] = {}
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)
    load_dotenv(override=False)

    config = AppConfig(config_path=path)
    for field_name in (
        "swap_threshold_gib",
        "poll_interval_sec",
        "cooldown_sec",
        "max_auto_terminations_per_incident",
        "min_candidate_rss_mb",
        "max_candidates_for_llm",
        "llm_timeout_sec",
        "enable_trend_trigger",
        "trend_window_sec",
        "swap_growth_threshold_gib",
        "trend_history_limit",
        "enable_memory_free_trigger",
        "memory_free_percent_threshold",
        "notifications_enabled",
        "base_url",
        "model",
    ):
        if field_name in data:
            setattr(config, field_name, data[field_name])

    if data.get("rules_path"):
        config.rules_path = Path(str(data["rules_path"])).expanduser()
    if data.get("history_path"):
        config.history_path = Path(str(data["history_path"])).expanduser()

    config.api_key = os.getenv("MSK_API_KEY") or None
    config.base_url = os.getenv("MSK_BASE_URL") or str(config.base_url)
    config.model = os.getenv("MSK_MODEL") or str(config.model)
    return config
