# MacOS Swap Killer

<details open>
<summary>中文</summary>

## 简介

MacOS Swap Killer 是一个保守的 Python 终端工具，用于持续监控 macOS 的 swap 使用量。当 swap 超过阈值时，它会收集高内存进程摘要，脱敏后交给 OpenAI-compatible LLM 判断，再由本地安全策略决定是否允许终止进程。

LLM 只是顾问，本地策略拥有最终否决权。默认是 `--dry-run`，不会真的杀进程；只有显式传入 `--execute` 时，才会对通过本地安全检查的低风险进程发送 `SIGTERM`。

## 安装

```bash
python3 -m pip install -e ".[dev]"
```

## 配置

```bash
macos-swap-killer init
```

然后编辑：

```text
~/Library/Application Support/MacOS Swap Killer/.env
```

DeepSeek V4 Flash 默认配置：

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

也可以换成任何 OpenAI-compatible 服务，只要保留 Chat Completions 兼容接口。

## 使用

检查本机依赖、配置和 swap 采集能力：

```bash
macos-swap-killer doctor
```

不实际终止进程，做一次测试扫描：

```bash
macos-swap-killer once --threshold-gib 0 --dry-run
```

前台持续监控，仍然不终止进程：

```bash
macos-swap-killer watch --dry-run
```

允许保守自动清理：

```bash
macos-swap-killer watch --execute
```

v1 只发送 `SIGTERM`，不会自动发送 `SIGKILL`。

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

工具还会本地否决 root/system 用户进程、关键系统路径进程、PID 复用、当前进程、父 shell、主 GUI App 进程，以及 LLM 输出不确定或格式错误的情况。

## 日志

普通日志：

```text
~/Library/Logs/MacOS Swap Killer/swap-killer.log
```

结构化事件：

```text
~/Library/Application Support/MacOS Swap Killer/events.jsonl
```

</details>

<details>
<summary>English</summary>

## Overview

MacOS Swap Killer is a conservative Python terminal tool for monitoring macOS swap usage. When swap crosses a threshold, it collects high-memory process summaries, redacts sensitive data, asks an OpenAI-compatible LLM for classification, and then lets local safety policy make the final termination decision.

The LLM is advisory only. Local policy can always veto. The default mode is `--dry-run`, so no process is terminated unless you explicitly pass `--execute`.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Configure

```bash
macos-swap-killer init
```

Then edit:

```text
~/Library/Application Support/MacOS Swap Killer/.env
```

Default DeepSeek V4 Flash config:

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

You can use any OpenAI-compatible provider as long as it supports a Chat Completions-compatible endpoint.

## Usage

Check local dependencies, config, and swap visibility:

```bash
macos-swap-killer doctor
```

Run one test scan without terminating anything:

```bash
macos-swap-killer once --threshold-gib 0 --dry-run
```

Run foreground monitoring without terminating anything:

```bash
macos-swap-killer watch --dry-run
```

Allow conservative automatic cleanup:

```bash
macos-swap-killer watch --execute
```

v1 sends `SIGTERM` only. It never sends `SIGKILL` automatically.

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

The tool also locally vetoes root/system-owned processes, critical system paths, PID reuse, the current process, the parent shell, main GUI app processes, malformed LLM responses, and uncertain LLM decisions.

## Logs

Human-readable log:

```text
~/Library/Logs/MacOS Swap Killer/swap-killer.log
```

Structured event log:

```text
~/Library/Application Support/MacOS Swap Killer/events.jsonl
```

</details>
