from __future__ import annotations

import re
from pathlib import Path

from .models import ProcessInfo, ProcessSummary


SECRET_ARG_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer)(=|:)?[^\s]*"
)
URL_CREDENTIAL_RE = re.compile(r"([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@", re.IGNORECASE)
LONG_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])")
ABS_PATH_RE = re.compile(r"(/Users/[^/\s]+|/private/tmp|/var/folders|/tmp)(/[^\s]*)?")


def redact_text(value: str) -> str:
    text = value.replace(str(Path.home()), "~")
    text = URL_CREDENTIAL_RE.sub(r"\1<redacted>@", text)
    text = SECRET_ARG_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = LONG_SECRET_RE.sub("<redacted>", text)
    text = ABS_PATH_RE.sub(_redact_path_match, text)
    return text


def _redact_path_match(match: re.Match[str]) -> str:
    raw = match.group(0).replace(str(Path.home()), "~")
    parts = raw.split("/")
    if len(parts) <= 4:
        return raw
    tail = "/".join(parts[-2:])
    if raw.startswith("~"):
        return f"~/.../{tail}"
    return f"/.../{tail}"


def summarize_process(process: ProcessInfo) -> ProcessSummary:
    return ProcessSummary(
        pid=process.pid,
        ppid=process.ppid,
        user=process.user,
        name=process.name,
        parent_name=process.parent_name,
        rss_mb=round(process.rss_mb, 1),
        memory_percent=round(process.memory_percent, 2),
        executable_category=process.executable_category,
        is_gui_main=process.is_gui_main,
        redacted_cmdline=[redact_text(arg) for arg in process.cmdline[:20]],
    )


def summarize_processes(processes: list[ProcessInfo]) -> list[ProcessSummary]:
    return [summarize_process(process) for process in processes]
