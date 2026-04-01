"""Base node class - all node types inherit from this."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NodeConfig:
    """Configuration for a single node in a flow."""

    id: str
    type: str
    prompt: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    runner: str | None = None  # Override global runner for this node
    max_turns: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class NodeResult:
    """Result of executing a node."""

    node_id: str
    output: str
    output_files: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Node(abc.ABC):
    """Abstract base class for all node types.

    Each node type defines:
    - A default prompt template
    - How to build the full prompt (with flow context)
    - How to handle the runner's output
    """

    # Subclasses should set these
    node_type: str = ""
    default_prompt: str = ""

    def __init__(self, config: NodeConfig):
        self.config = config
        self.prompt = config.prompt or self.default_prompt

    def build_prompt(self, flow_context: FlowContext) -> str:
        """Build the full prompt sent to the runner.

        Includes: flow overview, node status, available files, and task prompt.
        """
        sections = []

        # Section 1: Flow overview
        sections.append(f"# Flow 全貌")
        sections.append(f"名称：{flow_context.flow_name}")
        if flow_context.flow_description:
            sections.append(f"目标：{flow_context.flow_description}")

        # Section 2: Node map with status
        sections.append("\n## 节点流程")
        for i, node_info in enumerate(flow_context.all_nodes, 1):
            status = node_info["status"]
            marker = "✅ 已完成" if status == "completed" else (
                "← **你在这里**" if status == "current" else "⏳ 待执行"
            )
            outputs_str = ""
            if node_info.get("outputs"):
                outputs_str = f" → 产出: {', '.join(node_info['outputs'])}"
            sections.append(
                f"{i}. {node_info['id']} ({node_info['type']}){outputs_str} {marker}"
            )

        # Section 3: Working directory and available files
        sections.append(f"\n## 工作目录")
        sections.append(f"项目目录: {flow_context.workdir}")
        sections.append(
            f"上下文文件目录: {flow_context.context_dir}"
        )
        if flow_context.available_files:
            sections.append("\n可用的上下文文件:")
            for fpath, desc in flow_context.available_files:
                sections.append(f"- {fpath}  ({desc})")
        sections.append("\n你可以自行读取任何你需要的文件。")

        # Section 4: The actual task
        sections.append(f"\n# 你的任务")
        sections.append(self.prompt)

        # Section 5: Output instructions
        if self.config.outputs:
            sections.append(f"\n# 输出要求")
            sections.append(
                "请将你的工作产出写入以下文件（在上下文文件目录下）:"
            )
            for out_file in self.config.outputs:
                sections.append(f"- {out_file}")

        return "\n".join(sections)

    @abc.abstractmethod
    async def execute(self, runner, flow_context: FlowContext) -> NodeResult:
        """Execute this node using the given runner."""


@dataclass
class FlowContext:
    """Context information about the entire flow, passed to each node."""

    flow_name: str
    flow_description: str
    workdir: str
    context_dir: str
    all_nodes: list[dict] = field(default_factory=list)
    available_files: list[tuple[str, str]] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 5
    metadata: dict = field(default_factory=dict)
