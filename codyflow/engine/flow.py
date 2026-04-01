"""Flow engine - builds and runs LangGraph workflows from flow definitions."""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

import codyflow.nodes.builtin  # noqa: F401  — register built-in nodes
import codyflow.runners.claude_runner  # noqa: F401
import codyflow.runners.cody_runner  # noqa: F401
from codyflow.engine.logger import ExecutionLogger
from codyflow.nodes.base import FlowState, NodeConfig, NodeResult
from codyflow.nodes.registry import get_node_type
from codyflow.runners.registry import get_runner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_flow(definition: FlowDefinition) -> list[str]:
    """Validate a flow definition and return a list of error messages."""
    errors = []
    node_ids = {n.id for n in definition.nodes}

    for e in definition.edges:
        if e.from_node not in node_ids:
            errors.append(f"Edge references unknown source node '{e.from_node}'")
        if e.to_node not in node_ids and e.to_node != "END":
            errors.append(f"Edge references unknown target node '{e.to_node}'")

    targets = {e.to_node for e in definition.edges}
    start_nodes = node_ids - targets
    if not start_nodes:
        errors.append("Flow has no start node (all nodes have incoming edges)")

    edges_by_source: dict[str, list[EdgeDef]] = {}
    for e in definition.edges:
        edges_by_source.setdefault(e.from_node, []).append(e)

    for source, edges in edges_by_source.items():
        conditions = [e.condition for e in edges if e.condition]
        if len(conditions) != len(set(conditions)):
            errors.append(f"Node '{source}' has duplicate edge conditions: {conditions}")
        unconditional = [e for e in edges if not e.condition]
        if len(unconditional) > 1:
            targets = [e.to_node for e in unconditional]
            errors.append(
                f"Node '{source}' has {len(unconditional)} unconditional edges "
                f"(→ {', '.join(targets)}); only one is allowed"
            )

    for n in definition.nodes:
        if n.type == "custom" and not n.prompt:
            errors.append(f"Custom node '{n.id}' has no prompt — it will execute with an empty task")

    return errors


# ---------------------------------------------------------------------------
# Flow builder — converts FlowDefinition into a LangGraph StateGraph
# ---------------------------------------------------------------------------

class Flow:
    """Builds and executes a LangGraph workflow from a FlowDefinition."""

    def __init__(self, definition: FlowDefinition, workdir: str, runner_config: dict | None = None):
        self.definition = definition
        self.workdir = str(Path(workdir).resolve())
        self.context_dir = str(Path(self.workdir) / ".codyflow" / "context")
        self.logs_dir = str(Path(self.workdir) / ".codyflow" / "logs")
        self.db_path = str(Path(self.workdir) / ".codyflow" / "state.db")
        self.runner_config = runner_config or {}

        self._node_configs: dict[str, NodeConfig] = {
            n.id: n for n in definition.nodes
        }
        self._loop_back_targets = self._detect_loop_targets()

        self.exec_logger = ExecutionLogger(self.logs_dir)

        # Callbacks
        self.on_event: Any = None
        self.on_node_start: Any = None
        self.on_node_complete: Any = None
        self.on_flow_complete: Any = None
        self.on_interactive_input: Any = None

    def _emit(self, event: dict):
        """Emit an event to all listeners."""
        if self.on_event:
            self.on_event(event)

    def _detect_loop_targets(self) -> set[str]:
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

    def _get_runner_kwargs(self, runner_name: str) -> dict:
        """Build runner kwargs from stored config."""
        kwargs = {}
        cfg = self.runner_config
        if runner_name == "cody" and "cody" in cfg:
            cody_cfg = cfg["cody"]
            for key in ("api_key", "model", "base_url"):
                if cody_cfg.get(key):
                    kwargs[key] = cody_cfg[key]
        elif runner_name == "claude" and "claude_code" in cfg:
            claude_cfg = cfg["claude_code"]
            if claude_cfg.get("path"):
                kwargs["claude_path"] = claude_cfg["path"]
            if claude_cfg.get("model"):
                kwargs["model"] = claude_cfg["model"]
        return kwargs

    def _ensure_dirs(self):
        Path(self.context_dir).mkdir(parents=True, exist_ok=True)
        Path(self.logs_dir).mkdir(parents=True, exist_ok=True)

    def _build_node_map(self) -> list[dict[str, Any]]:
        return [
            {
                "id": nc.id,
                "type": nc.type,
                "outputs": nc.outputs,
                "prompt_summary": (nc.prompt or "")[:80],
            }
            for nc in self.definition.nodes
        ]

    # ------------------------------------------------------------------
    # Shared node execution core
    # ------------------------------------------------------------------

    async def _execute_node_core(
        self,
        node_config: NodeConfig,
        state: FlowState,
        interactive: bool = False,
    ) -> FlowState:
        """Core execution logic shared by regular and interactive nodes."""
        flow = self
        nid = node_config.id
        start_time = time.time()

        # Increment iteration on loop-back
        iteration = state.get("iteration", 0)
        if nid in flow._loop_back_targets and nid in state.get("completed_nodes", []):
            iteration += 1

        state = {**state, "current_node": nid, "iteration": iteration}

        # Build prompt
        node_cls = get_node_type(node_config.type)
        node = node_cls(node_config)
        prompt = node.build_prompt(state)

        # Emit start event
        flow._emit({
            "type": "node_start", "node_id": nid, "node_type": node_config.type,
            "iteration": iteration,
            "max_iterations": state.get("max_iterations", 5),
            "interactive": interactive,
            "timestamp": time.time(),
        })
        if flow.on_node_start:
            flow.on_node_start(nid, node_config.type)
        flow.exec_logger.log_node_start(nid, node_config.type, prompt)

        # Get runner config
        runner_name = node_config.runner or flow.definition.runner
        kwargs = flow._get_runner_kwargs(runner_name)
        if node_config.max_turns:
            kwargs["max_turns"] = node_config.max_turns

        # Execute with error handling + retry
        retries = 0
        last_error = None
        result: NodeResult | None = None

        while retries <= node_config.max_retries:
            try:
                async with get_runner(runner_name, workdir=flow.workdir, **kwargs) as runner:
                    if interactive:
                        result = await self._run_interactive(
                            node, runner, state, nid, prompt,
                        )
                    else:
                        result = await node.execute(runner, state)
                break
            except Exception as e:
                last_error = str(e)
                tb = traceback.format_exc()
                flow.exec_logger.log_node_error(nid, last_error, retries + 1, tb)
                logger.warning(f"Node {nid} failed (attempt {retries + 1}): {e}")

                flow._emit({
                    "type": "node_error", "node_id": nid,
                    "error": last_error, "attempt": retries + 1,
                    "timestamp": time.time(),
                })

                if node_config.error_strategy == "fail":
                    raise
                if node_config.error_strategy == "skip":
                    break
                retries += 1
                if retries > node_config.max_retries:
                    raise RuntimeError(
                        f"Node {nid} failed after {node_config.max_retries} retries: {last_error}"
                    ) from None

        duration = time.time() - start_time
        updates: dict[str, Any] = {"iteration": iteration}

        if result:
            # Write output files
            if result.output and node_config.outputs:
                ctx = Path(flow.context_dir)
                for out_file in node_config.outputs:
                    (ctx / out_file).write_text(result.output, encoding="utf-8")
                result.output_files = [str(ctx / f) for f in node_config.outputs]

            completed = list(state.get("completed_nodes", []))
            if nid not in completed:
                completed.append(nid)
            updates["completed_nodes"] = completed

            if "route" in result.metadata:
                updates["route"] = result.metadata["route"]

            # Log and emit
            flow.exec_logger.log_node_complete(nid, result, duration)

            complete_event: dict[str, Any] = {
                "type": "node_complete", "node_id": nid,
                "node_type": node_config.type,
                "duration": round(duration, 1),
                "output_preview": result.output[:300],
                "output_length": len(result.output),
                "output_files": result.output_files,
                "metadata": result.metadata,
                "timestamp": time.time(),
            }

            if "route" in result.metadata:
                reasoning = result.metadata.get("reasoning", "")
                complete_event["route"] = result.metadata["route"]
                complete_event["reasoning"] = reasoning
                flow.exec_logger.log_route_decision(
                    nid, result.metadata["route"], reasoning
                )

            if interactive and "turns" in result.metadata:
                complete_event["turns"] = result.metadata["turns"]

            flow._emit(complete_event)
            if flow.on_node_complete:
                flow.on_node_complete(nid, result)
        else:
            updates["last_error"] = last_error
            flow._emit({
                "type": "node_skipped", "node_id": nid,
                "error": last_error, "timestamp": time.time(),
            })

        return {**state, **updates}

    async def _run_interactive(
        self, node, runner, state: FlowState, nid: str, prompt: str,
    ) -> NodeResult:
        """Run an interactive multi-turn node."""
        result = await runner.run(prompt)
        session_id = result.session_id
        final_output = result.output
        turn_count = 1

        self._emit({
            "type": "interactive_turn", "node_id": nid,
            "turn": turn_count, "role": "assistant",
            "output_preview": result.output[:300],
            "timestamp": time.time(),
        })

        while self.on_interactive_input:
            user_msg = await self.on_interactive_input(nid, result.output)
            if not user_msg or user_msg.strip().lower() in (
                "done", "结束", "ok", "完成", "exit", "quit"
            ):
                break

            turn_count += 1
            self._emit({
                "type": "interactive_turn", "node_id": nid,
                "turn": turn_count, "role": "user",
                "timestamp": time.time(),
            })

            result = await runner.run(user_msg, session_id=session_id)
            session_id = result.session_id
            final_output = result.output

            turn_count += 1
            self._emit({
                "type": "interactive_turn", "node_id": nid,
                "turn": turn_count, "role": "assistant",
                "output_preview": result.output[:300],
                "timestamp": time.time(),
            })

        return NodeResult(
            node_id=nid, output=final_output,
            output_files=node.config.outputs,
            metadata={"turns": turn_count},
        )

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    def _make_node_fn(self, node_config: NodeConfig):
        flow = self

        # Pre-instantiate to let node __init__ apply defaults
        # (e.g. DiscussNode sets config.interactive = True)
        node_cls = get_node_type(node_config.type)
        node_cls(node_config)

        async def node_fn(state: FlowState) -> FlowState:
            return await flow._execute_node_core(
                node_config, state, interactive=node_config.interactive,
            )

        return node_fn

    def _find_start_node(self) -> str:
        targets = {e.to_node for e in self.definition.edges}
        for n in self.definition.nodes:
            if n.id not in targets:
                return n.id
        return self.definition.nodes[0].id

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(FlowState)

        for nc in self.definition.nodes:
            graph.add_node(nc.id, self._make_node_fn(nc))

        start = self._find_start_node()
        graph.set_entry_point(start)

        edges_by_source: dict[str, list[EdgeDef]] = {}
        for e in self.definition.edges:
            edges_by_source.setdefault(e.from_node, []).append(e)

        for source, edges in edges_by_source.items():
            has_conditions = any(e.condition for e in edges)

            if has_conditions:
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
                        if iteration >= max_iter:
                            logger.info(f"Max iterations ({max_iter}) reached, forcing END")
                            return END
                        return rm.get(route, rm.get("__default__", END))
                    return router

                graph.add_conditional_edges(source, make_router(route_map))
            else:
                if len(edges) > 1:
                    logger.warning(
                        f"Node '{source}' has {len(edges)} unconditional edges; "
                        f"only the first (→ {edges[0].to_node}) will be used"
                    )
                target = END if edges[0].to_node == "END" else edges[0].to_node
                graph.add_edge(source, target)

        sources_with_edges = set(edges_by_source.keys())
        for nc in self.definition.nodes:
            if nc.id not in sources_with_edges:
                graph.add_edge(nc.id, END)

        return graph

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(self, user_input: str = "") -> dict[str, Any]:
        """Execute the flow."""
        flow_start_time = time.time()
        self._ensure_dirs()

        errors = validate_flow(self.definition)
        if errors:
            for err in errors:
                logger.warning(f"Flow validation: {err}")

        input_text = user_input
        if input_text:
            Path(self.context_dir, "user_input.md").write_text(input_text, encoding="utf-8")

        self.exec_logger.log_flow_start(
            self.definition.name,
            self.definition.description or input_text,
            len(self.definition.nodes),
        )
        self._emit({
            "type": "flow_start",
            "flow_name": self.definition.name,
            "node_count": len(self.definition.nodes),
            "max_iterations": self.definition.max_iterations,
            "timestamp": time.time(),
        })

        initial_state: FlowState = {
            "flow_name": self.definition.name,
            "flow_description": self.definition.description or input_text,
            "user_message": input_text,
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
        }

        graph = self._build_graph()

        async with AsyncSqliteSaver.from_conn_string(self.db_path) as checkpointer:
            app = graph.compile(checkpointer=checkpointer)
            thread_config = {"configurable": {"thread_id": self.definition.name}}

            try:
                existing = await checkpointer.aget(thread_config)
                if existing and existing.get("channel_values"):
                    prev_state = existing["channel_values"]
                    initial_state = {**initial_state, **prev_state}
                    initial_state["current_node"] = ""
                    # Preserve current run's user input over stale checkpoint
                    if input_text:
                        initial_state["user_message"] = input_text
                        initial_state["flow_description"] = self.definition.description or input_text
                    logger.info(
                        f"Resuming flow '{self.definition.name}' — "
                        f"completed: {initial_state.get('completed_nodes', [])}, "
                        f"iteration: {initial_state.get('iteration', 0)}"
                    )
            except Exception as e:
                logger.debug(f"No checkpoint found, starting fresh: {e}")

            final_state = await app.ainvoke(initial_state, config=thread_config)

        total_duration = time.time() - flow_start_time
        completed = final_state.get("completed_nodes", [])
        iteration = final_state.get("iteration", 0)

        self.exec_logger.log_flow_complete(completed, iteration, total_duration)
        self._emit({
            "type": "flow_complete",
            "completed_nodes": completed,
            "iteration": iteration,
            "total_duration": round(total_duration, 1),
            "timestamp": time.time(),
        })

        if self.on_flow_complete:
            self.on_flow_complete(final_state)

        return final_state
