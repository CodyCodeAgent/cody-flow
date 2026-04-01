"""Built-in node types: discuss, learn, code, reflect, judge, custom."""

from __future__ import annotations

import logging

from codyflow.nodes.base import FlowState, Node, NodeConfig, NodeResult
from codyflow.nodes.registry import register_node_type

logger = logging.getLogger(__name__)


class DiscussNode(Node):
    """Discussion node - interactive multi-turn analysis with user.

    This node defaults to interactive mode. The flow engine handles
    multi-turn conversation via session_id; the node itself only needs
    to build prompts and execute single turns.
    """

    node_type = "discuss"
    default_prompt = (
        "你是讨论节点。请根据用户的需求进行深入分析和讨论。\n"
        "分析需求的可行性、技术方案、潜在风险和建议的实现路径。\n"
        "与用户进行多轮对话，直到用户确认讨论结束。\n"
        "最终产出一份清晰的讨论结论文档。"
    )
    default_interactive = True

    def __init__(self, config: NodeConfig):
        super().__init__(config)
        # Discuss nodes default to interactive unless explicitly set to False
        if not config.extra.get("_interactive_explicit"):
            config.interactive = True

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)
        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
            metadata={"session_id": result.session_id},
        )


class LearnNode(Node):
    """Learning node - studies the project codebase and tech stack."""

    node_type = "learn"
    default_prompt = (
        "你是学习节点。请浏览并学习当前项目的代码结构、技术栈、"
        "编码风格和架构模式。\n"
        "重点关注：目录结构、核心模块、依赖关系、配置文件。\n"
        "产出一份项目知识摘要文档。"
    )

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)
        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
        )


class CodeNode(Node):
    """Coding node - writes or modifies code based on context."""

    node_type = "code"
    default_prompt = (
        "你是写代码节点。请根据前序节点提供的讨论结论、学习成果"
        "以及可能的反思报告来编写或修改代码。\n"
        "你可以直接修改项目源码文件。\n"
        "确保代码质量高、符合项目现有风格、并满足需求。\n"
        "完成后，产出一份代码变更总结文档。"
    )

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)
        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
        )


class ReflectNode(Node):
    """Reflection node - reviews work and identifies issues."""

    node_type = "reflect"
    default_prompt = (
        "你是反思节点。请仔细检查前序节点完成的工作，特别是代码变更。\n"
        "你可以使用 git diff 或直接查看文件来了解变更内容。\n"
        "对照最初的需求，检查以下方面：\n"
        "1. 功能是否完整实现\n"
        "2. 代码质量和风格是否符合项目标准\n"
        "3. 是否存在 bug 或潜在问题\n"
        "4. 是否有遗漏的边界情况\n"
        "5. 是否符合最初讨论确定的方案\n"
        "产出一份详细的反思报告，明确列出发现的问题和改进建议。"
    )

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)
        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
        )


class JudgeNode(Node):
    """Judge node - decides routing based on upstream output.

    The AI must output a line starting with "ROUTE: <decision>".
    If no ROUTE line is found, defaults to "needs_fix" (conservative —
    better to review again than to silently pass).
    """

    node_type = "judge"
    default_prompt = (
        "你是判断节点。请阅读最近的反思报告，判断是否还有需要修改的问题。\n"
        "你的回答必须以下面两种格式之一开头：\n"
        "ROUTE: needs_fix — 如果还有问题需要修改\n"
        "ROUTE: passed — 如果所有问题已解决，质量达标\n"
        "然后简要说明判断理由。"
    )

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)

        # Parse routing decision — default to needs_fix (conservative)
        route = "needs_fix"
        for line in result.output.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("ROUTE:"):
                raw_route = stripped.split(":", 1)[1].strip().split()[0].lower()
                route = raw_route
                break
        else:
            logger.warning(
                f"Judge node '{self.config.id}' did not output a ROUTE line, "
                f"defaulting to 'needs_fix'"
            )

        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
            metadata={"route": route},
        )


class CustomNode(Node):
    """Custom node - user-defined behavior via prompt.

    Can be used to create any kind of node: pause, user-input,
    API call, testing, deployment, etc.
    Set interactive: true in YAML for multi-turn conversation.
    """

    node_type = "custom"
    default_prompt = ""

    async def execute(self, runner, state: FlowState) -> NodeResult:
        if not self.prompt:
            logger.warning(
                f"Custom node '{self.config.id}' has no prompt — "
                f"executing with empty task"
            )
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)
        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
        )


# Register all built-in node types
for cls in [DiscussNode, LearnNode, CodeNode, ReflectNode, JudgeNode, CustomNode]:
    register_node_type(cls.node_type, cls)
