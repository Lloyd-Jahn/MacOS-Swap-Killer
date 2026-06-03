<p align="right">
  <a href="./README.md">English</a> | 简体中文
</p>

<div align="center">
  <h1>MacOS Swap Killer</h1>
  <p><strong>一个保守、可解释、默认安全的 macOS swap 压力监控工具。</strong></p>
  <p>
    监控 swap、memory pressure 和高内存进程，让 LLM 只做分析顾问，
    最终由本地规则和硬安全策略决定是否可以处理。
  </p>
  <p>
    <a href="#功能">功能</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#mac-ui">Mac UI</a> ·
    <a href="#安全边界">安全边界</a> ·
    <a href="#开发">开发</a>
  </p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
    <img alt="Platform" src="https://img.shields.io/badge/Platform-macOS-111111?logo=apple&logoColor=white">
    <img alt="Mode" src="https://img.shields.io/badge/Default-dry--run-3fb950">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
  </p>
</div>

## 为什么

macOS 的 swap 一旦快速增长，电脑会突然变得很慢。真正麻烦的是：你通常不知道该关哪个进程，也不希望工具粗暴地把正在工作的 App 杀掉。

MacOS Swap Killer 的目标是做一个谨慎的本地助手：

- 先观察 swap、memory pressure 和增长趋势。
- 再收集高内存进程摘要，并对命令行做脱敏。
- LLM 只负责给建议，不拥有最终执行权。
- 本地硬安全策略、用户规则和 App playbook 拥有最终否决权。
- 默认永远是 `--dry-run`，只有显式 `--execute` 才可能发送 `SIGTERM`。

> [!IMPORTANT]
> v1 不会自动发送 `SIGKILL`。即使打开 `--execute`，也只会对通过本地安全检查、规则检查和低风险判断的进程发送 `SIGTERM`。

## 功能

- **Swap 监控**：读取 `sysctl`、`top` 或 `memory_pressure`，尽量保持可用。
- **趋势触发**：不仅看绝对阈值，也会在短时间 swap 快速增长时触发 incident。
- **LLM 辅助判断**：兼容 OpenAI-style Chat Completions 服务，默认配置 DeepSeek。
- **本地安全策略**：系统进程、root/system 进程、当前 shell、受保护 App 等会被硬保护。
- **用户规则**：通过 `rules.toml` 定义永远保护、需要确认、可自动处理的进程模式。
- **App playbook**：对浏览器、VS Code、Jupyter、Node、Docker、本地 AI、聊天和笔记类 App 更保守。
- **报告与通知**：记录事件、生成摘要报告，并尝试发送 macOS Notification Center 通知。
- **后台运行**：支持安装用户级 launchd agent，默认仍是 dry-run。
- **Mac UI**：提供一个轻量的本地状态窗口，用于查看状态、报告和执行 dry-run 扫描。

## 快速开始

```bash
python3 -m pip install -e ".[dev]"
macos-swap-killer init
macos-swap-killer doctor
macos-swap-killer once --threshold-gib 0 --dry-run
```

配置文件会写入：

```text
~/Library/Application Support/MacOS Swap Killer/config.toml
~/Library/Application Support/MacOS Swap Killer/.env
~/Library/Application Support/MacOS Swap Killer/rules.toml
```

默认 LLM 配置：

```text
MSK_API_KEY=your_api_key_here
MSK_BASE_URL=https://api.deepseek.com
MSK_MODEL=deepseek-v4-flash
```

也可以换成任何兼容 Chat Completions 的 OpenAI-style 服务。

## Mac UI

这个项目原本是纯 CLI 工具，没有图形界面。本分支新增了一个轻量的 macOS 本地窗口，基于 Python 标准库的 `tkinter`，不引入 Electron 或大型前端依赖。

启动方式：

```bash
macos-swap-killer ui
```

或者：

```bash
macos-swap-killer-ui
```

当前 UI 提供：

- 查看 swap used、memory free、API key、model、事件数量、incident 数量和 launchd 状态。
- 一键初始化配置文件。
- 执行一次 dry-run 扫描。
- 查看最近报告。
- 打开配置目录和规则文件。

UI 的定位是“状态面板 + 安全操作入口”。它不会提供隐藏的自动清理按钮；真正执行清理仍需要在 CLI 里显式使用 `--execute`。

## CLI

```bash
macos-swap-killer doctor
macos-swap-killer once --dry-run
macos-swap-killer once --dry-run --interactive
macos-swap-killer watch --dry-run
macos-swap-killer report
macos-swap-killer rules
```

允许保守自动处理时才使用：

```bash
macos-swap-killer watch --execute
```

安装用户级 launchd agent：

```bash
macos-swap-killer install-agent
macos-swap-killer agent-status
macos-swap-killer uninstall-agent
```

如果确实要让后台 agent 执行允许的 `SIGTERM`：

```bash
macos-swap-killer install-agent --execute
```

## 用户规则

创建或查看规则文件：

```bash
macos-swap-killer rules
```

`rules.toml` 支持三类规则：

- `protected.names`：永远保护，即使手动确认也不终止。
- `ask_confirm.names` / `ask_confirm.cmdline_contains`：只建议，必须交互确认。
- `auto_terminate.names` / `auto_terminate.cmdline_contains`：仍需 LLM 低风险判断和本地硬安全检查通过，才可能自动 `SIGTERM`。

默认规则保护 `WeChat`、`QQ`、`Notes`，并对浏览器、编辑器、Docker、Jupyter、本地 AI 服务采取更保守的确认策略。

## 报告

```bash
macos-swap-killer report
macos-swap-killer report --json
macos-swap-killer report --raw
```

日志和事件文件：

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

工具还会本地否决 root/system 用户进程、关键系统路径进程、PID 复用、当前进程、父 shell、用户规则保护的进程，以及 LLM 输出不确定或格式错误的情况。

## 开发

```bash
python3 -m pip install -e ".[dev]"
pytest
```

项目结构：

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

- 打包成可双击启动的 `.app`。
- 给 README 增加真实 UI 截图。
- 给 UI 增加设置页和规则编辑器。
- 增加更多 App playbook。

## License

MIT
