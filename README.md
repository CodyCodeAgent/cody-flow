# CodyFlow

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-115%20passed-brightgreen.svg)](#testing)

**AI workflow orchestration framework with a visual node-based flow editor.**

CodyFlow turns repetitive AI interaction patterns — "write code, review, fix, review again" — into configurable, auto-executing workflows. Design your flow visually in the browser, hit run, and watch AI work through it step by step.

[English](#quick-start) | [中文](#中文说明)

---

## Quick Start

```bash
# Install
pip install codyflow

# Launch the Web UI
codyflow
# or: python -m codyflow

# Open http://127.0.0.1:8080 in your browser
```

Then in the browser:

1. **Settings** — Configure your API key and default runner
2. **Editor** — Drag nodes onto the canvas, connect them with edges
3. **Run** — Enter a working directory and task description, click start
4. **Watch** — Real-time node execution status via WebSocket

## Core Concepts

### Nodes

Each node represents one AI execution step. Six built-in types:

| Type | Purpose | Behavior |
|------|---------|----------|
| **discuss** | Requirements discussion | Multi-turn interactive conversation with user |
| **learn** | Project study | AI browses project code, outputs knowledge summary |
| **code** | Write code | Writes/modifies code based on upstream context |
| **reflect** | Review & inspect | Checks code changes against requirements |
| **judge** | Route decision | Decides flow direction (fix / pass) based on review |
| **custom** | User-defined | Any custom behavior via prompt |

### Runners

Runners are the underlying AI engines that execute node tasks:

| Runner | Engine | Install |
|--------|--------|---------|
| **cody** | Cody SDK (`cody-ai`) | `pip install codyflow[cody]` |
| **claude** | Claude Agent SDK | `pip install codyflow[claude]` |

Runners can be set globally or overridden per node.

### Edges & Conditional Routing

Nodes connect via edges. Edges can carry conditions for branching:

```
discuss -> learn -> code -> reflect -> judge
                     ^                   |
                     |  needs_fix        | passed
                     +-------------------+---> END
```

The judge node uses AI to decide routing — no hardcoded rules.

### Context Passing

Nodes pass context through the file system (`.codyflow/context/`):

- Each node sees the full flow **panorama** (goal, node map, available files)
- Nodes **decide themselves** which context files to read
- Code nodes **directly modify** project source files
- Context directory holds only summary reports

## Web UI Features

- **Visual flow editor** — Drag-and-drop nodes, draw edges, set conditions
- **Flow management** — Create / save / open / delete (SQLite storage)
- **YAML import/export** — Share flow definitions with others
- **Built-in templates** — One-click standard workflow templates
- **Real-time execution** — WebSocket bidirectional communication with live canvas highlighting
- **Interactive nodes** — Multi-turn chat modal for discuss nodes
- **Context file browser** — View node output reports
- **Execution logs** — Structured JSONL logs + per-node prompt/output archives
- **Settings page** — API key, model, runner config, environment check
- **Canvas zoom/pan** — Scroll to zoom, Ctrl+drag to pan

## Architecture

```
+----------------------------------------------------------+
|              Web UI (Vue 3 CDN + FastAPI)                 |
|      Visual Editor | Real-time Execution | Settings      |
+----------------------------------------------------------+
|         REST API + WebSocket + SSE (FastAPI)              |
|   Flow CRUD | Run Control | Context Browser | Config     |
+----------------------------------------------------------+
|              Flow Engine (LangGraph)                      |
|   StateGraph | Conditional Routing | Loop Control        |
|   SQLite Checkpoint for State Persistence & Resume       |
+--------------------------+-------------------------------+
|     Node System          |       Runner System           |
|  +--------------------+  |  +-------------------------+  |
|  | discuss (interact) |  |  | Runner interface (ABC)  |  |
|  | learn              |  |  +-------------------------+  |
|  | code               |  |  | CodyRunner (cody-ai)   |  |
|  | reflect            |  |  | ClaudeRunner (claude)   |  |
|  | judge (routing)    |  |  | Extensible ...          |  |
|  | custom             |  |  +-------------------------+  |
|  +--------------------+  |                               |
+--------------------------+-------------------------------+
|              Storage (SQLite)                             |
|   Flow Definitions | Execution State | Config            |
+----------------------------------------------------------+
```

## Development

```bash
# Clone
git clone https://github.com/codycodeagent/cody-flow.git
cd cody-flow

# Install in dev mode
pip install -e ".[dev]"

# Run tests
make test

# Lint
make lint

# Format
make fmt
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_nodes.py
```

Current test coverage: **115 tests** across 7 test suites covering nodes, engine, storage, validation, judge parsing, logger, and API helpers.

## License

[MIT](LICENSE)

---

## 中文说明

CodyFlow 是一个**可视化节点式 AI 工作流编排框架**。

在日常使用 AI 编程 Agent 时，我们经常重复"写代码 -> 检查 -> 修改 -> 再检查"的循环。CodyFlow 把这种机械的人工驱动模式，变成可配置、可自动执行的工作流。

### 核心特性

- **可视化编辑器** — 在浏览器中拖拽节点、连线，设计 AI 工作流
- **6 种内置节点** — 讨论、学习、写代码、反思、判断、自定义
- **条件路由 + 循环** — 判断节点通过 AI 分析决定流程走向
- **WebSocket 实时通信** — 双向通信，支持交互式节点的多轮对话
- **断点恢复** — 基于 LangGraph Checkpoint，支持中断后继续执行
- **YAML 导入/导出** — 方便分享和复用工作流定义
- **多 Runner 支持** — Cody SDK 和 Claude Agent SDK，可按节点指定

### 设计原则

1. **节点平等** — 自定义节点和系统节点使用相同机制
2. **AI 有全貌** — 每个节点看到整个 flow 的目标、节点地图和可用文件
3. **直接操作** — 写代码节点直接修改项目源码，context 只放报告
4. **会话独立** — 每个节点独立启动，通过文件传递上下文，避免 token 膨胀
5. **讨论需要人** — 讨论节点默认开启交互模式，全程用户参与
6. **可恢复** — 基于 LangGraph Checkpoint，支持断点恢复
