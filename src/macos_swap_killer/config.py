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
EVENTS_FILE = CONFIG_DIR / "events.jsonl"
LOG_FILE = LOG_DIR / "swap-killer.log"


@dataclass(slots=True)
class AppConfig:
    swap_threshold_gib: float = 10.0
    poll_interval_sec: int = 60
    cooldown_sec: int = 900
    max_auto_terminations_per_incident: int = 2
    min_candidate_rss_mb: float = 128.0
    max_candidates_for_llm: int = 25
    llm_timeout_sec: float = 30.0
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    api_key: str | None = None
    config_path: Path = CONFIG_FILE


DEFAULT_CONFIG_TEXT = """# MacOS Swap Killer config
swap_threshold_gib = 10
poll_interval_sec = 60
cooldown_sec = 900
max_auto_terminations_per_incident = 2
min_candidate_rss_mb = 128
max_candidates_for_llm = 25
llm_timeout_sec = 30

# LLM values can also be set in .env.
base_url = "https://api.deepseek.com"
model = "deepseek-v4-flash"
"""


DEFAULT_ENV_TEXT = """# Fill these values before enabling LLM decisions.
MSK_API_KEY=
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
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
        "base_url",
        "model",
    ):
        if field_name in data:
            setattr(config, field_name, data[field_name])

    config.api_key = os.getenv("MSK_API_KEY") or None
    config.base_url = os.getenv("MSK_BASE_URL") or str(config.base_url)
    config.model = os.getenv("MSK_MODEL") or str(config.model)
    return config
