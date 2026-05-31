from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from .config import LAUNCH_AGENT_FILE, LAUNCH_AGENT_LABEL, LOG_DIR


def build_agent_plist(*, execute: bool, python_executable: str | None = None) -> dict[str, object]:
    mode = "--execute" if execute else "--dry-run"
    executable = python_executable or sys.executable
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            executable,
            "-m",
            "macos_swap_killer.cli",
            "watch",
            mode,
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.err.log"),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
        },
    }


def install_agent(*, execute: bool, load: bool = True, path: Path = LAUNCH_AGENT_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(build_agent_plist(execute=execute), handle)

    if load:
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], check=False)
        subprocess.run(["launchctl", "enable", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"], check=False)
    return path


def uninstall_agent(*, unload: bool = True, path: Path = LAUNCH_AGENT_FILE) -> bool:
    if unload:
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], check=False)
    if path.exists():
        path.unlink()
        return True
    return False


def agent_status(path: Path = LAUNCH_AGENT_FILE) -> dict[str, object]:
    loaded = False
    try:
        completed = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        loaded = completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        loaded = False
    return {
        "label": LAUNCH_AGENT_LABEL,
        "plist": str(path),
        "plist_exists": path.exists(),
        "loaded": loaded,
    }
