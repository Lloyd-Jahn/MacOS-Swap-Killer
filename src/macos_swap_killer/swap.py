from __future__ import annotations

import re
import subprocess

from .models import SwapInfo


SIZE_RE = re.compile(r"(total|used|free)\s*=\s*([0-9.]+)\s*([KMGT]?)", re.IGNORECASE)
TOP_SWAP_RE = re.compile(
    r"Swap:\s*(?P<used>[0-9.]+)(?P<used_unit>[KMGT])?\s+used,\s*"
    r"(?P<free>[0-9.]+)(?P<free_unit>[KMGT])?\s+free",
    re.IGNORECASE,
)
MEMORY_FREE_RE = re.compile(r"System-wide memory free percentage:\s*(\d+)%")


def _to_gib(value: float, unit: str | None) -> float:
    normalized = (unit or "B").upper()
    if normalized == "T":
        return value * 1024
    if normalized == "G":
        return value
    if normalized == "M":
        return value / 1024
    if normalized == "K":
        return value / 1024 / 1024
    return value / 1024 / 1024 / 1024


def parse_sysctl_swapusage(text: str) -> SwapInfo:
    values: dict[str, float] = {}
    for key, value, unit in SIZE_RE.findall(text):
        values[key.lower()] = _to_gib(float(value), unit)

    if "used" not in values:
        raise ValueError("sysctl output did not contain swap used value")

    return SwapInfo(
        used_gib=values.get("used"),
        total_gib=values.get("total"),
        free_gib=values.get("free"),
        source="sysctl",
        raw=text.strip(),
    )


def parse_top_swap(text: str) -> SwapInfo:
    match = TOP_SWAP_RE.search(text)
    if not match:
        raise ValueError("top output did not contain swap values")
    used = _to_gib(float(match.group("used")), match.group("used_unit"))
    free = _to_gib(float(match.group("free")), match.group("free_unit"))
    return SwapInfo(
        used_gib=used,
        total_gib=used + free,
        free_gib=free,
        source="top",
        raw=match.group(0),
    )


def parse_memory_pressure(text: str) -> SwapInfo:
    match = MEMORY_FREE_RE.search(text)
    free_percent = int(match.group(1)) if match else None
    return SwapInfo(
        used_gib=None,
        source="memory_pressure",
        raw=text.strip(),
        memory_free_percent=free_percent,
    )


def _run(command: list[str], timeout: float = 5.0) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


def get_swap_info() -> SwapInfo:
    errors: list[str] = []

    try:
        return parse_sysctl_swapusage(_run(["sysctl", "vm.swapusage"]))
    except Exception as exc:  # noqa: BLE001 - fallback should keep monitoring alive.
        errors.append(f"sysctl: {exc}")

    try:
        return parse_top_swap(_run(["top", "-l", "1", "-s", "0", "-n", "0"], timeout=8))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"top: {exc}")

    try:
        info = parse_memory_pressure(_run(["memory_pressure"]))
        info.raw = info.raw + "\n\nFallback errors:\n" + "\n".join(errors)
        return info
    except Exception as exc:  # noqa: BLE001
        errors.append(f"memory_pressure: {exc}")

    return SwapInfo(
        used_gib=None,
        source="unavailable",
        raw="\n".join(errors),
    )
