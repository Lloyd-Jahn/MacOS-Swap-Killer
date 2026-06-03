<p align="right">
  English | <a href="./README.zh-CN.md">简体中文</a>
</p>

<div align="center">
  <h1>MacOS Swap Killer</h1>
  <p><strong>A conservative, explainable, dry-run-first macOS swap pressure monitor.</strong></p>
  <p>
    Watch swap, memory pressure, and high-memory processes.
    Let the LLM advise, while local rules and hard safety checks keep final control.
  </p>
  <p>
    <a href="#features">Features</a> ·
    <a href="#quick-start">Quick Start</a> ·
    <a href="#mac-ui">Mac UI</a> ·
    <a href="#safety">Safety</a> ·
    <a href="#development">Development</a>
  </p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
    <img alt="Platform" src="https://img.shields.io/badge/Platform-macOS-111111?logo=apple&logoColor=white">
    <img alt="Mode" src="https://img.shields.io/badge/Default-dry--run-3fb950">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
  </p>
</div>

## Why

When macOS swap starts growing quickly, the whole machine can feel stuck. The hard part is knowing which process is safe to close without losing work.

MacOS Swap Killer is designed as a cautious local assistant:

- Observe swap, memory pressure, and swap growth trends.
- Collect high-memory process summaries with command-line redaction.
- Ask an OpenAI-compatible LLM for advice only.
- Let local policy, user rules, and app playbooks make the final decision.
- Stay in `--dry-run` by default. Real termination requires explicit `--execute`.

> [!IMPORTANT]
> v1 never sends `SIGKILL` automatically. Even in `--execute` mode, it only sends `SIGTERM` to low-risk processes that pass local hard safety checks.

## Features

- **Swap monitoring**: reads from `sysctl`, `top`, or `memory_pressure`.
- **Trend trigger**: detects fast swap growth before the absolute threshold is reached.
- **LLM-assisted classification**: supports OpenAI-style Chat Completions providers, with DeepSeek defaults.
- **Local hard safety**: protects system processes, root/system-owned processes, current shell context, and protected apps.
- **User rules**: configure protected, ask-confirm, and auto-terminate patterns in `rules.toml`.
- **App playbooks**: conservative behavior for browsers, VS Code, Jupyter, Node, Docker, local AI, chat, and notes apps.
- **Reports and notifications**: stores event logs, renders summaries, and sends macOS notifications when possible.
- **Launchd support**: install a user-level background agent, still dry-run by default.
- **Mac UI**: a small local status window for reports, dry-run scans, and config/rules access.

## Quick Start

```bash
python3 -m pip install -e ".[dev]"
macos-swap-killer init
macos-swap-killer doctor
macos-swap-killer once --threshold-gib 0 --dry-run
```

Config files are created under:

```text
~/Library/Application Support/MacOS Swap Killer/config.toml
~/Library/Application Support/MacOS Swap Killer/.env
~/Library/Application Support/MacOS Swap Killer/rules.toml
```

Default LLM environment values:

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

You can use any OpenAI-compatible provider that exposes a Chat Completions-style endpoint.

## Mac UI

The original project was CLI-only. This branch adds a lightweight local macOS window built with Python standard-library `tkinter`, avoiding Electron or large frontend dependencies.

Start it with:

```bash
macos-swap-killer ui
```

or:

```bash
macos-swap-killer-ui
```

The current UI can:

- Show swap used, memory free, API key status, model, event count, incident count, and launchd status.
- Initialize config files.
- Run one dry-run scan.
- Show the latest report.
- Open the config directory and rules file.

The UI is intentionally a status panel and safe operation entry point. It does not hide automatic cleanup behind a button; real termination still requires the CLI `--execute` flag.

## CLI

```bash
macos-swap-killer doctor
macos-swap-killer once --dry-run
macos-swap-killer once --dry-run --interactive
macos-swap-killer watch --dry-run
macos-swap-killer report
macos-swap-killer rules
```

Enable conservative real actions only when you mean it:

```bash
macos-swap-killer watch --execute
```

Install a user-level launchd agent:

```bash
macos-swap-killer install-agent
macos-swap-killer agent-status
macos-swap-killer uninstall-agent
```

Allow the background agent to send approved `SIGTERM` actions:

```bash
macos-swap-killer install-agent --execute
```

## User Rules

Create or inspect the local rules file:

```bash
macos-swap-killer rules
```

`rules.toml` supports:

- `protected.names`: never terminate, even after manual confirmation.
- `ask_confirm.names` / `ask_confirm.cmdline_contains`: suggest only, require interactive confirmation.
- `auto_terminate.names` / `auto_terminate.cmdline_contains`: still requires low-risk LLM advice and local hard safety checks.

Default rules protect `WeChat`, `QQ`, and `Notes`, and treat browsers, editors, Docker, Jupyter, and local AI services conservatively.

## Reports

```bash
macos-swap-killer report
macos-swap-killer report --json
macos-swap-killer report --raw
```

Logs and event files:

```text
~/Library/Logs/MacOS Swap Killer/swap-killer.log
~/Library/Application Support/MacOS Swap Killer/events.jsonl
~/Library/Application Support/MacOS Swap Killer/history.jsonl
```

## Safety

These processes are hard-protected in both local code and the LLM system prompt, and are never automatically terminated:

```text
WindowServer
kernel_task
launchd
loginwindow
Finder
Dock
SystemUIServer
```

The tool also locally vetoes root/system-owned processes, critical system paths, PID reuse, the current process, the parent shell, user-protected processes, malformed LLM responses, and uncertain LLM decisions.

## Development

```bash
python3 -m pip install -e ".[dev]"
pytest
```

Project layout:

```text
src/macos_swap_killer/
  cli.py            # Typer CLI
  ui.py             # lightweight Mac UI
  monitor.py        # incident orchestration
  policy.py         # local hard safety policy
  rules.py          # user rules
  playbooks.py      # app-specific behavior hints
  reporting.py      # event summaries
  launchd.py        # user agent install/status
tests/
```

## Roadmap

- Package the UI as a double-clickable `.app`.
- Add a README screenshot after running the UI on a real macOS desktop.
- Add UI settings and rules editing.
- Add more app playbooks.

## License

MIT
