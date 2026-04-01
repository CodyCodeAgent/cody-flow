"""Flow engine - builds and runs LangGraph workflows from YAML definitions."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from codyflow.nodes.base import FlowState, NodeConfig, NodeResult
from codyflow.nodes.registry import get_node_type
import codyflow.nodes.builtin  # noqa: F401  — register built-in nodes
from codyflow.runners.registry import get_runner
import codyflow.runners.cody_runner  # noqa: F401
import codyflow.runners.claude_runner  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------

@dataclass
class EdgeDef:
    from_node: str
    to_node: str
    condition: str | None = None


@dataclass
class FlowDefinition:
    name: str
    description: str = ""
    runner: str = "cody"
    max_iterations: int = 5
    nodes: list[NodeConfig] = field(default_factory=list)
    edges: list[EdgeDef] = field(default_factory=list)
    user_input: str = ""
    variables: dict[str, str] = field(default_factory=dict)


def _substitute_variables(text: str, variables: dict[str, str]) -> str:
    """Replace {var_name} placeholders with values from variables dict."""
    def replacer(match):
        key = match.group(1)
        return variables.get(key, match.group(0))
    return re.sub(r"\{(\w+)\}", replacer, text)


def parse_flow(yaml_path: str, variables: dict[str, str] | None = None) -> FlowDefinition:
    """Parse a flow definition from a YAML file with optional variable substitution."""
    variables = variables or {}

    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Apply variable substitution to the entire YAML
    if variables:
        raw = _substitute_variables(raw, variables)

    data = yaml.safe_load(raw)

    nodes = []
    for n in data.get("nodes", []):
        nodes.append(NodeConfig(
            id=n["id"],
            type=n.get("type", "custom"),
            prompt=n.get("prompt", ""),
            outputs=n.get("outputs", []),
            runner=n.get("runner"),
            max_turns=n.get("max_turns"),
            interactive=n.get("interactive", False),
            error_strategy=n.get("error_strategy", "retry"),
            max_retries=n.get("max_retries", 3),
            extra=n.get("extra", {}),
        ))

    edges = []
    for e in data.get("edges", []):
        edges.append(EdgeDef(
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
        variables=variables,
    )


# ---------------------------------------------------------------------------
# Flow builder — converts FlowDefinition into a LangGraph StateGraph
# ---------------------------------------------------------------------------

class Flow:
    """Builds and executes a LangGraph workflow from a FlowDefinition."""

    def __init__(self, definition: FlowDefinition, workdir: str):
        self.definition = definition
        self.workdir = str(Path(workdir).resolve())
        self.context_dir = str(Path(self.workdir) / ".codyflow" / "context")
        self.db_path = str(Path(self.workdir) / ".codyflow" / "state.db")

        self._node_configs: dict[str, NodeConfig] = {
            n.id: n for n in definition.nodes
        }

        # Callbacks
        self.on_node_start: Any = None
        self.on_node_complete: Any = None
        self.on_flow_complete: Any = None
        self.on_interactive_input: Any = None  # async callable for user input

    def _ensure_dirs(self):
        Path(self.context_dir).mkdir(parents=True, exist_ok=True)
        (Path(self.workdir) / ".codyflow" / "logs").mkdir(parents=True, exist_ok=True)

    def _build_node_map(self) -> list[dict[str, Any]]:
        """Build the node map list for FlowState."""
        return [
            {
                "id": nc.id,
                "type": nc.type,
                "outputs": nc.outputs,
                "prompt_summary": (nc.prompt or "")[:80],
            }
            for nc in self.definition.nodes
        ]

    def _make_node_fn(self, node_config: NodeConfig):
        """Create an async function for a LangGraph node."""
        flow = self

        async def node_fn(state: FlowState) -> FlowState:
            nid = node_config.id

            # Update current node
            state = {**state, "current_node": nid}

            if flow.on_node_start:
                flow.on_node_start(nid, node_config.type)

            # Get the right runner
            runner_name = node_config.runner or flow.definition.runner
            kwargs = {}
            if node_config.max_turns:
                kwargs["max_turns"] = node_config.max_turns

            # Execute with error handling
            retries = 0
            last_error = None
            result: NodeResult | None = None

            while retries <= node_config.max_retries:
                try:
                    node_cls = get_node_type(node_config.type)
                    node = node_cls(node_config)

                    async with get_runner(runner_name, workdir=flow.workdir, **kwargs) as runner:
                        result = await node.execute(runner, state)
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"Node {nid} failed (attempt {retries + 1}): {e}"
                    )
                    if node_config.error_strategy == "fail":
                        raise
                    if node_config.error_strategy == "skip":
                        break
                    retries += 1
                    if retries > node_config.max_retries:
                        if node_config.error_strategy == "retry":
                            raise RuntimeError(
                                f"Node {nid} failed after {node_config.max_retries} retries: {last_error}"
                            )

            updates: dict[str, Any] = {}

            if result:
                # Write output files to context directory
                if result.output and node_config.outputs:
                    ctx = Path(flow.context_dir)
                    for out_file in node_config.outputs:
                        (ctx / out_file).write_text(result.output, encoding="utf-8")

                # Update completed nodes
                completed = list(state.get("completed_nodes", []))
                if nid not in completed:
                    completed.append(nid)
                updates["completed_nodes"] = completed

                # If node produced a route decision, set it
                if "route" in result.metadata:
                    updates["route"] = result.metadata["route"]

                if flow.on_node_complete:
                    flow.on_node_complete(nid, result)
            else:
                updates["last_error"] = last_error

            return {**state, **updates}

        return node_fn

    def _make_interactive_node_fn(self, node_config: NodeConfig):
        """Create an async function for an interactive (multi-turn) node."""
        flow = self

        async def interactive_fn(state: FlowState) -> FlowState:
            nid = node_config.id
            state = {**state, "current_node": nid}

            if flow.on_node_start:
                flow.on_node_start(nid, node_config.type)

            runner_name = node_config.runner or flow.definition.runner
            kwargs = {}
            if node_config.max_turns:
                kwargs["max_turns"] = node_config.max_turns

            node_cls = get_node_type(node_config.type)
            node = node_cls(node_config)

            session_id = None
            final_output = ""

            async with get_runner(runner_name, workdir=flow.workdir, **kwargs) as runner:
                # First turn: send the full prompt
                prompt = node.build_prompt(state)
                result = await runner.run(prompt)
                session_id = result.session_id
                final_output = result.output

                if flow.on_node_complete:
                    flow.on_node_complete(nid, NodeResult(
                        node_id=nid, output=result.output
                    ))

                # Multi-turn loop: ask user for input
                while True:
                    if not flow.on_interactive_input:
                        break

                    user_msg = await flow.on_interactive_input(nid, result.output)
                    if not user_msg or user_msg.strip().lower() in ("done", "结束", "ok", "完成"):
                        break

                    result = await runner.run(user_msg, session_id=session_id)
                    session_id = result.session_id
                    final_output = result.output

                    if flow.on_node_complete:
                        flow.on_node_complete(nid, NodeResult(
                            node_id=nid, output=result.output
                        ))

            # Save final output
            if final_output and node_config.outputs:
                ctx = Path(flow.context_dir)
                for out_file in node_config.outputs:
                    (ctx / out_file).write_text(final_output, encoding="utf-8")

            completed = list(state.get("completed_nodes", []))
            if nid not in completed:
                completed.append(nid)

            return {**state, "completed_nodes": completed}

        return interactive_fn

    def _find_start_node(self) -> str:
        """Find the entry-point node (no incoming edges)."""
        targets = {e.to_node for e in self.definition.edges}
        for n in self.definition.nodes:
            if n.id not in targets:
                return n.id
        return self.definition.nodes[0].id

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph from the flow definition."""
        graph = StateGraph(FlowState)

        # Add nodes
        for nc in self.definition.nodes:
            if nc.interactive:
                graph.add_node(nc.id, self._make_interactive_node_fn(nc))
            else:
                graph.add_node(nc.id, self._make_node_fn(nc))

        # Set entry point
        start = self._find_start_node()
        graph.set_entry_point(start)

        # Group edges by source node
        edges_by_source: dict[str, list[EdgeDef]] = {}
        for e in self.definition.edges:
            edges_by_source.setdefault(e.from_node, []).append(e)

        # Add edges
        for source, edges in edges_by_source.items():
            has_conditions = any(e.condition for e in edges)

            if has_conditions:
                # Conditional routing
                route_map: dict[str, str] = {}
                for e in edges:
                    target = END if e.to_node == "END" else e.to_node
                    if e.condition:
                        route_map[e.condition] = target
                    else:
                        route_map["__default__"] = target

                def make_router(rm):
                    def router(state: FlowState) -> str:
                        route = state.get("route", "")
                        # Check iteration limit for loop-back edges
                        iteration = state.get("iteration", 0)
                        max_iter = state.get("max_iterations", 5)
                        if iteration >= max_iter and route in rm:
                            # If we're at max iterations, force END
                            return END
                        return rm.get(route, rm.get("__default__", END))
                    return router

                graph.add_conditional_edges(source, make_router(route_map))
            else:
                # Simple edge (should be exactly one unconditional target)
                if len(edges) == 1:
                    target = END if edges[0].to_node == "END" else edges[0].to_node
                    graph.add_edge(source, target)

        # Nodes with no outgoing edges → END
        sources_with_edges = set(edges_by_source.keys())
        for nc in self.definition.nodes:
            if nc.id not in sources_with_edges:
                graph.add_edge(nc.id, END)

        return graph

    async def run(self, user_input: str = "") -> dict[str, Any]:
        """Execute the flow.

        Args:
            user_input: The user's task description / requirements.

        Returns:
            The final flow state.
        """
        self._ensure_dirs()

        # Save user input
        input_text = user_input or self.definition.user_input
        if input_text:
            Path(self.context_dir, "user_input.md").write_text(
                input_text, encoding="utf-8"
            )

        # Build initial state
        initial_state: FlowState = {
            "flow_name": self.definition.name,
            "flow_description": self.definition.description or input_text,
            "workdir": self.workdir,
            "context_dir": self.context_dir,
            "node_map": self._build_node_map(),
            "current_node": "",
            "completed_nodes": [],
            "iteration": 0,
            "max_iterations": self.definition.max_iterations,
            "route": "",
            "last_error": None,
            "waiting_for_user": False,
            "user_message": "",
        }

        # Build graph
        graph = self._build_graph()

        # Compile with SQLite checkpoint for persistence & resume
        async with AsyncSqliteSaver.from_conn_string(self.db_path) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)

            # Check for existing state (resume support)
            thread_config = {"configurable": {"thread_id": self.definition.name}}

            # Reset any "running" nodes to pending on startup
            existing = await checkpointer.aget(thread_config)
            if existing:
                logger.info(f"Resuming flow '{self.definition.name}' from checkpoint")
                # Use existing state but clear any stale "current_node"
                initial_state = {**existing.get("channel_values", initial_state)}
                initial_state["current_node"] = ""

            # Run the graph
            final_state = await app.ainvoke(initial_state, config=thread_config)

        if self.on_flow_complete:
            self.on_flow_complete(final_state)

        return final_state
