"""Tests for flow engine internals (no actual AI execution)."""

from __future__ import annotations

import pytest

from codyflow.engine.flow import Flow, FlowDefinition, EdgeDef
from codyflow.nodes.base import NodeConfig


def _make_definition(**overrides) -> FlowDefinition:
    defaults = {
        "name": "test-flow",
        "description": "Test",
        "runner": "cody",
        "max_iterations": 5,
        "nodes": [],
        "edges": [],
    }
    defaults.update(overrides)
    return FlowDefinition(**defaults)


# ---------------------------------------------------------------------------
# _detect_loop_targets
# ---------------------------------------------------------------------------

class TestDetectLoopTargets:
    def test_no_loops(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [EdgeDef(from_node="a", to_node="b")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert flow._loop_back_targets == set()

    def test_detects_backward_edge(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
            NodeConfig(id="c", type="judge"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b"),
            EdgeDef(from_node="b", to_node="c"),
            EdgeDef(from_node="c", to_node="a", condition="needs_fix"),
        ]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert "a" in flow._loop_back_targets

    def test_self_loop(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="a", to_node="a")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert "a" in flow._loop_back_targets

    def test_end_edge_ignored(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="a", to_node="END")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert flow._loop_back_targets == set()


# ---------------------------------------------------------------------------
# _find_start_node
# ---------------------------------------------------------------------------

class TestFindStartNode:
    def test_single_node(self):
        nodes = [NodeConfig(id="only", type="code")]
        defn = _make_definition(nodes=nodes)
        flow = Flow(defn, workdir="/tmp")
        assert flow._find_start_node() == "only"

    def test_linear_chain(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
            NodeConfig(id="c", type="judge"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b"),
            EdgeDef(from_node="b", to_node="c"),
        ]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert flow._find_start_node() == "a"

    def test_all_have_incoming_falls_back_to_first(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b"),
            EdgeDef(from_node="b", to_node="a"),
        ]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        assert flow._find_start_node() == "a"


# ---------------------------------------------------------------------------
# _get_runner_kwargs
# ---------------------------------------------------------------------------

class TestGetRunnerKwargs:
    def test_cody_runner_kwargs(self):
        defn = _make_definition()
        flow = Flow(defn, workdir="/tmp", runner_config={
            "cody": {"api_key": "sk-123", "model": "claude-sonnet-4-6", "base_url": "https://api.example.com"}
        })
        kwargs = flow._get_runner_kwargs("cody")
        assert kwargs["api_key"] == "sk-123"
        assert kwargs["model"] == "claude-sonnet-4-6"
        assert kwargs["base_url"] == "https://api.example.com"

    def test_claude_runner_kwargs(self):
        defn = _make_definition()
        flow = Flow(defn, workdir="/tmp", runner_config={
            "claude_code": {"path": "/usr/bin/claude", "model": "claude-opus-4-6"}
        })
        kwargs = flow._get_runner_kwargs("claude")
        assert kwargs["claude_path"] == "/usr/bin/claude"
        assert kwargs["model"] == "claude-opus-4-6"

    def test_empty_config(self):
        defn = _make_definition()
        flow = Flow(defn, workdir="/tmp", runner_config={})
        assert flow._get_runner_kwargs("cody") == {}
        assert flow._get_runner_kwargs("claude") == {}

    def test_empty_values_skipped(self):
        defn = _make_definition()
        flow = Flow(defn, workdir="/tmp", runner_config={
            "cody": {"api_key": "", "model": "claude-sonnet-4-6"}
        })
        kwargs = flow._get_runner_kwargs("cody")
        assert "api_key" not in kwargs
        assert kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# _make_node_fn — DiscussNode pre-instantiation
# ---------------------------------------------------------------------------

class TestMakeNodeFn:
    def test_discuss_node_config_mutated_to_interactive(self):
        """Bug 1 regression: DiscussNode should set config.interactive=True
        during _make_node_fn, before the closure reads it."""
        nodes = [NodeConfig(id="d", type="discuss")]
        edges = []
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")

        # After _make_node_fn, the config should have interactive=True
        flow._make_node_fn(nodes[0])
        assert nodes[0].interactive is True

    def test_code_node_stays_non_interactive(self):
        nodes = [NodeConfig(id="c", type="code")]
        defn = _make_definition(nodes=nodes)
        flow = Flow(defn, workdir="/tmp")
        flow._make_node_fn(nodes[0])
        assert nodes[0].interactive is False


# ---------------------------------------------------------------------------
# _build_node_map
# ---------------------------------------------------------------------------

class TestBuildNodeMap:
    def test_returns_correct_structure(self):
        nodes = [
            NodeConfig(id="a", type="code", prompt="Do something", outputs=["out.md"]),
            NodeConfig(id="b", type="reflect"),
        ]
        defn = _make_definition(nodes=nodes)
        flow = Flow(defn, workdir="/tmp")
        node_map = flow._build_node_map()

        assert len(node_map) == 2
        assert node_map[0]["id"] == "a"
        assert node_map[0]["type"] == "code"
        assert node_map[0]["outputs"] == ["out.md"]
        assert node_map[1]["id"] == "b"

    def test_prompt_summary_truncated(self):
        long_prompt = "x" * 200
        nodes = [NodeConfig(id="a", type="code", prompt=long_prompt)]
        defn = _make_definition(nodes=nodes)
        flow = Flow(defn, workdir="/tmp")
        node_map = flow._build_node_map()
        assert len(node_map[0]["prompt_summary"]) == 80


# ---------------------------------------------------------------------------
# _build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_builds_linear_graph(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [EdgeDef(from_node="a", to_node="b")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        graph = flow._build_graph()
        # Should compile without error
        graph.compile()

    def test_builds_conditional_graph(self):
        nodes = [
            NodeConfig(id="code", type="code"),
            NodeConfig(id="judge", type="judge"),
            NodeConfig(id="done", type="custom", prompt="done"),
        ]
        edges = [
            EdgeDef(from_node="code", to_node="judge"),
            EdgeDef(from_node="judge", to_node="code", condition="needs_fix"),
            EdgeDef(from_node="judge", to_node="done", condition="passed"),
        ]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        graph = flow._build_graph()
        graph.compile()

    def test_node_without_outgoing_edge_goes_to_end(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [EdgeDef(from_node="a", to_node="b")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        # b has no outgoing edge, should auto-connect to END
        graph = flow._build_graph()
        graph.compile()

    def test_explicit_end_edge(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="a", to_node="END")]
        defn = _make_definition(nodes=nodes, edges=edges)
        flow = Flow(defn, workdir="/tmp")
        graph = flow._build_graph()
        graph.compile()
