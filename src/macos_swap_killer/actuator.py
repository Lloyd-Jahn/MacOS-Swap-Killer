from __future__ import annotations

import math

import psutil

from .models import ActionResult, LLMDecision, ProcessInfo
from .policy import local_veto


def _same_process(snapshot: ProcessInfo, live: psutil.Process) -> bool:
    if snapshot.create_time is None:
        return True
    try:
        return math.isclose(float(snapshot.create_time), float(live.create_time()), abs_tol=1.0)
    except psutil.Error:
        return False


def terminate_process(
    process: ProcessInfo,
    decision: LLMDecision,
    *,
    dry_run: bool,
    wait_sec: float = 8.0,
) -> ActionResult:
    veto = local_veto(process, decision)
    if not veto.allowed:
        return ActionResult(
            pid=process.pid,
            process_name=process.name,
            action="terminate",
            status="vetoed",
            reason=veto.reason,
            dry_run=dry_run,
        )

    try:
        live = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return ActionResult(
            pid=process.pid,
            process_name=process.name,
            action="terminate",
            status="gone",
            reason="process exited before action",
            dry_run=dry_run,
        )

    if not _same_process(process, live):
        return ActionResult(
            pid=process.pid,
            process_name=process.name,
            action="terminate",
            status="vetoed",
            reason="pid was reused after snapshot",
            dry_run=dry_run,
        )

    if dry_run:
        return ActionResult(
            pid=process.pid,
            process_name=process.name,
            action="terminate",
            status="dry_run",
            reason="would send SIGTERM",
            dry_run=True,
        )

    try:
        live.terminate()
        live.wait(timeout=wait_sec)
        status = "terminated"
        reason = "process exited after SIGTERM"
    except psutil.TimeoutExpired:
        status = "timeout"
        reason = "process did not exit after SIGTERM; SIGKILL is not used in v1"
    except psutil.AccessDenied:
        status = "denied"
        reason = "permission denied"
    except psutil.NoSuchProcess:
        status = "terminated"
        reason = "process exited during action"

    return ActionResult(
        pid=process.pid,
        process_name=process.name,
        action="terminate",
        status=status,
        reason=reason,
        dry_run=False,
    )
