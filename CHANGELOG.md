# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-01

### Added

- **Visual flow editor** — Drag-and-drop node canvas with edge drawing and conditional routing
- **6 built-in node types** — discuss, learn, code, reflect, judge, custom
- **2 runner backends** — Cody SDK (`cody-ai`) and Claude Agent SDK (`claude-agent-sdk`)
- **Flow engine** powered by LangGraph with conditional routing, loops, and SQLite checkpoint
- **WebSocket bidirectional communication** for real-time execution events and interactive node input
- **SSE fallback** for environments without WebSocket support
- **Interactive discuss nodes** — Multi-turn chat modal for user-AI conversation
- **SQLite flow storage** — CRUD for flow definitions with import/export YAML
- **Built-in templates** — basic, quick-fix, and deep-analysis workflow templates
- **Execution logger** — Structured JSONL logs with per-node prompt/output archives
- **Context file browser** — View node output reports from the UI
- **Settings page** — API key, model, runner config, and environment detection
- **Canvas zoom/pan** — Scroll to zoom, Ctrl+drag to pan
- **115 unit tests** covering nodes, engine, storage, validation, logger, API helpers, and registries
