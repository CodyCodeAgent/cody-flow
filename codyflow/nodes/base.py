"""Base node class and flow state definitions for LangGraph integration."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# LangGraph shared state
# ---------------------------------------------------------------------------

class FlowState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    # Flow metadata
    flow_name: str
    flow_description: str
    workdir: str
    context_dir: str

    # Node map: [{id, type, status, outputs, prompt_summary}, ...]
    node_map: list[dict[str, Any]]

    # Execution tracking
    current_node: str
    completed_nodes: list[str]
    iteration: int
    max_iterations: int

    # Routing (set by judge-type nodes)
    route: str

    # Error tracking
    last_error: str | None

    # Interactive node state
    waiting_for_user: bool
    user_message: str


# ---------------------------------------------------------------------------
# Node configuration
# ---------------------------------------------------------------------------

@dataclass
class NodeConfig:
    """Configuration for a single node in a flow."""

    id: str
    type: str
    prompt: str = ""
    outputs: list[str] = field(default_factory=list)
    runner: str | None = None
    max_turns: int | None = None
    interactive: bool = False
    error_strategy: str = "retry"  # retry | skip | fail
    max_retries: int = 3
    extra: dict = field(default_factory=dict)


@dataclass
class NodeResult:
    """Result of executing a node."""

    node_id: str
    output: str
    output_files: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base node class
# ---------------------------------------------------------------------------

class Node(abc.ABC):
    """Abstract base class for all node types."""

    node_type: str = ""
    default_prompt: str = ""

    def __init__(self, config: NodeConfig):
        self.config = config
        self.prompt = config.prompt or self.default_prompt

    def build_prompt(self, state: FlowState) -> str:
        """Build the full prompt with flow panorama."""
        sections = []

        # Section 1: Flow overview
        sections.append("# Flow 全貌")
        sections.append(f"名称：{state['flow_name']}")
        if state.get("flow_description"):
            sections.append(f"目标：{state['flow_description']}")
        if state.get("user_message"):
            sections.append(f"\n## 用户需求\n{state['user_message']}")

        # Section 2: Node map with status
        sections.append("\n## 节点流程")
        completed = set(state.get("completed_nodes", []))
        current = state.get("current_node", "")
        for i, node_info in enumerate(state.get("node_map", []), 1):
            nid = node_info["id"]
            if nid in completed:
                marker = "✅ 已完成"
            elif nid == current:
                marker = "← **你在这里**"
            else:
                marker = "⏳ 待执行"
            outputs_str = ""
            if node_info.get("outputs"):
                outputs_str = f" → 产出: {', '.join(node_info['outputs'])}"
            sections.append(
                f"{i}. {nid} ({node_info['type']}){outputs_str} {marker}"
            )

        # Section 3: Working directory and available context files
        context_dir = state.get("context_dir", "")
        sections.append("\n## 工作目录")
        sections.append(f"项目目录: {state['workdir']}")
        sections.append(f"上下文文件目录: {context_dir}")

        if context_dir:
            ctx_path = Path(context_dir)
            if ctx_path.exists():
                files = sorted(ctx_path.iterdir())
                context_files = [f for f in files if f.is_file()]
                if context_files:
                    sections.append("\n可用的上下文文件:")
                    node_map = state.get("node_map", [])
                    for f in context_files:
                        producer = "用户输入" if f.name == "user_input.md" else "未知"
                        for nm in node_map:
                            if f.name in nm.get("outputs", []):
                                producer = f"{nm['id']} ({nm['type']})"
                                break
                        sections.append(f"- {f.name}  (来自: {producer})")

        sections.append("\n你可以自行读取任何你需要的文件来了解上下文。")

        # Section 4: Iteration info (if in a loop)
        iteration = state.get("iteration", 0)
        if iteration > 0:
            max_iter = state.get("max_iterations", 5)
            sections.append("\n## 迭代信息")
            sections.append(f"当前是第 {iteration + 1} 轮迭代（最多 {max_iter} 轮）")

        # Section 5: The actual task
        sections.append("\n# 你的任务")
        sections.append(self.prompt)

        # Section 6: Output file instructions
        if self.config.outputs:
            sections.append("\n# 输出要求")
            sections.append(
                "请将你的工作产出（总结/报告）写入以下文件（在上下文文件目录下）:"
            )
            for out_file in self.config.outputs:
                sections.append(f"- {out_file}")

        return "\n".join(sections)

    @abc.abstractmethod
    async def execute(self, runner, state: FlowState) -> NodeResult:
        """Execute this node using the given runner and shared state."""
