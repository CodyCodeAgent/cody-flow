"""Tests for flow validation logic."""

import pytest

from codyflow.engine.flow import FlowDefinition, EdgeDef, validate_flow
from codyflow.nodes.base import NodeConfig


def _make_flow(nodes=None, edges=None, **kwargs):
    return FlowDefinition(
        name="test",
        nodes=nodes or [],
        edges=edges or [],
        **kwargs,
    )


class TestValidateFlow:
    def test_valid_linear_flow(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [EdgeDef(from_node="a", to_node="b")]
        errors = validate_flow(_make_flow(nodes, edges))
        assert errors == []

    def test_unknown_source_node(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="missing", to_node="a")]
        errors = validate_flow(_make_flow(nodes, edges))
        assert any("unknown source" in e for e in errors)

    def test_unknown_target_node(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="a", to_node="missing")]
        errors = validate_flow(_make_flow(nodes, edges))
        assert any("unknown target" in e for e in errors)

    def test_end_target_is_valid(self):
        nodes = [NodeConfig(id="a", type="code")]
        edges = [EdgeDef(from_node="a", to_node="END")]
        errors = validate_flow(_make_flow(nodes, edges))
        assert errors == []

    def test_no_start_node(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="reflect"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b"),
            EdgeDef(from_node="b", to_node="a"),
        ]
        errors = validate_flow(_make_flow(nodes, edges))
        assert any("no start node" in e for e in errors)

    def test_duplicate_edge_conditions(self):
        nodes = [
            NodeConfig(id="a", type="judge"),
            NodeConfig(id="b", type="code"),
            NodeConfig(id="c", type="code"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b", condition="passed"),
            EdgeDef(from_node="a", to_node="c", condition="passed"),
        ]
        errors = validate_flow(_make_flow(nodes, edges))
        assert any("duplicate edge conditions" in e for e in errors)

    def test_custom_node_without_prompt(self):
        nodes = [NodeConfig(id="a", type="custom", prompt="")]
        errors = validate_flow(_make_flow(nodes))
        assert any("no prompt" in e for e in errors)

    def test_custom_node_with_prompt_is_ok(self):
        nodes = [NodeConfig(id="a", type="custom", prompt="Do something")]
        errors = validate_flow(_make_flow(nodes))
        # Should not complain about prompt
        assert not any("no prompt" in e for e in errors)

    def test_multiple_unconditional_edges(self):
        nodes = [
            NodeConfig(id="a", type="code"),
            NodeConfig(id="b", type="code"),
            NodeConfig(id="c", type="code"),
        ]
        edges = [
            EdgeDef(from_node="a", to_node="b"),
            EdgeDef(from_node="a", to_node="c"),
        ]
        errors = validate_flow(_make_flow(nodes, edges))
        assert any("unconditional edges" in e for e in errors)

    def test_empty_flow(self):
        errors = validate_flow(_make_flow())
        # No nodes, no edges — no start node error
        assert any("no start node" in e for e in errors)
