from __future__ import annotations

import json
import shutil
import subprocess


def send_notification(title: str, message: str, *, enabled: bool = True) -> bool:
    if not enabled or not shutil.which("osascript"):
        return False

    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return True
