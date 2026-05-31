from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path

import typer

from .config import CONFIG_FILE, EVENTS_FILE, LAUNCH_AGENT_FILE, RULES_FILE, ensure_user_files, load_config
from .launchd import agent_status, install_agent, uninstall_agent
from .logging_utils import setup_logging
from .models import LLMDecision, ProcessInfo
from .monitor import SwapKiller
from .reporting import load_events, render_summary, summarize_events
from .rules import ensure_rules_file
from .swap import get_swap_info


app = typer.Typer(help="Conservative LLM-assisted macOS swap pressure monitor.")


@app.command("init")
def init_command(force: bool = typer.Option(False, "--force", help="Overwrite existing config files.")) -> None:
    """Create config and env files under Library/Application Support."""
    written = ensure_user_files(force=force)
    if not written:
        typer.echo("Config files already exist.")
        typer.echo(f"Config: {CONFIG_FILE}")
        return
    typer.echo("Wrote:")
    for path in written:
        typer.echo(f"  {path}")


@app.command()
def doctor(config: Path | None = typer.Option(None, "--config", help="Path to config.toml.")) -> None:
    """Check local dependencies, config, and swap visibility."""
    loaded = load_config(config)
    swap = get_swap_info()
    commands = ["sysctl", "top", "memory_pressure"]

    typer.echo(f"Platform: {platform.platform()}")
    typer.echo(f"Config: {loaded.config_path} ({'exists' if loaded.config_path.exists() else 'missing'})")
    typer.echo(f"Rules: {loaded.rules_path} ({'exists' if loaded.rules_path.exists() else 'missing; built-in defaults active'})")
    typer.echo(f"History: {loaded.history_path}")
    typer.echo(f"API key: {'configured' if loaded.api_key else 'missing'}")
    typer.echo(f"Base URL: {loaded.base_url}")
    typer.echo(f"Model: {loaded.model}")
    typer.echo(f"Trend trigger: {'enabled' if loaded.enable_trend_trigger else 'disabled'}")
    typer.echo(f"Notifications: {'enabled' if loaded.notifications_enabled else 'disabled'}")
    typer.echo(f"Swap source: {swap.source}")
    if swap.used_gib is not None:
        typer.echo(f"Swap used: {swap.used_gib:.2f} GiB")
    else:
        typer.echo("Swap used: unavailable")
    for command in commands:
        typer.echo(f"{command}: {shutil.which(command) or 'missing'}")


@app.command()
def once(
    config: Path | None = typer.Option(None, "--config", help="Path to config.toml."),
    threshold_gib: float | None = typer.Option(None, "--threshold-gib", help="Override swap threshold."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview or execute allowed SIGTERM actions."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt for ASK_CONFIRM decisions in the terminal."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Run one scan."""
    loaded = load_config(config)
    logger = setup_logging(verbose=verbose)
    result = SwapKiller(loaded, logger=logger).run_once(
        dry_run=dry_run,
        threshold_gib=threshold_gib,
        interactive=interactive,
        confirm_callback=_confirm_process if interactive else None,
    )
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def watch(
    config: Path | None = typer.Option(None, "--config", help="Path to config.toml."),
    threshold_gib: float | None = typer.Option(None, "--threshold-gib", help="Override swap threshold."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview or execute allowed SIGTERM actions."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt for ASK_CONFIRM decisions in the terminal."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Run continuous foreground monitoring."""
    loaded = load_config(config)
    logger = setup_logging(verbose=verbose)
    try:
        SwapKiller(loaded, logger=logger).watch(
            dry_run=dry_run,
            threshold_gib=threshold_gib,
            interactive=interactive,
            confirm_callback=_confirm_process if interactive else None,
        )
    except KeyboardInterrupt:
        logger.info("watch stopped by user")
        raise typer.Exit(code=0) from None


@app.command()
def report(
    limit: int = typer.Option(200, "--limit", "-n", help="Number of recent events to analyze."),
    raw: bool = typer.Option(False, "--raw", help="Print raw JSON events instead of a summary."),
    json_output: bool = typer.Option(False, "--json", help="Print summary as JSON."),
) -> None:
    """Show recent actions, vetoes, decisions, and swap peaks."""
    if not EVENTS_FILE.exists():
        typer.echo(f"No event log found: {EVENTS_FILE}")
        return

    events = load_events(EVENTS_FILE, limit=limit)
    if raw:
        for event in events:
            typer.echo(json.dumps(event, ensure_ascii=False, indent=2))
        return

    summary = summarize_events(events)
    if json_output:
        typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        typer.echo(render_summary(summary))


@app.command("rules")
def rules_command(force: bool = typer.Option(False, "--force", help="Overwrite existing rules.toml.")) -> None:
    """Create or show the local user rules file."""
    path = ensure_rules_file(force=force, path=RULES_FILE)
    typer.echo(f"Rules file: {path}")


@app.command("install-agent")
def install_agent_command(
    execute: bool = typer.Option(False, "--execute", help="Install the launchd agent in execute mode instead of dry-run."),
    load: bool = typer.Option(True, "--load/--no-load", help="Load the agent immediately with launchctl."),
) -> None:
    """Install a user launchd agent for foreground-free monitoring."""
    path = install_agent(execute=execute, load=load)
    mode = "execute" if execute else "dry-run"
    typer.echo(f"Installed {mode} launchd agent: {path}")


@app.command("uninstall-agent")
def uninstall_agent_command(
    unload: bool = typer.Option(True, "--unload/--no-unload", help="Unload the agent with launchctl before removing it."),
) -> None:
    """Unload and remove the user launchd agent."""
    removed = uninstall_agent(unload=unload)
    typer.echo(f"Removed {LAUNCH_AGENT_FILE}: {removed}")


@app.command("agent-status")
def agent_status_command() -> None:
    """Show launchd agent installation and loaded state."""
    typer.echo(json.dumps(agent_status(), ensure_ascii=False, indent=2))


def _confirm_process(process: ProcessInfo, decision: LLMDecision, reason: str) -> bool:
    typer.echo("")
    typer.echo(f"PID: {process.pid}")
    typer.echo(f"Name: {process.name}")
    typer.echo(f"RSS: {process.rss_mb:.1f} MiB")
    typer.echo(f"LLM: {decision.action.value} / {decision.risk.value} / {decision.reason}")
    typer.echo(f"Local reason: {reason}")
    return typer.confirm("Send SIGTERM to this process?")


if __name__ == "__main__":
    app()
