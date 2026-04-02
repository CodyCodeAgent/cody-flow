"""FastAPI backend for CodyFlow web UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codyflow.engine.flow import EdgeDef, Flow, FlowDefinition, validate_flow
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

_web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(_web_dir / "static")), name="static")

_storage = FlowStorage()
_config_path = Path.home() / ".codyflow" / "config.json"
_tasks_base_dir = Path.home() / ".codyflow" / "tasks"


# ---------------------------------------------------------------------------
# Per-task in-memory context
# ---------------------------------------------------------------------------

@dataclass
class TaskContext:
    task_id: str
    flow_obj: Flow | None = None
    asyncio_task: asyncio.Task | None = None
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    interactive_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    log_path: str = ""

    @property
    def is_running(self) -> bool:
        return self.asyncio_task is not None and not self.asyncio_task.done()


# task_id → TaskContext (in-memory, only live tasks)
_task_contexts: dict[str, TaskContext] = {}
# workdir → task_id (mutex: one task per workdir)
_workdir_locks: dict[str, str] = {}


def _new_task_id() -> str:
    return f"t{int(time.time() * 1000)}{secrets.token_hex(3)}"


def _task_log_path(task_id: str) -> Path:
    p = _tasks_base_dir / task_id
    p.mkdir(parents=True, exist_ok=True)
    return p / "events.jsonl"


def _append_event_log(log_path: str, event: dict) -> None:
    with contextlib.suppress(Exception):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_event_log(log_path: str) -> list[dict]:
    events = []
    p = Path(log_path)
    if not p.exists():
        return events
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            with contextlib.suppress(json.JSONDecodeError):
                events.append(json.loads(line))
    return events


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
    workdir: str = ""
    max_iterations: int = 5
    nodes: list[NodeModel] = []
    edges: list[EdgeModel] = []


class SaveFlowRequest(BaseModel):
    flow: FlowModel
    flow_id: int | None = None


class CreateTaskRequest(BaseModel):
    flow: FlowModel
    flow_id: int | None = None
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
    definition = {
        "name": req.flow.name,
        "description": req.flow.description,
        "runner": req.flow.runner,
        "workdir": req.flow.workdir,
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
    if not _storage.delete_flow(flow_id):
        raise HTTPException(404, f"Flow not found: {flow_id}")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Flow utilities
# ---------------------------------------------------------------------------

@app.get("/api/node-types")
async def get_node_types():
    return {"types": list_node_types()}


@app.get("/api/runners")
async def get_runners():
    return {"runners": list_runners()}


@app.get("/api/templates")
async def api_list_templates():
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
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(403, "Invalid filename")
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    file_path = examples_dir / filename
    if not file_path.exists():
        raise HTTPException(404, f"Template not found: {filename}")
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise HTTPException(500, f"Template parse error: {e}") from None
    return _parse_yaml_flow_data(data)


@app.post("/api/flow/validate")
async def api_validate(flow: FlowModel):
    definition = _model_to_definition(flow)
    errors = validate_flow(definition)
    return {"valid": len(errors) == 0, "errors": errors}


@app.post("/api/flow/export-yaml")
async def api_export_yaml(flow: FlowModel):
    data = _model_to_yaml_dict(flow)
    yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"yaml": yaml_str}


class ImportYamlRequest(BaseModel):
    yaml_content: str


@app.post("/api/flow/import-yaml")
async def api_import_yaml(req: ImportYamlRequest):
    try:
        data = yaml.safe_load(req.yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML 解析错误: {e}") from None
    if not isinstance(data, dict):
        raise HTTPException(400, "无效的 YAML 格式")
    return _parse_yaml_flow_data(data)


# ---------------------------------------------------------------------------
# Task API
# ---------------------------------------------------------------------------

@app.post("/api/tasks")
async def api_create_task(req: CreateTaskRequest):
    """Create and immediately start a new task."""
    workdir = str(Path(req.workdir or ".").resolve())

    # Workdir mutex
    existing_task_id = _workdir_locks.get(workdir)
    if existing_task_id and existing_task_id in _task_contexts:
        ctx = _task_contexts[existing_task_id]
        if ctx.is_running:
            raise HTTPException(409, f"工作目录 {workdir} 已有任务在运行 (task: {existing_task_id})")

    task_id = _new_task_id()
    log_path = str(_task_log_path(task_id))

    # Persist to DB
    flow_snapshot = {
        "name": req.flow.name,
        "description": req.flow.description,
        "runner": req.flow.runner,
        "max_iterations": req.flow.max_iterations,
        "nodes": [n.model_dump() for n in req.flow.nodes],
        "edges": [e.model_dump() for e in req.flow.edges],
    }
    _storage.create_task(
        task_id=task_id,
        flow_id=req.flow_id,
        flow_name=req.flow.name,
        flow_snapshot=flow_snapshot,
        workdir=workdir,
        user_input=req.user_input,
        log_path=log_path,
    )

    # Build in-memory context
    ctx = TaskContext(task_id=task_id, log_path=log_path)
    _task_contexts[task_id] = ctx
    _workdir_locks[workdir] = task_id

    # Build flow engine
    definition = _model_to_definition(req.flow)
    runner_config = _load_runner_config()
    flow_obj = Flow(definition, workdir, runner_config=runner_config)
    ctx.flow_obj = flow_obj

    def on_event(event: dict) -> None:
        _append_event_log(log_path, event)
        ctx.event_queue.put_nowait(event)

    async def on_interactive_input(node_id: str, assistant_output: str) -> str:
        on_event({
            "type": "interactive_wait",
            "node_id": node_id,
            "output": assistant_output,
            "timestamp": time.time(),
        })
        return await ctx.interactive_queue.get()

    flow_obj.on_event = on_event
    flow_obj.on_node_start = lambda nid, ntype: None
    flow_obj.on_node_complete = lambda nid, result: None
    flow_obj.on_flow_complete = lambda state: None
    flow_obj.on_interactive_input = on_interactive_input

    async def run_task():
        try:
            await flow_obj.run(req.user_input)
            _storage.update_task_status(task_id, "completed")
        except asyncio.CancelledError:
            _storage.update_task_status(task_id, "stopped")
            on_event({"type": "flow_stopped", "timestamp": time.time()})
        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            _storage.update_task_status(task_id, "failed")
            on_event({"type": "flow_error", "error": str(e), "timestamp": time.time()})
        finally:
            _workdir_locks.pop(workdir, None)

    ctx.asyncio_task = asyncio.create_task(run_task())
    return {"task_id": task_id, "status": "started"}


@app.get("/api/tasks")
async def api_list_tasks():
    tasks = _storage.list_tasks()
    result = []
    for t in tasks:
        ctx = _task_contexts.get(t.id)
        live_status = None
        if ctx:
            if ctx.is_running:
                live_status = "running"
            elif ctx.asyncio_task and ctx.asyncio_task.done():
                try:
                    ctx.asyncio_task.result()
                    live_status = "completed"
                except Exception:
                    live_status = "failed"
        result.append({
            "id": t.id,
            "flow_name": t.flow_name,
            "flow_id": t.flow_id,
            "workdir": t.workdir,
            "user_input": t.user_input,
            "status": live_status or t.status,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        })
    return {"tasks": result}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = _storage.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")
    ctx = _task_contexts.get(task_id)
    live_status = None
    if ctx:
        live_status = "running" if ctx.is_running else None
    events = _read_event_log(task.log_path)
    return {
        "id": task.id,
        "flow_name": task.flow_name,
        "flow_id": task.flow_id,
        "flow_snapshot": task.flow_snapshot,
        "workdir": task.workdir,
        "user_input": task.user_input,
        "status": live_status or task.status,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "events": events,
    }


@app.post("/api/tasks/{task_id}/stop")
async def api_stop_task(task_id: str):
    ctx = _task_contexts.get(task_id)
    if not ctx or not ctx.is_running:
        return {"status": "not_running"}
    ctx.asyncio_task.cancel()
    return {"status": "stopping"}


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str):
    ctx = _task_contexts.get(task_id)
    if ctx and ctx.is_running:
        raise HTTPException(409, "任务运行中，请先停止")
    _task_contexts.pop(task_id, None)
    if not _storage.delete_task(task_id):
        raise HTTPException(404, f"Task not found: {task_id}")
    return {"status": "deleted"}


@app.websocket("/ws/task/{task_id}")
async def ws_task(ws: WebSocket, task_id: str):
    """Per-task WebSocket: streams events and accepts interactive input."""
    await ws.accept()

    ctx = _task_contexts.get(task_id)
    if not ctx:
        # Task not in memory — send historical events and close
        task = _storage.get_task(task_id)
        if task:
            for ev in _read_event_log(task.log_path):
                await ws.send_json(ev)
        await ws.close()
        return

    # Replay historical events first
    for ev in _read_event_log(ctx.log_path):
        await ws.send_json(ev)

    async def send_events():
        while True:
            try:
                event = await asyncio.wait_for(ctx.event_queue.get(), timeout=30.0)
                await ws.send_json(event)
                if event.get("type") in ("flow_complete", "flow_stopped", "flow_error"):
                    break
            except asyncio.TimeoutError:
                await ws.send_json({"type": "keepalive"})
            except Exception:
                break

    async def recv_messages():
        while True:
            try:
                data = await ws.receive_json()
                if data.get("type") == "interactive_input":
                    ctx.interactive_queue.put_nowait(data.get("message", ""))
                elif data.get("type") == "stop" and ctx.is_running:
                    ctx.asyncio_task.cancel()
            except (WebSocketDisconnect, Exception):
                break

    try:
        await asyncio.gather(send_events(), recv_messages(), return_exceptions=True)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Context File Browser
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
    results: dict[str, Any] = {}
    v = sys.version
    results["python"] = {"ok": sys.version_info >= (3, 10), "detail": f"Python {v.split()[0]}"}
    try:
        import langgraph
        results["langgraph"] = {"ok": True, "detail": f"v{getattr(langgraph, '__version__', '?')}"}
    except ImportError:
        results["langgraph"] = {"ok": False, "detail": "未安装 — pip install langgraph"}
    try:
        import claude_agent_sdk
        results["claude_code"] = {"ok": True, "detail": f"v{getattr(claude_agent_sdk, '__version__', '?')}"}
    except ImportError:
        results["claude_code"] = {"ok": False, "detail": "未安装 — pip install claude-agent-sdk"}
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_workdir(workdir: str) -> Path:
    resolved = Path(workdir).resolve()
    if not resolved.is_dir():
        raise HTTPException(400, f"工作目录不存在: {resolved}")
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


def _parse_yaml_flow_data(data: dict) -> dict:
    nodes = []
    raw_nodes = data.get("nodes", [])
    # Layout: start at top-center, end at bottom-center, others in between
    n_total = len(raw_nodes)
    for i, n in enumerate(raw_nodes):
        node_type = n.get("type", "custom")
        if node_type == "start":
            x, y = 220, 20
        elif node_type == "end":
            x, y = 220, 40 + (n_total - 1) * 130
        else:
            x, y = 220, 40 + i * 130
        nodes.append({
            "id": n.get("id", f"node_{i}"),
            "type": node_type,
            "prompt": n.get("prompt", ""),
            "outputs": n.get("outputs", []),
            "runner": n.get("runner"),
            "interactive": n.get("interactive", False),
            "error_strategy": n.get("error_strategy", "retry"),
            "max_retries": n.get("max_retries", 3),
            "x": x,
            "y": y,
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
        "workdir": data.get("workdir", ""),
        "max_iterations": data.get("max_iterations", 3),
        "nodes": nodes,
        "edges": edges,
    }


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
        "workdir": flow.workdir,
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
