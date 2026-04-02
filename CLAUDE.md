# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

CodyFlow is an AI workflow orchestration framework. Users design flows visually in a browser-based editor; flows execute as LangGraph state graphs with real-time WebSocket updates. The core pattern is: Visual editor → FastAPI backend → LangGraph engine → Runner (Cody/Claude SDK) → AI execution.

## Commands

```bash
# Install
pip install -e ".[dev]"       # Dev install with all dependencies

# Run
python -m codyflow             # Start web server at http://127.0.0.1:8080
codyflow --port 3000           # Custom port

# Test
pytest -v                      # Run all 115 tests
pytest tests/test_nodes.py     # Single test file
pytest tests/test_nodes.py::TestClassName::test_method  # Single test

# Lint/Format
ruff check codyflow/ tests/    # Lint
ruff format codyflow/ tests/   # Format
ruff check --fix codyflow/ tests/  # Auto-fix

# Combined
make check                     # lint + tests
```

## Architecture

```
Web UI (Vue 3 CDN, no build step)
    ↓ REST / WebSocket
FastAPI (codyflow/web/api.py)
    ↓
Flow Engine: LangGraph StateGraph (codyflow/engine/flow.py)
    ↓
Node System (codyflow/nodes/)   →   Runner System (codyflow/runners/)
    ↓                                   ↓
SQLite state persistence         Cody SDK / Claude Agent SDK
```

**Data flow between nodes**: nodes communicate via `.codyflow/context/` filesystem files (not in-memory). Each node receives the full flow panorama — goal, node map, available context files — and writes its output as a new context file.

**State graph**: `FlowState` (TypedDict in `nodes/base.py`) is the shared LangGraph state. `engine/flow.py` builds the `StateGraph` from a flow definition and handles conditional routing.

## Key Extension Points

**Adding a node type** — subclass `SimpleNode` in `nodes/builtin.py`, override `build_prompt()`, register with `register_node_type("name", MyNode)` in `nodes/registry.py`.

**Adding a runner** — subclass `Runner` (ABC in `runners/base.py`), implement `async run(prompt, session_id, config)`, register with `register_runner("name", MyRunner)` in `runners/registry.py`.

## Node Types (6 built-in)

| Node | Purpose |
|------|---------|
| `discuss` | Interactive multi-turn conversation; supports session-based history |
| `learn` | Studies project code, produces knowledge summary |
| `code` | Writes/modifies source files based on upstream context |
| `reflect` | Reviews work, surfaces issues |
| `judge` | AI-based routing decision; parses "ROUTE:", "Decision:", or keyword detection |
| `custom` | User-defined arbitrary prompt |

**Judge routing**: the `judge` node output is parsed in `nodes/builtin.py` — it looks for `ROUTE: <target>`, `Decision: <target>`, or keyword matching against node names. No hardcoded rules.

## Storage

- SQLite at `~/.codyflow/codyflow.db` (production) or in-memory (tests)
- `storage.py` handles flow CRUD and YAML import/export
- `engine/logger.py` writes execution logs as JSONL + per-node archive files

## Frontend

Single-page app in `codyflow/web/static/`. Vue 3 loaded via CDN — **no build step, no npm**. Components are plain JS files in `static/components/`. Served by FastAPI's `StaticFiles`.

## Optional AI Runners

```bash
pip install codyflow[cody]    # Enable Cody SDK runner
pip install codyflow[claude]  # Enable Claude Agent SDK runner
```

## Flow Definition Format

Flows are stored in SQLite but can be imported/exported as YAML. See `examples/` for templates (e.g., `basic.flow.yaml` shows the discuss → learn → code → reflect → judge pattern with loop-back).
