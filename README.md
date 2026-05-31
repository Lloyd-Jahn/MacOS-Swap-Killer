# MacOS Swap Killer

<details open>
<summary>中文</summary>

## 简介

MacOS Swap Killer 是一个保守的 Python 终端工具，用于持续监控 macOS 的 swap、memory pressure 和高内存进程。当 swap 过高或短时间快速增长时，它会收集进程摘要，脱敏后交给 OpenAI-compatible LLM 判断，再由本地安全策略、用户规则和 App playbook 决定是否允许处理。

LLM 只是顾问，本地策略拥有最终否决权。默认是 `--dry-run`，不会真的杀进程；只有显式传入 `--execute` 时，才会对通过本地安全检查的低风险进程发送 `SIGTERM`。v1 不会自动发送 `SIGKILL`。

## 安装

```bash
python3 -m pip install -e ".[dev]"
```

## 配置

```bash
macos-swap-killer init
```

配置文件：

```text
~/Library/Application Support/MacOS Swap Killer/config.toml
~/Library/Application Support/MacOS Swap Killer/.env
~/Library/Application Support/MacOS Swap Killer/rules.toml
```

DeepSeek V4 Flash 默认配置：

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

也可以换成任何 OpenAI-compatible 服务，只要保留 Chat Completions 兼容接口。

## 使用

检查本机依赖、配置、规则和 swap 采集能力：

```bash
macos-swap-killer doctor
```

不实际终止进程，做一次测试扫描：

```bash
macos-swap-killer once --threshold-gib 0 --dry-run
```

允许终端交互确认：

```bash
macos-swap-killer once --threshold-gib 0 --dry-run --interactive
```

前台持续监控：

```bash
macos-swap-killer watch --dry-run
```

允许保守自动清理：

```bash
macos-swap-killer watch --execute
```

安装用户级 launchd 后台服务，默认仍是 dry-run：

```bash
macos-swap-killer install-agent
macos-swap-killer agent-status
macos-swap-killer uninstall-agent
```

如果确实要让 launchd 后台执行允许的 `SIGTERM`：

```bash
macos-swap-killer install-agent --execute
```

## 用户规则

创建或查看规则文件：

```bash
macos-swap-killer rules
```

`rules.toml` 支持：

- `protected.names`：永远保护，即使手动确认也不终止。
- `ask_confirm.names` / `ask_confirm.cmdline_contains`：只建议，必须交互确认。
- `auto_terminate.names` / `auto_terminate.cmdline_contains`：仍需 LLM 低风险判断和本地硬安全检查通过，才可能自动 `SIGTERM`。

默认规则保护 `WeChat`、`QQ`、`Notes`，并对浏览器、编辑器、Docker、Jupyter、本地 AI 服务采取更保守的确认策略。

## 趋势触发

除了 `swap_threshold_gib = 10`，工具还会记录最近窗口内的 swap 样本。默认当 10 分钟内 swap 增长超过 `2 GiB` 时，也会触发一次 incident。这样可以在 swap 还没到 10G、但正在快速恶化时提前提醒。

## App Playbook

内置 playbook 会区分常见场景：

- Chrome/Edge/Safari：主 App 保护，renderer/helper 可低风险处理。
- VS Code：主 App 保护，extension host 默认确认，renderer/helper 可低风险处理。
- Python/Jupyter：notebook kernel 默认确认，测试进程可低风险处理。
- Node：测试和构建 worker 可低风险处理，服务类默认确认。
- Docker、本地 AI、聊天和笔记类 App 默认更保守。

## 报告和通知

事件发生时会尝试发送 macOS Notification Center 通知。

查看摘要报告：

```bash
macos-swap-killer report
macos-swap-killer report --json
macos-swap-killer report --raw
```

日志：

```text
~/Library/Logs/MacOS Swap Killer/swap-killer.log
~/Library/Application Support/MacOS Swap Killer/events.jsonl
~/Library/Application Support/MacOS Swap Killer/history.jsonl
```

## 安全边界

以下进程在本地代码和 LLM system prompt 中都被硬保护，永远不会被自动终止：

```text
WindowServer
kernel_task
launchd
loginwindow
Finder
Dock
SystemUIServer
```

工具还会本地否决 root/system 用户进程、关键系统路径进程、PID 复用、当前进程、父 shell、受用户规则保护的进程，以及 LLM 输出不确定或格式错误的情况。

</details>

<details>
<summary>English</summary>

## Overview

MacOS Swap Killer is a conservative Python terminal tool for monitoring macOS swap, memory pressure, and high-memory processes. When swap is high or growing quickly, it collects process summaries, redacts sensitive data, asks an OpenAI-compatible LLM for classification, and then lets local safety policy, user rules, and app-specific playbooks make the final decision.

The LLM is advisory only. Local policy can always veto. The default mode is `--dry-run`, so no process is terminated unless you explicitly pass `--execute`. v1 never sends `SIGKILL` automatically.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Configure

```bash
macos-swap-killer init
```

Config files:

```text
~/Library/Application Support/MacOS Swap Killer/config.toml
~/Library/Application Support/MacOS Swap Killer/.env
~/Library/Application Support/MacOS Swap Killer/rules.toml
```

Default DeepSeek V4 Flash config:

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

You can use any OpenAI-compatible provider as long as it supports a Chat Completions-compatible endpoint.

## Usage

Check local dependencies, config, rules, and swap visibility:

```bash
macos-swap-killer doctor
```

Run one test scan without terminating anything:

```bash
macos-swap-killer once --threshold-gib 0 --dry-run
```

Enable terminal confirmation for `ASK_CONFIRM` decisions:

```bash
macos-swap-killer once --threshold-gib 0 --dry-run --interactive
```

Run foreground monitoring:

```bash
macos-swap-killer watch --dry-run
```

Allow conservative automatic cleanup:

```bash
macos-swap-killer watch --execute
```

Install a user launchd agent. It runs in dry-run mode by default:

```bash
macos-swap-killer install-agent
macos-swap-killer agent-status
macos-swap-killer uninstall-agent
```

To allow the launchd agent to send approved `SIGTERM` actions:

```bash
macos-swap-killer install-agent --execute
```

## User Rules

Create or show the local rules file:

```bash
macos-swap-killer rules
```

`rules.toml` supports:

- `protected.names`: never terminate, even after manual confirmation.
- `ask_confirm.names` / `ask_confirm.cmdline_contains`: suggest only, require interactive confirmation.
- `auto_terminate.names` / `auto_terminate.cmdline_contains`: still requires a low-risk LLM decision and all hard local checks.

Default rules protect `WeChat`, `QQ`, and `Notes`, and handle browsers, editors, Docker, Jupyter, and local AI services conservatively.

## Trend Trigger

In addition to `swap_threshold_gib = 10`, the tool records recent swap samples. By default, if swap grows by more than `2 GiB` within 10 minutes, it triggers an incident before the absolute threshold is reached.

## App Playbooks

Built-in playbooks distinguish common workloads:

- Chrome/Edge/Safari: protect the main app; renderer/helper processes may be low-risk.
- VS Code: protect the main app; extension hosts require confirmation; renderer/helper processes may be low-risk.
- Python/Jupyter: notebook kernels require confirmation; test workers may be low-risk.
- Node: test/build workers may be low-risk; service-like processes require confirmation.
- Docker, local AI, chat, and notes apps are handled conservatively.

## Reports And Notifications

Incidents attempt to send macOS Notification Center alerts.

Show summary reports:

```bash
macos-swap-killer report
macos-swap-killer report --json
macos-swap-killer report --raw
```

Logs:

```text
~/Library/Logs/MacOS Swap Killer/swap-killer.log
~/Library/Application Support/MacOS Swap Killer/events.jsonl
~/Library/Application Support/MacOS Swap Killer/history.jsonl
```

## Safety

The following processes are hard-protected in both local code and the LLM system prompt. They are never automatically terminated:

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

</details>
