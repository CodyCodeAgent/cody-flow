"""Flow engine - parses YAML, orchestrates nodes, handles routing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from codyflow.nodes.base import FlowContext, NodeConfig, NodeResult
from codyflow.nodes.registry import get_node_type
# Ensure built-in nodes are registered
import codyflow.nodes.builtin  # noqa: F401
from codyflow.runners.registry import get_runner
# Ensure built-in runners are registered
import codyflow.runners.cody_runner  # noqa: F401
import codyflow.runners.claude_runner  # noqa: F401


@dataclass
class Edge:
    """A connection between two nodes, optionally with a condition."""

    from_node: str
    to_node: str
    condition: str | None = None


@dataclass
class FlowDefinition:
    """Parsed flow definition from YAML."""

    name: str
    description: str = ""
    runner: str = "cody"
    max_iterations: int = 5
    nodes: list[NodeConfig] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    user_input: str = ""


def parse_flow(yaml_path: str) -> FlowDefinition:
    """Parse a flow definition from a YAML file."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nodes = []
    for n in data.get("nodes", []):
        nodes.append(NodeConfig(
            id=n["id"],
            type=n.get("type", "custom"),
            prompt=n.get("prompt", ""),
            inputs=n.get("inputs", []),
            outputs=n.get("outputs", []),
            runner=n.get("runner"),
            max_turns=n.get("max_turns"),
            extra=n.get("extra", {}),
        ))

    edges = []
    for e in data.get("edges", []):
        edges.append(Edge(
            from_node=e["from"],
            to_node=e["to"],
            condition=e.get("condition"),
        ))

    return FlowDefinition(
        name=data.get("name", "unnamed"),
        description=data.get("description", ""),
        runner=data.get("runner", "cody"),
        max_iterations=data.get("max_iterations", 5),
        nodes=nodes,
        edges=edges,
        user_input=data.get("user_input", ""),
    )


class Flow:
    """The main flow engine that orchestrates node execution."""

    def __init__(self, definition: FlowDefinition, workdir: str):
        self.definition = definition
        self.workdir = workdir
        self.context_dir = Path(workdir) / ".codyflow" / "context"
        self.logs_dir = Path(workdir) / ".codyflow" / "logs"

        # State tracking
        self.completed_nodes: set[str] = set()
        self.node_results: dict[str, NodeResult] = {}
        self.iteration = 0

        # Build node lookup
        self._node_configs = {n.id: n for n in definition.nodes}

        # Callbacks for progress reporting
        self.on_node_start: Any = None
        self.on_node_complete: Any = None
        self.on_flow_complete: Any = None

    def _ensure_dirs(self):
        """Create working directories if they don't exist."""
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _get_start_nodes(self) -> list[str]:
        """Find nodes with no incoming edges (entry points)."""
        targets = {e.to_node for e in self.definition.edges}
        return [n.id for n in self.definition.nodes if n.id not in targets]

    def _get_next_nodes(self, current_id: str, route: str | None = None) -> list[str]:
        """Get the next node(s) after the current one, considering conditions."""
        next_nodes = []
        for edge in self.definition.edges:
            if edge.from_node != current_id:
                continue
            # If edge has a condition, only follow it when route matches
            if edge.condition is not None:
                if route == edge.condition:
                    next_nodes.append(edge.to_node)
            else:
                # Unconditional edge
                next_nodes.append(edge.to_node)
        return next_nodes

    def _build_flow_context(self, current_node_id: str) -> FlowContext:
        """Build the FlowContext for a specific node."""
        all_nodes = []
        for nc in self.definition.nodes:
            if nc.id in self.completed_nodes:
                status = "completed"
            elif nc.id == current_node_id:
                status = "current"
            else:
                status = "pending"
            all_nodes.append({
                "id": nc.id,
                "type": nc.type,
                "status": status,
                "outputs": nc.outputs,
                "prompt_summary": (nc.prompt or "")[:80],
            })

        # Collect available context files
        available_files = []
        if self.context_dir.exists():
            for f in sorted(self.context_dir.iterdir()):
                if f.is_file():
                    # Find which node produced this file
                    producer = "unknown"
                    for nc in self.definition.nodes:
                        if f.name in nc.outputs:
                            producer = f"{nc.id} ({nc.type})"
                            break
                    available_files.append((str(f), producer))

        return FlowContext(
            flow_name=self.definition.name,
            flow_description=self.definition.description,
            workdir=self.workdir,
            context_dir=str(self.context_dir),
            all_nodes=all_nodes,
            available_files=available_files,
            iteration=self.iteration,
            max_iterations=self.definition.max_iterations,
        )

    def _get_runner(self, node_config: NodeConfig):
        """Get the runner for a node (node-level override or global default)."""
        runner_name = node_config.runner or self.definition.runner
        kwargs = {}
        if node_config.max_turns:
            kwargs["max_turns"] = node_config.max_turns
        return get_runner(runner_name, workdir=self.workdir, **kwargs)

    async def _execute_node(self, node_id: str) -> NodeResult:
        """Execute a single node."""
        config = self._node_configs[node_id]
        node_cls = get_node_type(config.type)
        node = node_cls(config)

        flow_context = self._build_flow_context(node_id)

        if self.on_node_start:
            self.on_node_start(node_id, config.type)

        async with self._get_runner(config) as runner:
            result = await node.execute(runner, flow_context)

        # Save output files to context directory
        if result.output and config.outputs:
            for output_file in config.outputs:
                output_path = self.context_dir / output_file
                output_path.write_text(result.output, encoding="utf-8")

        self.completed_nodes.add(node_id)
        self.node_results[node_id] = result

        if self.on_node_complete:
            self.on_node_complete(node_id, result)

        return result

    async def run(self, user_input: str = "") -> dict[str, NodeResult]:
        """Execute the entire flow.

        Args:
            user_input: The user's task description / requirements.

        Returns:
            Dict mapping node IDs to their results.
        """
        self._ensure_dirs()

        # Save user input to context
        if user_input or self.definition.user_input:
            input_text = user_input or self.definition.user_input
            (self.context_dir / "user_input.md").write_text(
                input_text, encoding="utf-8"
            )
            self.definition.description = (
                self.definition.description or input_text
            )

        # Find starting nodes
        queue = self._get_start_nodes()
        if not queue:
            raise ValueError("Flow has no start nodes (all nodes have incoming edges)")

        while queue:
            node_id = queue.pop(0)

            # Skip already completed nodes (unless in a loop iteration)
            if node_id in self.completed_nodes and node_id not in self._loop_nodes():
                continue

            result = await self._execute_node(node_id)

            # Get routing decision if the node produced one
            route = result.metadata.get("route")

            # Find next nodes
            next_nodes = self._get_next_nodes(node_id, route)

            # Handle END sentinel
            next_nodes = [n for n in next_nodes if n != "END"]

            # Check iteration limits for loops
            if any(n in self.completed_nodes for n in next_nodes):
                self.iteration += 1
                if self.iteration >= self.definition.max_iterations:
                    break
                # Reset completed status for loop nodes so they re-execute
                for n in next_nodes:
                    self.completed_nodes.discard(n)

            queue.extend(next_nodes)

        if self.on_flow_complete:
            self.on_flow_complete(self.node_results)

        return self.node_results

    def _loop_nodes(self) -> set[str]:
        """Identify nodes that are targets of back-edges (loop destinations)."""
        forward_targets = set()
        loop_targets = set()
        for edge in self.definition.edges:
            if edge.to_node in forward_targets:
                loop_targets.add(edge.to_node)
            forward_targets.add(edge.to_node)
        return loop_targets
