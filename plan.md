# MacOS Swap Killer Implementation Plan

## Summary

Build `MacOS Swap Killer` as a Python 3.11+ terminal CLI that continuously watches macOS swap usage. When swap exceeds `10 GiB`, the tool collects a process snapshot, sends a privacy-redacted summary to an OpenAI-compatible LLM, and only terminates low-risk, user-owned helper/background processes after local safety checks pass.

The LLM is advisory only. Final execution is gated by hardcoded local policy. The tool must never automatically kill core macOS processes, including `WindowServer`, `kernel_task`, `launchd`, `loginwindow`, `Finder`, `Dock`, and `SystemUIServer`.

Actual termination is opt-in in v1: commands default to `--dry-run`; users must pass `--execute` to send `SIGTERM`.

## Key Changes

- Python package with CLI commands:
  - `macos-swap-killer init`: create user config and `.env` template.
  - `macos-swap-killer watch`: foreground continuous monitor.
  - `macos-swap-killer once`: one scan, useful for testing.
  - `macos-swap-killer doctor`: verify macOS commands, config, and API key.
  - `macos-swap-killer report`: show recent actions and skipped decisions.
- Default config:
  - `swap_threshold_gib = 10`
  - `poll_interval_sec = 60`
  - `cooldown_sec = 900`
  - `max_auto_terminations_per_incident = 2`
  - LLM API: OpenAI-compatible `base_url`, `model`, and manually filled `MSK_API_KEY`.
- Main modules:
  - `cli.py`: Typer CLI entrypoint.
  - `monitor.py`: swap polling and incident lifecycle.
  - `processes.py`: process snapshot via `psutil`.
  - `privacy.py`: command-line/path/token redaction before LLM calls.
  - `llm.py`: OpenAI-compatible JSON call and response validation.
  - `policy.py`: hard safety rules and auto-eligible classification.
  - `actuator.py`: PID revalidation, `SIGTERM`, post-action checks.
  - `models.py`: Pydantic request/response schemas.

## Safety Design

- Hardcode `NEVER_KILL_NAMES` in local code and repeat it in the LLM system prompt:

  ```python
  NEVER_KILL_NAMES = {
      "WindowServer",
      "kernel_task",
      "launchd",
      "loginwindow",
      "Finder",
      "Dock",
      "SystemUIServer",
  }
  ```

- Local policy vetoes termination when:
  - Process name matches `NEVER_KILL_NAMES`.
  - PID is current process, parent process, PID `0`, or PID `1`.
  - PID was reused since the process snapshot.
  - Process is owned by `root` or a system user.
  - Process path is under critical system locations such as `/System/Library`, `/usr/libexec`, or `/sbin`.
  - Process appears to be a main GUI app process.
  - LLM response is invalid, missing, uncertain, or asks to kill a protected process.
- Auto termination is allowed only for low-risk user-owned child/helper processes, such as browser renderers, Electron helpers, VS Code helpers, build/test workers, or obvious cache/background workers.
- Main GUI apps like Chrome, Edge, VS Code, WeChat, Finder, etc. are not auto-killed.
- Execution sequence:
  - Send `SIGTERM`.
  - Wait 5-10 seconds.
  - Recheck process state.
  - Do not auto-send `SIGKILL` in v1.

## LLM Interface

- Send only redacted process summaries by default:
  - PID, PPID, user, process name, RSS, memory percent, executable category, parent name, age, and redacted command line.
  - Redact API keys, tokens, long file paths, home directory, project names, URLs with credentials, and env-like arguments.
- LLM request includes:
  - Current swap usage.
  - Memory pressure summary.
  - Candidate processes.
  - Hard safety rules.
  - Explicit instruction: if uncertain, return `IGNORE` or `ASK_CONFIRM`, never `TERMINATE`.
- LLM response schema:

  ```json
  {
    "overall_risk": "low|medium|high",
    "decisions": [
      {
        "pid": 12345,
        "process_name": "Code Helper (Renderer)",
        "action": "TERMINATE|ASK_CONFIRM|IGNORE",
        "risk": "low|medium|high",
        "reason": "short explanation",
        "expected_memory_mb": 1024
      }
    ]
  }
  ```

## Test Plan

- Unit tests:
  - Parse `sysctl vm.swapusage`, `memory_pressure`, and `top` fixtures.
  - Verify `NEVER_KILL_NAMES` cannot be terminated even if LLM says `TERMINATE`.
  - Verify root/system/main-GUI processes are vetoed.
  - Verify PID reuse detection blocks action.
  - Verify redaction removes tokens, home paths, and credentials.
  - Verify malformed LLM JSON results in no action.
- Integration smoke tests:
  - Fake process provider plus fake LLM response.
  - `once --dry-run --threshold-gib 0` triggers incident without killing.
  - Simulated LLM recommending protected process kill is logged as veto.
  - Simulated low-risk helper process receives `SIGTERM` only when `--execute` is enabled.

## Assumptions

- First version is a foreground terminal tool, not a launchd background service.
- User manually fills API credentials in `.env` or shell env:
  - `MSK_API_KEY`
  - `MSK_BASE_URL`
  - `MSK_MODEL`
- Default LLM API is OpenAI-compatible.
- Default privacy mode is redacted process summaries.
- `purge` is not used in v1 because killing the right user process is safer and more explainable than forcing global cache purge.
