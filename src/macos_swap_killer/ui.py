from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import (
    CONFIG_DIR,
    CONFIG_FILE,
    EVENTS_FILE,
    LOG_FILE,
    RULES_FILE,
    AppConfig,
    ensure_user_files,
    load_config,
)
from .launchd import agent_status
from .logging_utils import setup_logging
from .models import SwapInfo
from .monitor import SwapKiller
from .reporting import load_events, render_summary, summarize_events
from .swap import get_swap_info


STATUS_LABELS = (
    "Swap used",
    "Swap total",
    "Memory free",
    "Swap source",
    "API key",
    "Model",
    "Threshold",
    "Events",
    "Incidents",
    "Max swap",
    "Latest event",
    "Launch agent",
)


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    swap_used: str
    swap_total: str
    memory_free: str
    swap_source: str
    api_status: str
    model: str
    threshold: str
    events: str
    incidents: str
    max_swap: str
    latest_event: str
    agent: str

    def rows(self) -> list[tuple[str, str]]:
        return list(
            zip(
                STATUS_LABELS,
                (
                    self.swap_used,
                    self.swap_total,
                    self.memory_free,
                    self.swap_source,
                    self.api_status,
                    self.model,
                    self.threshold,
                    self.events,
                    self.incidents,
                    self.max_swap,
                    self.latest_event,
                    self.agent,
                ),
                strict=True,
            )
        )


def collect_dashboard_snapshot(
    *,
    config_loader: Callable[[], AppConfig] = load_config,
    swap_loader: Callable[[], SwapInfo] = get_swap_info,
    events_loader: Callable[[], list[dict[str, Any]]] | None = None,
    agent_loader: Callable[[], dict[str, Any]] = agent_status,
) -> DashboardSnapshot:
    """Collect display-ready status values for the lightweight Mac UI."""
    config = config_loader()
    swap = _load_swap_safely(swap_loader)
    events = events_loader() if events_loader else load_events(EVENTS_FILE, limit=200)
    summary = summarize_events(events)
    agent = agent_loader()

    return DashboardSnapshot(
        swap_used=_format_gib(swap.used_gib),
        swap_total=_format_gib(swap.total_gib),
        memory_free=_format_percent(swap.memory_free_percent),
        swap_source=swap.source,
        api_status="configured" if config.api_key else "missing",
        model=str(config.model),
        threshold=f"{config.swap_threshold_gib:g} GiB",
        events=str(summary["event_count"]),
        incidents=str(summary["incident_count"]),
        max_swap=f"{summary['max_swap_gib']} GiB",
        latest_event=str(summary["latest_timestamp"] or "n/a"),
        agent=_format_agent(agent),
    )


def run_ui() -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
    except ImportError as exc:  # pragma: no cover - depends on local Python build.
        raise RuntimeError("tkinter is required for the Mac UI. Install a Python build that includes Tk.") from exc

    class SwapKillerWindow:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("MacOS Swap Killer")
            self.root.geometry("760x620")
            self.root.minsize(660, 540)

            style = ttk.Style()
            if "aqua" in style.theme_names():
                style.theme_use("aqua")
            style.configure("Title.TLabel", font=("SF Pro Display", 22, "bold"))
            style.configure("Subtitle.TLabel", foreground="#5f6368")
            style.configure("Status.TLabel", font=("SF Pro Text", 12))

            self.status_vars: dict[str, tk.StringVar] = {}
            self._build(ttk, scrolledtext)
            self.refresh()

        def _build(self, ttk_module: Any, scrolledtext_module: Any) -> None:
            frame = ttk_module.Frame(self.root, padding=24)
            frame.pack(fill="both", expand=True)

            ttk_module.Label(frame, text="MacOS Swap Killer", style="Title.TLabel").pack(anchor="w")
            ttk_module.Label(
                frame,
                text="A small local dashboard for swap pressure, reports, and safe dry-run checks.",
                style="Subtitle.TLabel",
            ).pack(anchor="w", pady=(4, 18))

            status = ttk_module.LabelFrame(frame, text="Status", padding=14)
            status.pack(fill="x")
            for index, key in enumerate(STATUS_LABELS):
                var = self.status_vars[key] = tk.StringVar(value="...")
                ttk_module.Label(status, text=key, foreground="#5f6368").grid(
                    row=index // 2,
                    column=(index % 2) * 2,
                    sticky="w",
                    padx=(0, 8),
                    pady=5,
                )
                ttk_module.Label(status, textvariable=var, style="Status.TLabel").grid(
                    row=index // 2,
                    column=(index % 2) * 2 + 1,
                    sticky="w",
                    padx=(0, 28),
                    pady=5,
                )

            actions = ttk_module.Frame(frame)
            actions.pack(fill="x", pady=(18, 14))
            ttk_module.Button(actions, text="Refresh", command=self.refresh).pack(side="left", padx=(0, 8))
            ttk_module.Button(actions, text="Init Files", command=self.init_files).pack(side="left", padx=(0, 8))
            ttk_module.Button(actions, text="Dry-run Scan", command=self.dry_run_scan).pack(side="left", padx=(0, 8))
            ttk_module.Button(actions, text="Report", command=self.show_report).pack(side="left", padx=(0, 8))
            ttk_module.Button(actions, text="Open Config", command=lambda: self.open_path(CONFIG_DIR)).pack(
                side="left",
                padx=(0, 8),
            )
            ttk_module.Button(actions, text="Open Rules", command=lambda: self.open_path(RULES_FILE)).pack(side="left")

            self.output = scrolledtext_module.ScrolledText(frame, height=13, wrap="word", relief="solid", borderwidth=1)
            self.output.pack(fill="both", expand=True)
            self.output.insert(
                "end",
                "Ready. Dry-run Scan previews decisions only; automatic termination still requires the CLI --execute flag.\n",
            )
            self.output.configure(state="disabled")

            footer = ttk_module.Label(
                frame,
                text=f"Config: {CONFIG_FILE}   Log: {LOG_FILE}",
                foreground="#777777",
            )
            footer.pack(anchor="w", pady=(10, 0))

        def refresh(self) -> None:
            def job() -> DashboardSnapshot:
                return collect_dashboard_snapshot()

            self._run_background("Refresh", job, self._render_snapshot)

        def init_files(self) -> None:
            def job() -> str:
                written = ensure_user_files()
                if not written:
                    return "Config files already exist."
                return "Wrote:\n" + "\n".join(f"  {path}" for path in written)

            self._run_background("Init Files", job, self._append_result)

        def dry_run_scan(self) -> None:
            def job() -> str:
                loaded = load_config()
                logger = setup_logging(verbose=False)
                result = SwapKiller(loaded, logger=logger).run_once(dry_run=True, interactive=False)
                return result.model_dump_json(indent=2)

            self._run_background("Dry-run Scan", job, self._append_result)

        def show_report(self) -> None:
            events = load_events(EVENTS_FILE, limit=200)
            if not events:
                self._append_result("No event log found yet.")
                return
            self._append_result(render_summary(summarize_events(events)))

        def open_path(self, path: Path) -> None:
            target = path if path.exists() else path.parent
            try:
                subprocess.run(["open", str(target)], check=False)
            except OSError as exc:
                messagebox.showerror("Open failed", str(exc))

        def _run_background(self, title: str, job: Callable[[], Any], on_success: Callable[[Any], None]) -> None:
            self._append_result(f"$ {title} ...")

            def worker() -> None:
                try:
                    result = job()
                except Exception as exc:  # noqa: BLE001 - surface UI errors without crashing the window.
                    self.root.after(0, lambda: self._append_result(f"{title} failed: {exc}"))
                else:
                    self.root.after(0, lambda: on_success(result))

            threading.Thread(target=worker, daemon=True).start()

        def _render_snapshot(self, snapshot: DashboardSnapshot) -> None:
            for key, value in snapshot.rows():
                self.status_vars[key].set(value)
            self._append_result("Status refreshed.")

        def _append_result(self, text: str) -> None:
            self.output.configure(state="normal")
            self.output.insert("end", f"\n{text}\n")
            self.output.see("end")
            self.output.configure(state="disabled")

    root = tk.Tk()
    SwapKillerWindow(root)
    root.mainloop()


def _load_swap_safely(swap_loader: Callable[[], SwapInfo]) -> SwapInfo:
    try:
        return swap_loader()
    except Exception as exc:  # noqa: BLE001 - status UI should stay open if collection fails.
        return SwapInfo(source="unavailable", raw=str(exc))


def _format_gib(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f} GiB"


def _format_percent(value: int | None) -> str:
    return "n/a" if value is None else f"{value}%"


def _format_agent(agent: dict[str, Any]) -> str:
    if agent.get("loaded"):
        return "loaded"
    if agent.get("plist_exists"):
        return "installed"
    return "not installed"
