from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import EVENTS_FILE


def load_events(path: Path = EVENTS_FILE, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit is not None:
        lines = lines[-limit:]

    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    incidents = [event for event in events if event.get("event") == "incident"]
    swaps: list[tuple[float, str]] = []
    action_statuses: Counter[str] = Counter()
    veto_reasons: Counter[str] = Counter()
    decision_actions: Counter[str] = Counter()
    process_hits: Counter[str] = Counter()

    for event in events:
        result = event.get("result") or {}
        swap = result.get("swap") or {}
        used = swap.get("used_gib")
        if isinstance(used, int | float):
            swaps.append((float(used), str(event.get("timestamp", ""))))

        for action in result.get("actions") or []:
            action_statuses[str(action.get("status", "unknown"))] += 1
            process_hits[str(action.get("process_name", "unknown"))] += 1

        for veto in result.get("vetoes") or []:
            veto_reasons[str(veto.get("reason", "unknown"))] += 1
            if veto.get("name"):
                process_hits[str(veto["name"])] += 1

        for decision in result.get("decisions") or []:
            decision_actions[str(decision.get("action", "unknown"))] += 1
            process_hits[str(decision.get("process_name", "unknown"))] += 1

    max_swap = max(swaps, default=(0.0, ""))
    latest_event = events[-1] if events else None
    return {
        "event_count": len(events),
        "incident_count": len(incidents),
        "max_swap_gib": round(max_swap[0], 3),
        "max_swap_at": max_swap[1],
        "latest_timestamp": latest_event.get("timestamp") if latest_event else None,
        "action_statuses": dict(action_statuses.most_common()),
        "decision_actions": dict(decision_actions.most_common()),
        "top_veto_reasons": dict(veto_reasons.most_common(10)),
        "top_processes": dict(process_hits.most_common(10)),
    }


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "MacOS Swap Killer Report",
        f"Events: {summary['event_count']}",
        f"Incidents: {summary['incident_count']}",
        f"Max swap: {summary['max_swap_gib']} GiB at {summary['max_swap_at'] or 'n/a'}",
        f"Latest event: {summary['latest_timestamp'] or 'n/a'}",
        "",
        "Decision actions:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in summary["decision_actions"].items())
    lines.append("")
    lines.append("Action statuses:")
    lines.extend(f"  {key}: {value}" for key, value in summary["action_statuses"].items())
    lines.append("")
    lines.append("Top veto reasons:")
    lines.extend(f"  {key}: {value}" for key, value in summary["top_veto_reasons"].items())
    lines.append("")
    lines.append("Top processes:")
    lines.extend(f"  {key}: {value}" for key, value in summary["top_processes"].items())
    return "\n".join(lines)
