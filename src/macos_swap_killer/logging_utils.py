from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from .config import CONFIG_DIR, EVENTS_FILE, LOG_DIR, LOG_FILE


def setup_logging(verbose: bool = False) -> logging.Logger:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("macos_swap_killer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(stream_handler)

    return logger


def write_event(event: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        **event,
    }
    with EVENTS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
