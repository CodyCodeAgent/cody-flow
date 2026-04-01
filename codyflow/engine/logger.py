"""Execution logger — writes structured logs to .codyflow/logs/."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from codyflow.nodes.base import NodeResult


class ExecutionLogger:
    """Logs all execution details to files for debugging and observability."""

    def __init__(self, logs_dir: str):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.run_log = self.logs_dir / f"run_{self.run_id}.jsonl"

    def log_event(self, event: dict):
        """Append a structured event to the run log."""
        event["timestamp"] = time.time()
        event["run_id"] = self.run_id
        with open(self.run_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_node_start(self, node_id: str, node_type: str, prompt: str):
        self.log_event({
            "event": "node_start",
            "node_id": node_id,
            "node_type": node_type,
            "prompt_length": len(prompt),
        })
        prompt_file = self.logs_dir / f"{self.run_id}_{node_id}_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

    def log_node_complete(self, node_id: str, result: NodeResult, duration: float):
        self.log_event({
            "event": "node_complete",
            "node_id": node_id,
            "output_length": len(result.output),
            "output_files": result.output_files,
            "metadata": result.metadata,
            "duration_seconds": round(duration, 2),
        })
        output_file = self.logs_dir / f"{self.run_id}_{node_id}_output.md"
        output_file.write_text(result.output, encoding="utf-8")

    def log_node_error(self, node_id: str, error: str, attempt: int, tb: str = ""):
        self.log_event({
            "event": "node_error",
            "node_id": node_id,
            "error": error,
            "attempt": attempt,
            "traceback": tb,
        })

    def log_route_decision(self, node_id: str, route: str, reasoning: str):
        self.log_event({
            "event": "route_decision",
            "node_id": node_id,
            "route": route,
            "reasoning": reasoning,
        })

    def log_flow_start(self, flow_name: str, description: str, node_count: int):
        self.log_event({
            "event": "flow_start",
            "flow_name": flow_name,
            "description": description,
            "node_count": node_count,
        })

    def log_flow_complete(self, completed_nodes: list, iteration: int, total_duration: float):
        self.log_event({
            "event": "flow_complete",
            "completed_nodes": completed_nodes,
            "iteration": iteration,
            "total_duration_seconds": round(total_duration, 2),
        })
