"""FastAPI backend for CodyFlow web UI."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from codyflow.engine.flow import Flow, FlowDefinition, validate_flow, EdgeDef
from codyflow.nodes.base import NodeConfig
from codyflow.nodes.registry import list_node_types
from codyflow.runners.registry import list_runners
from codyflow.storage import FlowStorage

logger = logging.getLogger(__name__)

app = FastAPI(title="CodyFlow", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
_web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(_web_dir / "static")), name="static")

# Singletons
_storage = FlowStorage()
_config_path = Path.home() / ".codyflow" / "config.json"

# In-memory run state
_current_flow: Flow | None = None
_flow_task: asyncio.Task | None = None
_flow_events: list[dict[str, Any]] = []
_event_queue: asyncio.Queue | None = None
_interactive_input_queue: asyncio.Queue | None = None
_active_ws: WebSocket | None = None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NodeModel(BaseModel):
    id: str
    type: str
    prompt: str = ""
    outputs: list[str] = []
    runner: str | None = None
    interactive: bool = False
    error_strategy: str = "retry"
    max_retries: int = 3
    x: float = 0
    y: float = 0


class EdgeModel(BaseModel):
    from_node: str = ""
    to_node: str = ""
    condition: str | None = None


class FlowModel(BaseModel):
    name: str
    description: str = ""
    runner: str = "cody"
    max_iterations: int = 5
    nodes: list[NodeModel] = []
    edges: list[EdgeModel] = []


class SaveFlowRequest(BaseModel):
    flow: FlowModel
    flow_id: int | None = None  # None = create new, int = update existing


class RunRequest(BaseModel):
    flow: FlowModel
    workdir: str = "."
    user_input: str = ""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = _web_dir / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Flow CRUD (SQLite)
# ---------------------------------------------------------------------------

@app.get("/api/flows")
async def api_list_flows():
    """List all saved flows."""
    flows = _storage.list_flows()
    return {
        "flows": [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "node_count": len(f.definition.get("nodes", [])),
                "created_at": f.created_at,
                "updated_at": f.updated_at,
            }
            for f in flows
        ]
    }


@app.get("/api/flows/{flow_id}")
async def api_get_flow(flow_id: int):
    """Load a saved flow by ID."""
    flow = _storage.get_flow(flow_id)
    if not flow:
        raise HTTPException(404, f"Flow not found: {flow_id}")
    return {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "definition": flow.definition,
        "created_at": flow.created_at,
        "updated_at": flow.updated_at,
    }


@app.post("/api/flows/save")
async def api_save_flow(req: SaveFlowRequest):
    """Save a flow to SQLite. Creates new if flow_id is None, updates otherwise."""
    definition = {
        "name": req.flow.name,
        "description": req.flow.description,
        "runner": req.flow.runner,
        "max_iterations": req.flow.max_iterations,
        "nodes": [n.model_dump() for n in req.flow.nodes],
        "edges": [e.model_dump() for e in req.flow.edges],
    }
    flow_id = _storage.save_flow(
        name=req.flow.name,
        description=req.flow.description,
        definition=definition,
        flow_id=req.flow_id,
    )
    return {"id": flow_id, "status": "saved"}


@app.delete("/api/flows/{flow_id}")
async def api_delete_flow(flow_id: int):
    """Delete a saved flow."""
    if not _storage.delete_flow(flow_id):
        raise HTTPException(404, f"Flow not found: {flow_id}")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Flow operations
# ---------------------------------------------------------------------------

@app.get("/api/node-types")
async def get_node_types():
    return {"types": list_node_types()}


@app.get("/api/runners")
async def get_runners():
    return {"runners": list_runners()}


@app.get("/api/templates")
async def api_list_templates():
    """List available flow templates from examples/ directory."""
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    templates = []
    if examples_dir.exists():
        for f in sorted(examples_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                templates.append({
                    "filename": f.name,
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "node_count": len(data.get("nodes", [])),
                })
            except Exception:
                pass
    return {"templates": templates}


@app.get("/api/templates/{filename}")
async def api_get_template(filename: str):
    """Load a specific template by filename."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(403, "Invalid filename")
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    file_path = examples_dir / filename
    if not file_path.exists():
        raise HTTPException(404, f"Template not found: {filename}")
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise HTTPException(500, f"Template parse error: {e}")

    # Parse into standardized format with default UI positions
    nodes = []
    for i, n in enumerate(data.get("nodes", [])):
        nodes.append({
            "id": n.get("id", f"node_{i}"),
            "type": n.get("type", "custom"),
            "prompt": n.get("prompt", ""),
            "outputs": n.get("outputs", []),
            "runner": n.get("runner"),
            "interactive": n.get("interactive", False),
            "error_strategy": n.get("error_strategy", "retry"),
            "max_retries": n.get("max_retries", 3),
            "x": 220,
            "y": 40 + i * 120,
        })

    edges = []
    for e in data.get("edges", []):
        edges.append({
            "from_node": e.get("from", ""),
            "to_node": e.get("to", ""),
            "condition": e.get("condition"),
        })

    return {
        "name": data.get("name", "imported"),
        "description": data.get("description", ""),
        "runner": data.get("runner", "cody"),
        "max_iterations": data.get("max_iterations", 3),
        "nodes": nodes,
        "edges": edges,
    }


@app.post("/api/flow/validate")
async def api_validate(flow: FlowModel):
    definition = _model_to_definition(flow)
    errors = validate_flow(definition)
    return {"valid": len(errors) == 0, "errors": errors}


@app.post("/api/flow/export-yaml")
async def api_export_yaml(flow: FlowModel):
    """Export flow as YAML string for sharing."""
    data = _model_to_yaml_dict(flow)
    yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"yaml": yaml_str}


class ImportYamlRequest(BaseModel):
    yaml_content: str


@app.post("/api/flow/import-yaml")
async def api_import_yaml(req: ImportYamlRequest):
    """Import a flow from YAML content. Returns parsed flow definition."""
    try:
        data = yaml.safe_load(req.yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML 解析错误: {e}")

    if not isinstance(data, dict):
        raise HTTPException(400, "无效的 YAML 格式")

    # Parse into standardized format with default UI positions
    nodes = []
    for i, n in enumerate(data.get("nodes", [])):
        nodes.append({
            "id": n.get("id", f"node_{i}"),
            "type": n.get("type", "custom"),
            "prompt": n.get("prompt", ""),
            "outputs": n.get("outputs", []),
            "runner": n.get("runner"),
            "interactive": n.get("interactive", False),
            "error_strategy": n.get("error_strategy", "retry"),
            "max_retries": n.get("max_retries", 3),
            "x": 220,
            "y": 40 + i * 120,
        })

    edges = []
    for e in data.get("edges", []):
        edges.append({
            "from_node": e.get("from", ""),
            "to_node": e.get("to", ""),
            "condition": e.get("condition"),
        })

    return {
        "name": data.get("name", "imported"),
        "description": data.get("description", ""),
        "runner": data.get("runner", "cody"),
        "max_iterations": data.get("max_iterations", 3),
        "nodes": nodes,
        "edges": edges,
    }


@app.post("/api/flow/run")
async def api_run_flow(req: RunRequest):
    global _current_flow, _flow_task, _flow_events, _event_queue, _interactive_input_queue

    if _flow_task and not _flow_task.done():
        raise HTTPException(409, "A flow is already running")

    _flow_events = []
    _event_queue = asyncio.Queue()
    _interactive_input_queue = asyncio.Queue()
    definition = _model_to_definition(req.flow)
    workdir = str(Path(req.workdir).resolve())

    runner_config = _load_runner_config()
    _current_flow = Flow(definition, workdir, runner_config=runner_config)

    def on_event(event: dict):
        _flow_events.append(event)
        if _event_queue:
            _event_queue.put_nowait(event)

    async def on_interactive_input(node_id: str, assistant_output: str) -> str:
        """Called by engine when an interactive node needs user input.

        Emits a 'interactive_wait' event so the frontend shows a chat input,
        then blocks until the user sends a message via WebSocket.
        """
        on_event({
            "type": "interactive_wait",
            "node_id": node_id,
            "output": assistant_output,
            "timestamp": time.time(),
        })
        # Block until user sends a message
        user_msg = await _interactive_input_queue.get()
        return user_msg

    _current_flow.on_event = on_event
    _current_flow.on_node_start = lambda nid, ntype: None
    _current_flow.on_node_complete = lambda nid, result: None
    _current_flow.on_flow_complete = lambda state: None
    _current_flow.on_interactive_input = on_interactive_input

    _flow_task = asyncio.create_task(_current_flow.run(req.user_input))
    return {"status": "started"}


@app.get("/api/flow/status")
async def api_flow_status():
    if not _flow_task:
        return {"status": "idle", "events": []}

    status = "running" if not _flow_task.done() else "completed"
    if _flow_task.done():
        try:
            _flow_task.result()
        except Exception:
            status = "failed"

    return {"status": status, "events": _flow_events}


@app.get("/api/flow/events")
async def api_flow_events_sse():
    """Server-Sent Events endpoint for real-time flow execution events."""
    async def event_generator():
        if not _event_queue:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No flow running'})}\n\n"
            return

        # Send already-collected events
        sent_count = len(_flow_events)
        for ev in _flow_events:
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

        # Drain queue of events we already sent (they were added to both lists)
        drained = 0
        while not _event_queue.empty() and drained < sent_count:
            try:
                _event_queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break

        while True:
            try:
                event = await asyncio.wait_for(_event_queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") == "flow_complete":
                    break
            except asyncio.TimeoutError:
                yield f": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.websocket("/ws/flow")
async def ws_flow(ws: WebSocket):
    """WebSocket endpoint for bidirectional flow communication.

    Server → Client: flow events (same as SSE)
    Client → Server: interactive node user input (JSON: {"type": "interactive_input", "message": "..."})
    """
    global _active_ws
    await ws.accept()
    _active_ws = ws

    try:
        # Send already-collected events
        for ev in list(_flow_events):
            await ws.send_json(ev)

        # Drain queue of events we already sent
        if _event_queue:
            drained = 0
            sent_count = len(_flow_events)
            while not _event_queue.empty() and drained < sent_count:
                try:
                    _event_queue.get_nowait()
                    drained += 1
                except asyncio.QueueEmpty:
                    break

        async def send_events():
            """Forward engine events to WebSocket."""
            if not _event_queue:
                return
            while True:
                try:
                    event = await asyncio.wait_for(_event_queue.get(), timeout=30.0)
                    await ws.send_json(event)
                    if event.get("type") in ("flow_complete", "flow_stopped"):
                        break
                except asyncio.TimeoutError:
                    await ws.send_json({"type": "keepalive"})
                except Exception:
                    break

        async def recv_messages():
            """Receive user messages and route to interactive input queue."""
            while True:
                try:
                    data = await ws.receive_json()
                    if data.get("type") == "interactive_input" and _interactive_input_queue:
                        _interactive_input_queue.put_nowait(data.get("message", ""))
                    elif data.get("type") == "stop":
                        if _flow_task and not _flow_task.done():
                            _flow_task.cancel()
                            if _event_queue:
                                _event_queue.put_nowait({"type": "flow_stopped", "timestamp": time.time()})
                except (WebSocketDisconnect, Exception):
                    break

        # Run send and receive concurrently
        await asyncio.gather(send_events(), recv_messages(), return_exceptions=True)

    except WebSocketDisconnect:
        pass
    finally:
        _active_ws = None


@app.post("/api/flow/stop")
async def api_stop_flow():
    global _flow_task
    if _flow_task and not _flow_task.done():
        _flow_task.cancel()
        if _event_queue:
            _event_queue.put_nowait({"type": "flow_stopped", "timestamp": time.time()})
        return {"status": "stopped"}
    return {"status": "not_running"}


# ---------------------------------------------------------------------------
# Context File Browser API
# ---------------------------------------------------------------------------

@app.get("/api/context/list")
async def api_list_context(workdir: str = Query(".")):
    ctx_dir = _validate_workdir(workdir) / ".codyflow" / "context"
    if not ctx_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(ctx_dir.iterdir()):
        if f.is_file():
            stat = f.stat()
            files.append({"name": f.name, "size": stat.st_size, "modified": stat.st_mtime})
    return {"files": files}


@app.get("/api/context/read")
async def api_read_context(filename: str, workdir: str = Query(".")):
    ctx_dir = _validate_workdir(workdir) / ".codyflow" / "context"
    file_path = ctx_dir / filename

    if not file_path.resolve().is_relative_to(ctx_dir.resolve()):
        raise HTTPException(403, "Access denied")
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    content = file_path.read_text(encoding="utf-8")
    return {"name": filename, "content": content, "size": len(content)}


@app.get("/api/logs/list")
async def api_list_logs(workdir: str = Query(".")):
    logs_dir = _validate_workdir(workdir) / ".codyflow" / "logs"
    if not logs_dir.exists():
        return {"files": []}

    files = []
    for f in sorted(logs_dir.iterdir(), reverse=True):
        if f.is_file() and f.suffix == ".jsonl":
            stat = f.stat()
            files.append({"name": f.name, "size": stat.st_size, "modified": stat.st_mtime})
    return {"files": files[:20]}


@app.get("/api/logs/read")
async def api_read_log(filename: str, workdir: str = Query(".")):
    logs_dir = _validate_workdir(workdir) / ".codyflow" / "logs"
    file_path = logs_dir / filename

    if not file_path.resolve().is_relative_to(logs_dir.resolve()):
        raise HTTPException(403, "Access denied")
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    events = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return {"events": events}


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.get("/api/config/load")
async def api_load_config():
    if _config_path.exists():
        return json.loads(_config_path.read_text(encoding="utf-8"))
    return {}


@app.post("/api/config/save")
async def api_save_config(config: dict):
    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"saved": str(_config_path)}


@app.get("/api/config/check-env")
async def api_check_env():
    results = {}

    v = sys.version
    results["python"] = {"ok": sys.version_info >= (3, 10), "detail": f"Python {v.split()[0]}"}

    try:
        import langgraph
        results["langgraph"] = {"ok": True, "detail": f"v{getattr(langgraph, '__version__', '?')}"}
    except ImportError:
        results["langgraph"] = {"ok": False, "detail": "未安装 — pip install langgraph"}

    try:
        import cody
        results["cody_sdk"] = {"ok": True, "detail": f"v{getattr(cody, '__version__', '?')}"}
    except ImportError:
        results["cody_sdk"] = {"ok": False, "detail": "未安装 — pip install cody-ai"}

    try:
        import claude_agent_sdk
        results["claude_code"] = {"ok": True, "detail": f"v{getattr(claude_agent_sdk, '__version__', '?')}"}
    except ImportError:
        results["claude_code"] = {"ok": False, "detail": "未安装 — pip install claude-agent-sdk"}

    import os
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CODY_MODEL_API_KEY"))
    if has_key:
        results["api_key"] = {"ok": True, "detail": "已配置 (环境变量)"}
    elif _config_path.exists():
        try:
            cfg = json.loads(_config_path.read_text())
            if cfg.get("cody", {}).get("api_key"):
                results["api_key"] = {"ok": True, "detail": "已配置 (配置文件)"}
            else:
                results["api_key"] = {"ok": False, "detail": "未配置 API Key"}
        except Exception:
            results["api_key"] = {"ok": False, "detail": "未配置 API Key"}
    else:
        results["api_key"] = {"ok": False, "detail": "未配置 — 在设置页面填写或设置环境变量"}

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_workdir(workdir: str) -> Path:
    """Resolve and validate a workdir path. Raises HTTPException on invalid input."""
    resolved = Path(workdir).resolve()
    if not resolved.is_dir():
        raise HTTPException(400, f"工作目录不存在: {resolved}")
    # Block obvious traversal attempts (e.g. workdir = "/etc" or "/")
    # Must be at least 2 levels deep to be a plausible project directory
    if len(resolved.parts) < 3:
        raise HTTPException(403, f"工作目录不允许: {resolved}")
    return resolved


def _load_runner_config() -> dict:
    if not _config_path.exists():
        return {}
    try:
        return json.loads(_config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _model_to_definition(flow: FlowModel) -> FlowDefinition:
    nodes = [
        NodeConfig(
            id=n.id, type=n.type, prompt=n.prompt,
            outputs=n.outputs, runner=n.runner,
            interactive=n.interactive,
            error_strategy=n.error_strategy,
            max_retries=n.max_retries,
        )
        for n in flow.nodes
    ]
    edges = [
        EdgeDef(from_node=e.from_node, to_node=e.to_node, condition=e.condition)
        for e in flow.edges
    ]
    return FlowDefinition(
        name=flow.name,
        description=flow.description,
        runner=flow.runner,
        max_iterations=flow.max_iterations,
        nodes=nodes,
        edges=edges,
    )


def _model_to_yaml_dict(flow: FlowModel) -> dict:
    return {
        "name": flow.name,
        "description": flow.description,
        "runner": flow.runner,
        "max_iterations": flow.max_iterations,
        "nodes": [
            {k: v for k, v in {
                "id": n.id, "type": n.type,
                "prompt": n.prompt or None,
                "outputs": n.outputs or None,
                "runner": n.runner,
                "interactive": n.interactive or None,
                "error_strategy": n.error_strategy if n.error_strategy != "retry" else None,
                "max_retries": n.max_retries if n.max_retries != 3 else None,
            }.items() if v is not None}
            for n in flow.nodes
        ],
        "edges": [
            {k: v for k, v in {
                "from": e.from_node, "to": e.to_node,
                "condition": e.condition,
            }.items() if v is not None}
            for e in flow.edges
        ],
    }
