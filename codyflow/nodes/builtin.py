"""Built-in node types: discuss, learn, code, reflect, judge, custom."""

from __future__ import annotations

import logging
import re

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

    Uses multiple strategies to parse the routing decision:
    1. "ROUTE: <decision>" — explicit route marker
    2. "Decision: <decision>" / "判断: <decision>" — alternative markers
    3. Keyword detection — looks for "passed"/"通过" vs "needs_fix"/"需要修改"

    If no decision can be parsed, defaults to "needs_fix" (conservative —
    better to review again than to silently pass).

    Also extracts the reasoning text (everything after the route line)
    into metadata["reasoning"] for display in the UI.
    """

    node_type = "judge"
    default_prompt = (
        "你是判断节点。请阅读最近的反思报告，判断是否还有需要修改的问题。\n\n"
        "你的回答必须包含以下格式的决定行：\n"
        "ROUTE: needs_fix — 如果还有问题需要修改\n"
        "ROUTE: passed — 如果所有问题已解决，质量达标\n\n"
        "然后详细说明判断理由，包括：\n"
        "1. 主要发现的问题（如有）\n"
        "2. 代码质量评估\n"
        "3. 需求满足程度\n"
        "4. 做出该判断的核心原因"
    )

    # Patterns to detect route decisions (order matters — first match wins)
    _ROUTE_PATTERNS = [
        # "ROUTE: passed" / "ROUTE: needs_fix"
        re.compile(r"^\s*ROUTE\s*[:：]\s*(\S+)", re.IGNORECASE),
        # "Decision: passed" / "Decision: needs_fix"
        re.compile(r"^\s*Decision\s*[:：]\s*(\S+)", re.IGNORECASE),
        # "判断: passed" / "判断结果: needs_fix"
        re.compile(r"^\s*判断(?:结果)?\s*[:：]\s*(\S+)"),
        # "结论: passed"
        re.compile(r"^\s*结论\s*[:：]\s*(\S+)"),
    ]

    # Keywords that map to specific routes
    _PASS_KEYWORDS = {"passed", "pass", "ok", "approved", "lgtm", "通过", "达标", "合格"}
    _FIX_KEYWORDS = {"needs_fix", "fix", "failed", "reject", "需要修改", "不通过", "不合格", "需修改"}

    async def execute(self, runner, state: FlowState) -> NodeResult:
        prompt = self.build_prompt(state)
        result = await runner.run(prompt)

        route, reasoning = self._parse_route(result.output)

        return NodeResult(
            node_id=self.config.id,
            output=result.output,
            output_files=self.config.outputs,
            metadata={
                "route": route,
                "reasoning": reasoning,
            },
        )

    def _parse_route(self, output: str) -> tuple[str, str]:
        """Parse routing decision and reasoning from judge output.

        Returns (route, reasoning) tuple.
        """
        lines = output.splitlines()
        route = None
        route_line_idx = -1

        # Strategy 1: Look for explicit route markers
        for i, line in enumerate(lines):
            for pattern in self._ROUTE_PATTERNS:
                m = pattern.match(line)
                if m:
                    raw = m.group(1).strip().lower().rstrip(".,;!。，；！")
                    route = self._normalize_route(raw)
                    route_line_idx = i
                    break
            if route is not None:
                break

        # Strategy 2: Keyword detection in full output (fallback)
        if route is None:
            output_lower = output.lower()
            has_pass = any(kw in output_lower for kw in self._PASS_KEYWORDS)
            has_fix = any(kw in output_lower for kw in self._FIX_KEYWORDS)

            if has_pass and not has_fix:
                route = "passed"
            elif has_fix and not has_pass:
                route = "needs_fix"
            elif has_fix and has_pass:
                # Both present — conservative: needs_fix
                route = "needs_fix"
                logger.info(
                    f"Judge '{self.config.id}' output contains both pass and fix keywords, "
                    f"defaulting to 'needs_fix'"
                )
            else:
                route = "needs_fix"
                logger.warning(
                    f"Judge '{self.config.id}' could not parse route from output, "
                    f"defaulting to 'needs_fix'"
                )

        # Extract reasoning — everything after the route line, or full output if no marker
        if route_line_idx >= 0:
            reasoning_lines = lines[route_line_idx + 1:]
            reasoning = "\n".join(reasoning_lines).strip()
        else:
            # No explicit marker found — use entire output as reasoning
            reasoning = output.strip()

        # Truncate reasoning to a reasonable length for metadata
        if len(reasoning) > 1000:
            reasoning = reasoning[:1000] + "..."

        return route, reasoning

    def _normalize_route(self, raw: str) -> str:
        """Normalize a raw route string to a canonical form."""
        if raw in self._PASS_KEYWORDS:
            return "passed"
        if raw in self._FIX_KEYWORDS:
            return "needs_fix"
        # Return as-is for custom routes (user-defined conditions)
        return raw


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
