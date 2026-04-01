"""Tests for node base classes, built-in nodes, and prompt building."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from codyflow.nodes.base import FlowState, Node, NodeConfig, NodeResult
from codyflow.nodes.builtin import (
    SimpleNode, DiscussNode, LearnNode, CodeNode,
    ReflectNode, JudgeNode, CustomNode,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> FlowState:
    base: FlowState = {
        "flow_name": "test-flow",
        "flow_description": "Test description",
        "user_message": "",
        "workdir": "/tmp/test",
        "context_dir": "/tmp/test/.codyflow/context",
        "node_map": [
            {"id": "n1", "type": "code", "outputs": ["out.md"], "prompt_summary": ""},
            {"id": "n2", "type": "reflect", "outputs": [], "prompt_summary": ""},
        ],
        "current_node": "n1",
        "completed_nodes": [],
        "iteration": 0,
        "max_iterations": 5,
        "route": "",
        "last_error": None,
        "waiting_for_user": False,
    }
    base.update(overrides)
    return base


def _make_config(**overrides) -> NodeConfig:
    defaults = {"id": "test_node", "type": "code"}
    defaults.update(overrides)
    return NodeConfig(**defaults)


# ---------------------------------------------------------------------------
# build_prompt tests
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_includes_flow_name(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state())
        assert "test-flow" in prompt

    def test_includes_flow_description(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(flow_description="Build a widget"))
        assert "Build a widget" in prompt

    def test_includes_user_message_section(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(user_message="Fix the login bug"))
        assert "用户需求" in prompt
        assert "Fix the login bug" in prompt

    def test_no_user_message_section_when_empty(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(user_message=""))
        assert "用户需求" not in prompt

    def test_includes_node_map_with_status(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(
            current_node="n1",
            completed_nodes=["n2"],
        ))
        assert "你在这里" in prompt
        assert "已完成" in prompt

    def test_includes_task_prompt(self):
        cfg = _make_config(prompt="Please write clean code")
        node = CodeNode(cfg)
        prompt = node.build_prompt(_make_state())
        assert "Please write clean code" in prompt

    def test_uses_default_prompt_when_no_custom(self):
        cfg = _make_config(prompt="")
        node = CodeNode(cfg)
        prompt = node.build_prompt(_make_state())
        assert "写代码节点" in prompt

    def test_includes_output_requirements(self):
        cfg = _make_config(outputs=["result.md", "summary.md"])
        node = CodeNode(cfg)
        prompt = node.build_prompt(_make_state())
        assert "result.md" in prompt
        assert "summary.md" in prompt

    def test_no_output_section_when_empty(self):
        cfg = _make_config(outputs=[])
        node = CodeNode(cfg)
        prompt = node.build_prompt(_make_state())
        assert "输出要求" not in prompt

    def test_includes_iteration_info(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(iteration=2, max_iterations=5))
        assert "第 3 轮迭代" in prompt
        assert "最多 5 轮" in prompt

    def test_no_iteration_info_at_zero(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(iteration=0))
        assert "迭代信息" not in prompt

    def test_includes_workdir(self):
        node = CodeNode(_make_config())
        prompt = node.build_prompt(_make_state(workdir="/my/project"))
        assert "/my/project" in prompt


# ---------------------------------------------------------------------------
# SimpleNode tests
# ---------------------------------------------------------------------------

class TestSimpleNode:
    @pytest.mark.asyncio
    async def test_execute_calls_runner(self):
        cfg = _make_config(prompt="Do something")
        node = CodeNode(cfg)

        mock_runner = AsyncMock()
        mock_runner.run.return_value = MagicMock(output="Done!", session_id=None)

        result = await node.execute(mock_runner, _make_state())
        assert result.output == "Done!"
        assert result.node_id == "test_node"
        mock_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_passes_built_prompt(self):
        cfg = _make_config(prompt="Custom task")
        node = CodeNode(cfg)

        mock_runner = AsyncMock()
        mock_runner.run.return_value = MagicMock(output="ok", session_id=None)

        await node.execute(mock_runner, _make_state())
        prompt_arg = mock_runner.run.call_args[0][0]
        assert "Custom task" in prompt_arg

    @pytest.mark.asyncio
    async def test_execute_sets_output_files(self):
        cfg = _make_config(outputs=["report.md"])
        node = CodeNode(cfg)

        mock_runner = AsyncMock()
        mock_runner.run.return_value = MagicMock(output="report content", session_id=None)

        result = await node.execute(mock_runner, _make_state())
        assert result.output_files == ["report.md"]


# ---------------------------------------------------------------------------
# DiscussNode tests
# ---------------------------------------------------------------------------

class TestDiscussNode:
    def test_defaults_to_interactive(self):
        cfg = _make_config(type="discuss")
        node = DiscussNode(cfg)
        assert cfg.interactive is True

    def test_explicit_non_interactive(self):
        cfg = _make_config(type="discuss", extra={"_interactive_explicit": True})
        cfg.interactive = False
        node = DiscussNode(cfg)
        assert cfg.interactive is False

    def test_has_default_prompt(self):
        cfg = _make_config(type="discuss", prompt="")
        node = DiscussNode(cfg)
        assert "讨论节点" in node.prompt


# ---------------------------------------------------------------------------
# CustomNode tests
# ---------------------------------------------------------------------------

class TestCustomNode:
    @pytest.mark.asyncio
    async def test_warns_on_empty_prompt(self, caplog):
        cfg = _make_config(type="custom", prompt="")
        node = CustomNode(cfg)

        mock_runner = AsyncMock()
        mock_runner.run.return_value = MagicMock(output="ok", session_id=None)

        import logging
        with caplog.at_level(logging.WARNING):
            await node.execute(mock_runner, _make_state())
        assert any("no prompt" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_no_warning_with_prompt(self, caplog):
        cfg = _make_config(type="custom", prompt="Do X")
        node = CustomNode(cfg)

        mock_runner = AsyncMock()
        mock_runner.run.return_value = MagicMock(output="ok", session_id=None)

        import logging
        with caplog.at_level(logging.WARNING):
            await node.execute(mock_runner, _make_state())
        assert not any("no prompt" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Node type identity tests
# ---------------------------------------------------------------------------

class TestNodeTypes:
    def test_learn_node_type(self):
        assert LearnNode.node_type == "learn"

    def test_code_node_type(self):
        assert CodeNode.node_type == "code"

    def test_reflect_node_type(self):
        assert ReflectNode.node_type == "reflect"

    def test_judge_node_type(self):
        assert JudgeNode.node_type == "judge"

    def test_custom_node_type(self):
        assert CustomNode.node_type == "custom"

    def test_discuss_node_type(self):
        assert DiscussNode.node_type == "discuss"

    def test_all_have_default_prompts(self):
        for cls in [DiscussNode, LearnNode, CodeNode, ReflectNode, JudgeNode]:
            assert cls.default_prompt, f"{cls.__name__} has no default_prompt"

    def test_custom_has_empty_default_prompt(self):
        assert CustomNode.default_prompt == ""
