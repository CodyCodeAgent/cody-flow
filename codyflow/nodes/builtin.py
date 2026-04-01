"""Built-in node types: discuss, learn, code, reflect, judge, custom."""

from __future__ import annotations

from codyflow.nodes.base import FlowState, Node, NodeConfig, NodeResult
from codyflow.nodes.registry import register_node_type


class DiscussNode(Node):
    """Discussion node - interactive multi-turn analysis with user."""

    node_type = "discuss"
    default_prompt = (
        "你是讨论节点。请根据用户的需求进行深入分析和讨论。\n"
        "分析需求的可行性、技术方案、潜在风险和建议的实现路径。\n"
        "与用户进行多轮对话，直到用户确认讨论结束。\n"
        "最终产出一份清晰的讨论结论文档。"
    )

    def __init__(self, config: NodeConfig):
        # 讨论节点默认开启交互模式
        config.interactive = config.interactive or True
        super().__init__(config)

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)

        # 交互模式：使用 session_id 支持多轮对话
        user_msg = state.get("user_message", "")
        session_id = state.get("_discuss_session_id")

        if user_msg and session_id:
            # 后续轮次：用户追加消息
            result = await runner.run(user_msg, session_id=session_id)
        else:
            # 首轮：发送完整 prompt
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
    """Judge node - decides routing based on upstream output."""

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

        # Parse routing decision from output
        route = "passed"
        for line in result.output.splitlines():
            stripped = line.strip()
            if stripped.startswith("ROUTE:"):
                route = stripped.split(":", 1)[1].strip().split()[0]
                break

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
    """

    node_type = "custom"
    default_prompt = ""

    async def execute(self, runner, state: FlowState) -> NodeResult:
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
