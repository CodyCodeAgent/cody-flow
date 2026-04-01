"""Tests for node and runner registries."""

import pytest

from codyflow.nodes.base import Node, NodeResult
from codyflow.nodes.registry import get_node_type, list_node_types, register_node_type
from codyflow.runners.base import Runner, RunnerResult
from codyflow.runners.registry import get_runner, list_runners, register_runner

# ---------------------------------------------------------------------------
# Node registry
# ---------------------------------------------------------------------------

class TestNodeRegistry:
    def test_builtin_types_registered(self):
        types = list_node_types()
        assert "discuss" in types
        assert "learn" in types
        assert "code" in types
        assert "reflect" in types
        assert "judge" in types
        assert "custom" in types

    def test_get_node_type_returns_class(self):
        cls = get_node_type("code")
        assert issubclass(cls, Node)

    def test_get_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown node type"):
            get_node_type("nonexistent_type_xyz")

    def test_error_message_lists_available(self):
        with pytest.raises(ValueError, match="code"):
            get_node_type("nonexistent_type_xyz")

    def test_register_custom_type(self):
        class MyNode(Node):
            node_type = "my_test_node"
            async def execute(self, runner, state):
                return NodeResult(node_id="x", output="")

        register_node_type("my_test_node", MyNode)
        assert get_node_type("my_test_node") is MyNode
        assert "my_test_node" in list_node_types()


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------

class TestRunnerRegistry:
    def test_builtin_runners_registered(self):
        runners = list_runners()
        assert "cody" in runners
        assert "claude" in runners

    def test_get_unknown_runner_raises(self):
        with pytest.raises(ValueError, match="Unknown runner"):
            get_runner("nonexistent_runner_xyz", workdir="/tmp")

    def test_register_custom_runner(self):
        class MockRunner(Runner):
            async def run(self, prompt, session_id=None):
                return RunnerResult(output="mock")

        register_runner("mock_test_runner", MockRunner)
        runner = get_runner("mock_test_runner", workdir="/tmp")
        assert isinstance(runner, MockRunner)
        assert "mock_test_runner" in list_runners()
