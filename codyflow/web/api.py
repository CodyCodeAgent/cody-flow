"""FastAPI backend for CodyFlow web UI."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codyflow.engine.flow import Flow, FlowDefinition, parse_flow, validate_flow, EdgeDef
from codyflow.nodes.base import NodeConfig
from codyflow.nodes.registry import list_node_types
from codyflow.runners.registry import list_runners

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

# In-memory state
_current_flow: Flow | None = None
_flow_task: asyncio.Task | None = None
_flow_events: list[dict[str, Any]] = []
_config_path = Path.home() / ".codyflow" / "config.json"


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


class RunRequest(BaseModel):
    workdir: str = "."
    user_input: str = ""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main web UI."""
    html_path = _web_dir / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Flow API
# ---------------------------------------------------------------------------

@app.get("/api/node-types")
async def get_node_types():
    return {"types": list_node_types()}


@app.get("/api/runners")
async def get_runners():
    return {"runners": list_runners()}


@app.post("/api/flow/validate")
async def api_validate(flow: FlowModel):
    definition = _model_to_definition(flow)
    errors = validate_flow(definition)
    return {"valid": len(errors) == 0, "errors": errors}


@app.post("/api/flow/save")
async def api_save_flow(flow: FlowModel, path: str = "flow.yaml"):
    data = _model_to_yaml_dict(flow)
    Path(path).write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return {"saved": path}


@app.post("/api/flow/load")
async def api_load_flow(path: str = "flow.yaml"):
    if not Path(path).exists():
        raise HTTPException(404, f"File not found: {path}")
    definition = parse_flow(path)
    return _definition_to_model(definition)


@app.post("/api/flow/run")
async def api_run_flow(flow: FlowModel):
    global _current_flow, _flow_task, _flow_events

    if _flow_task and not _flow_task.done():
        raise HTTPException(409, "A flow is already running")

    _flow_events = []
    definition = _model_to_definition(flow)
    workdir = "."

    _current_flow = Flow(definition, workdir)
    _current_flow.on_node_start = lambda nid, ntype: _flow_events.append(
        {"type": "node_start", "node_id": nid, "node_type": ntype}
    )
    _current_flow.on_node_complete = lambda nid, result: _flow_events.append(
        {"type": "node_complete", "node_id": nid, "output": result.output[:500]}
    )
    _current_flow.on_flow_complete = lambda state: _flow_events.append(
        {"type": "flow_complete",
         "completed": state.get("completed_nodes", []),
         "iteration": state.get("iteration", 0)}
    )

    _flow_task = asyncio.create_task(_current_flow.run())
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


@app.post("/api/flow/stop")
async def api_stop_flow():
    global _flow_task
    if _flow_task and not _flow_task.done():
        _flow_task.cancel()
        return {"status": "stopped"}
    return {"status": "not_running"}


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
    """Check environment dependencies."""
    results = {}

    # Python version
    v = sys.version
    ok = sys.version_info >= (3, 10)
    results["python"] = {"ok": ok, "detail": f"Python {v.split()[0]}"}

    # LangGraph
    try:
        import langgraph
        results["langgraph"] = {"ok": True, "detail": f"v{getattr(langgraph, '__version__', '?')}"}
    except ImportError:
        results["langgraph"] = {"ok": False, "detail": "未安装 — pip install langgraph"}

    # Cody SDK
    try:
        import cody
        results["cody_sdk"] = {"ok": True, "detail": f"v{getattr(cody, '__version__', '?')}"}
    except ImportError:
        results["cody_sdk"] = {"ok": False, "detail": "未安装 — pip install cody-ai"}

    # Claude Code SDK
    try:
        import claude_agent_sdk
        results["claude_code"] = {"ok": True, "detail": f"v{getattr(claude_agent_sdk, '__version__', '?')}"}
    except ImportError:
        results["claude_code"] = {"ok": False, "detail": "未安装 — pip install claude-agent-sdk"}

    # API Key check
    import os
    has_key = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CODY_MODEL_API_KEY")
    )
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


def _definition_to_model(d: FlowDefinition) -> dict:
    return {
        "name": d.name,
        "description": d.description,
        "runner": d.runner,
        "max_iterations": d.max_iterations,
        "nodes": [
            {"id": n.id, "type": n.type, "prompt": n.prompt,
             "outputs": n.outputs, "runner": n.runner,
             "interactive": n.interactive,
             "error_strategy": n.error_strategy,
             "max_retries": n.max_retries, "x": 0, "y": 0}
            for n in d.nodes
        ],
        "edges": [
            {"from_node": e.from_node, "to_node": e.to_node, "condition": e.condition}
            for e in d.edges
        ],
    }
