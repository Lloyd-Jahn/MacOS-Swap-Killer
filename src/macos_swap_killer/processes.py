from __future__ import annotations

from pathlib import Path

import psutil

from .models import ProcessInfo


HELPER_TOKENS = (
    "helper",
    "renderer",
    "gpu",
    "plugin",
    "extension",
    "worker",
    "utility",
    "crashpad",
    "zygote",
    "web content",
    "node service",
)


def executable_category(exe: str | None) -> str:
    if not exe:
        return "unknown"
    if exe.startswith("/System/") or exe.startswith("/usr/libexec/") or exe.startswith("/sbin/"):
        return "system"
    if exe.startswith("/usr/sbin/"):
        return "system"
    if exe.startswith("/Applications/") and ".app/" in exe:
        return "gui_app"
    if "/Library/" in exe and ".app/" in exe:
        return "gui_app"
    if exe.startswith(str(Path.home())):
        return "user_home"
    return "background_or_cli"


def is_main_gui_app(name: str, exe: str | None, cmdline: list[str], ppid: int | None) -> bool:
    if not exe or ".app/Contents/MacOS/" not in exe:
        return False

    combined = " ".join([name, exe, *cmdline]).lower()
    if any(token in combined for token in HELPER_TOKENS):
        return False

    # macOS launches most top-level GUI apps directly from launchd.
    return ppid == 1 or exe.startswith("/Applications/")


def _safe_parent_name(proc: psutil.Process) -> str | None:
    try:
        parent = proc.parent()
        return parent.name() if parent else None
    except psutil.Error:
        return None


def collect_processes() -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []
    attrs = ["pid", "ppid", "username", "name", "exe", "cmdline", "memory_info", "memory_percent", "create_time", "status"]

    for proc in psutil.process_iter(attrs=attrs):
        try:
            info = proc.info
            name = info.get("name") or ""
            exe = info.get("exe")
            cmdline = info.get("cmdline") or []
            ppid = info.get("ppid")
            rss = int(getattr(info.get("memory_info"), "rss", 0) or 0)
            processes.append(
                ProcessInfo(
                    pid=int(info["pid"]),
                    ppid=int(ppid) if ppid is not None else None,
                    user=info.get("username"),
                    name=name,
                    exe=exe,
                    cmdline=list(cmdline),
                    rss_bytes=rss,
                    memory_percent=float(info.get("memory_percent") or 0.0),
                    create_time=info.get("create_time"),
                    status=info.get("status"),
                    parent_name=_safe_parent_name(proc),
                    is_gui_main=is_main_gui_app(name, exe, list(cmdline), ppid),
                    executable_category=executable_category(exe),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(processes, key=lambda item: item.rss_bytes, reverse=True)


def select_candidates(
    processes: list[ProcessInfo],
    min_rss_mb: float,
    max_candidates: int,
) -> list[ProcessInfo]:
    min_bytes = min_rss_mb * 1024 * 1024
    return [process for process in processes if process.rss_bytes >= min_bytes][:max_candidates]
