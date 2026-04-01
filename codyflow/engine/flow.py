"""Flow engine - builds and runs LangGraph workflows from YAML definitions."""

from __future__ import annotations

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

    # Apply variable substitution to the entire YAML (including prompts)
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
# Validation
# ---------------------------------------------------------------------------

def validate_flow(definition: FlowDefinition) -> list[str]:
    """Validate a flow definition and return a list of error messages."""
    errors = []
    node_ids = {n.id for n in definition.nodes}

    # Check edges reference existing nodes
    for e in definition.edges:
        if e.from_node not in node_ids:
            errors.append(f"Edge references unknown source node '{e.from_node}'")
        if e.to_node not in node_ids and e.to_node != "END":
            errors.append(f"Edge references unknown target node '{e.to_node}'")

    # Check for unreachable nodes (no incoming edges and not a start node)
    targets = {e.to_node for e in definition.edges}
    sources = {e.from_node for e in definition.edges}
    start_nodes = node_ids - targets
    if not start_nodes:
        errors.append("Flow has no start node (all nodes have incoming edges)")

    for nid in node_ids:
        if nid not in targets and nid not in start_nodes:
            errors.append(f"Node '{nid}' is unreachable")

    # Check conditional edges have valid structure
    edges_by_source: dict[str, list[EdgeDef]] = {}
    for e in definition.edges:
        edges_by_source.setdefault(e.from_node, []).append(e)

    for source, edges in edges_by_source.items():
        conditions = [e.condition for e in edges if e.condition]
        if conditions and len(conditions) != len(edges):
            # Mix of conditional and unconditional from same source is OK
            # (unconditional becomes default)
            pass
        if len(conditions) != len(set(conditions)):
            errors.append(
                f"Node '{source}' has duplicate edge conditions: {conditions}"
            )

    # Warn about custom nodes with no prompt
    for n in definition.nodes:
        if n.type == "custom" and not n.prompt:
            errors.append(
                f"Custom node '{n.id}' has no prompt — it will execute with an empty task"
            )

    return errors


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

        # Detect which nodes are loop-back targets
        self._loop_back_targets = self._detect_loop_targets()

        # Callbacks
        self.on_node_start: Any = None
        self.on_node_complete: Any = None
        self.on_flow_complete: Any = None
        self.on_interactive_input: Any = None  # async callable for user input

    def _detect_loop_targets(self) -> set[str]:
        """Find nodes that are targets of back-edges (loop destinations).

        A back-edge is an edge that points to a node that appears earlier
        in the node list (i.e. the edge goes "backwards" in the flow).
        """
        node_order = {n.id: i for i, n in enumerate(self.definition.nodes)}
        targets = set()
        for e in self.definition.edges:
            if e.to_node == "END":
                continue
            from_idx = node_order.get(e.from_node, 0)
            to_idx = node_order.get(e.to_node, 0)
            if to_idx <= from_idx:
                targets.add(e.to_node)
        return targets

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

            # Increment iteration if this node is a loop-back target
            iteration = state.get("iteration", 0)
            if nid in flow._loop_back_targets and nid in state.get("completed_nodes", []):
                iteration += 1

            state = {**state, "current_node": nid, "iteration": iteration}

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
                        logger.warning(f"Skipping node {nid} due to error: {e}")
                        break
                    retries += 1
                    if retries > node_config.max_retries:
                        raise RuntimeError(
                            f"Node {nid} failed after {node_config.max_retries} retries: {last_error}"
                        )

            updates: dict[str, Any] = {"iteration": iteration}

            if result:
                # Write output files to context directory
                if result.output and node_config.outputs:
                    ctx = Path(flow.context_dir)
                    for out_file in node_config.outputs:
                        (ctx / out_file).write_text(result.output, encoding="utf-8")
                    result.output_files = [
                        str(ctx / f) for f in node_config.outputs
                    ]

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

                # Multi-turn loop: ask user for input
                while True:
                    if not flow.on_interactive_input:
                        break

                    user_msg = await flow.on_interactive_input(nid, result.output)
                    if not user_msg or user_msg.strip().lower() in (
                        "done", "结束", "ok", "完成", "exit", "quit"
                    ):
                        break

                    result = await runner.run(user_msg, session_id=session_id)
                    session_id = result.session_id
                    final_output = result.output

            # Save final output
            if final_output and node_config.outputs:
                ctx = Path(flow.context_dir)
                for out_file in node_config.outputs:
                    (ctx / out_file).write_text(final_output, encoding="utf-8")

            completed = list(state.get("completed_nodes", []))
            if nid not in completed:
                completed.append(nid)

            if flow.on_node_complete:
                flow.on_node_complete(nid, NodeResult(
                    node_id=nid,
                    output=final_output,
                    output_files=node_config.outputs,
                ))

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
                        iteration = state.get("iteration", 0)
                        max_iter = state.get("max_iterations", 5)
                        # Force END if at max iterations
                        if iteration >= max_iter:
                            logger.info(
                                f"Max iterations ({max_iter}) reached, forcing END"
                            )
                            return END
                        return rm.get(route, rm.get("__default__", END))
                    return router

                graph.add_conditional_edges(source, make_router(route_map))
            else:
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

        # Validate flow definition
        errors = validate_flow(self.definition)
        if errors:
            for err in errors:
                logger.warning(f"Flow validation: {err}")

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

        # Build and compile graph
        graph = self._build_graph()

        async with AsyncSqliteSaver.from_conn_string(self.db_path) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            thread_config = {"configurable": {"thread_id": self.definition.name}}

            # Check for existing checkpoint (resume support)
            try:
                existing = await checkpointer.aget(thread_config)
                if existing and existing.get("channel_values"):
                    prev_state = existing["channel_values"]
                    # Restore state but reset current_node (was "running")
                    initial_state = {**initial_state, **prev_state}
                    initial_state["current_node"] = ""
                    logger.info(
                        f"Resuming flow '{self.definition.name}' — "
                        f"completed: {initial_state.get('completed_nodes', [])}, "
                        f"iteration: {initial_state.get('iteration', 0)}"
                    )
            except Exception as e:
                logger.debug(f"No checkpoint found, starting fresh: {e}")

            final_state = await app.ainvoke(initial_state, config=thread_config)

        if self.on_flow_complete:
            self.on_flow_complete(final_state)

        return final_state
