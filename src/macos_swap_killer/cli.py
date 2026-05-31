from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path

import typer

from .config import CONFIG_FILE, EVENTS_FILE, ensure_user_files, load_config
from .logging_utils import setup_logging
from .monitor import SwapKiller
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
    typer.echo(f"API key: {'configured' if loaded.api_key else 'missing'}")
    typer.echo(f"Base URL: {loaded.base_url}")
    typer.echo(f"Model: {loaded.model}")
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Run one scan."""
    loaded = load_config(config)
    logger = setup_logging(verbose=verbose)
    result = SwapKiller(loaded, logger=logger).run_once(dry_run=dry_run, threshold_gib=threshold_gib)
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def watch(
    config: Path | None = typer.Option(None, "--config", help="Path to config.toml."),
    threshold_gib: float | None = typer.Option(None, "--threshold-gib", help="Override swap threshold."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview or execute allowed SIGTERM actions."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Run continuous foreground monitoring."""
    loaded = load_config(config)
    logger = setup_logging(verbose=verbose)
    try:
        SwapKiller(loaded, logger=logger).watch(dry_run=dry_run, threshold_gib=threshold_gib)
    except KeyboardInterrupt:
        logger.info("watch stopped by user")
        raise typer.Exit(code=0) from None


@app.command()
def report(limit: int = typer.Option(20, "--limit", "-n", help="Number of recent events to show.")) -> None:
    """Print recent structured events."""
    if not EVENTS_FILE.exists():
        typer.echo(f"No event log found: {EVENTS_FILE}")
        return

    lines = EVENTS_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            typer.echo(line)
            continue
        typer.echo(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
