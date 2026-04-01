"""Tests for API helper functions (no server needed)."""

from __future__ import annotations

import pytest

from codyflow.web.api import (
    _parse_yaml_flow_data,
    _model_to_definition,
    _model_to_yaml_dict,
    FlowModel,
    NodeModel,
    EdgeModel,
)
from codyflow.engine.flow import FlowDefinition
from codyflow.nodes.base import NodeConfig


# ---------------------------------------------------------------------------
# _parse_yaml_flow_data
# ---------------------------------------------------------------------------

class TestParseYamlFlowData:
    def test_basic_parsing(self):
        data = {
            "name": "my-flow",
            "description": "A test flow",
            "runner": "claude",
            "max_iterations": 5,
            "nodes": [
                {"id": "n1", "type": "code", "prompt": "Write code"},
                {"id": "n2", "type": "reflect"},
            ],
            "edges": [
                {"from": "n1", "to": "n2"},
            ],
        }
        result = _parse_yaml_flow_data(data)
        assert result["name"] == "my-flow"
        assert result["description"] == "A test flow"
        assert result["runner"] == "claude"
        assert result["max_iterations"] == 5
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_node_defaults(self):
        data = {"nodes": [{"id": "n1"}]}
        result = _parse_yaml_flow_data(data)
        node = result["nodes"][0]
        assert node["type"] == "custom"
        assert node["prompt"] == ""
        assert node["outputs"] == []
        assert node["runner"] is None
        assert node["interactive"] is False
        assert node["error_strategy"] == "retry"
        assert node["max_retries"] == 3

    def test_ui_positions_assigned(self):
        data = {"nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
        result = _parse_yaml_flow_data(data)
        assert result["nodes"][0]["x"] == 220
        assert result["nodes"][0]["y"] == 40
        assert result["nodes"][1]["y"] == 160  # 40 + 1*120
        assert result["nodes"][2]["y"] == 280  # 40 + 2*120

    def test_edge_parsing(self):
        data = {
            "edges": [
                {"from": "a", "to": "b", "condition": "passed"},
                {"from": "a", "to": "c"},
            ]
        }
        result = _parse_yaml_flow_data(data)
        assert result["edges"][0]["from_node"] == "a"
        assert result["edges"][0]["to_node"] == "b"
        assert result["edges"][0]["condition"] == "passed"
        assert result["edges"][1]["condition"] is None

    def test_empty_data_defaults(self):
        result = _parse_yaml_flow_data({})
        assert result["name"] == "imported"
        assert result["description"] == ""
        assert result["runner"] == "cody"
        assert result["max_iterations"] == 3
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_auto_generated_node_ids(self):
        data = {"nodes": [{}, {}, {}]}  # No ids
        result = _parse_yaml_flow_data(data)
        assert result["nodes"][0]["id"] == "node_0"
        assert result["nodes"][1]["id"] == "node_1"
        assert result["nodes"][2]["id"] == "node_2"

    def test_interactive_node(self):
        data = {"nodes": [{"id": "d", "type": "discuss", "interactive": True}]}
        result = _parse_yaml_flow_data(data)
        assert result["nodes"][0]["interactive"] is True


# ---------------------------------------------------------------------------
# _model_to_definition
# ---------------------------------------------------------------------------

class TestModelToDefinition:
    def test_converts_correctly(self):
        flow = FlowModel(
            name="test",
            description="desc",
            runner="claude",
            max_iterations=3,
            nodes=[
                NodeModel(id="a", type="code", prompt="Do stuff"),
                NodeModel(id="b", type="reflect"),
            ],
            edges=[
                EdgeModel(from_node="a", to_node="b"),
            ],
        )
        defn = _model_to_definition(flow)
        assert isinstance(defn, FlowDefinition)
        assert defn.name == "test"
        assert defn.runner == "claude"
        assert len(defn.nodes) == 2
        assert isinstance(defn.nodes[0], NodeConfig)
        assert defn.nodes[0].prompt == "Do stuff"
        assert len(defn.edges) == 1
        assert defn.edges[0].from_node == "a"

    def test_preserves_node_settings(self):
        flow = FlowModel(
            name="t",
            nodes=[
                NodeModel(
                    id="n", type="custom",
                    interactive=True,
                    error_strategy="fail",
                    max_retries=1,
                    runner="claude",
                ),
            ],
        )
        defn = _model_to_definition(flow)
        nc = defn.nodes[0]
        assert nc.interactive is True
        assert nc.error_strategy == "fail"
        assert nc.max_retries == 1
        assert nc.runner == "claude"

    def test_edge_conditions(self):
        flow = FlowModel(
            name="t",
            edges=[
                EdgeModel(from_node="j", to_node="c", condition="needs_fix"),
                EdgeModel(from_node="j", to_node="END"),
            ],
        )
        defn = _model_to_definition(flow)
        assert defn.edges[0].condition == "needs_fix"
        assert defn.edges[1].condition is None


# ---------------------------------------------------------------------------
# _model_to_yaml_dict
# ---------------------------------------------------------------------------

class TestModelToYamlDict:
    def test_basic_conversion(self):
        flow = FlowModel(
            name="my-flow",
            description="A flow",
            runner="cody",
            max_iterations=5,
            nodes=[NodeModel(id="a", type="code", prompt="Do X")],
            edges=[EdgeModel(from_node="a", to_node="END")],
        )
        d = _model_to_yaml_dict(flow)
        assert d["name"] == "my-flow"
        assert d["runner"] == "cody"
        assert len(d["nodes"]) == 1
        assert d["nodes"][0]["id"] == "a"
        assert d["edges"][0]["from"] == "a"
        assert d["edges"][0]["to"] == "END"

    def test_omits_default_values(self):
        flow = FlowModel(
            name="t",
            nodes=[NodeModel(id="a", type="code")],
        )
        d = _model_to_yaml_dict(flow)
        node = d["nodes"][0]
        # Default prompt="" → None → omitted
        assert "prompt" not in node
        # Default outputs=[] → None → omitted
        assert "outputs" not in node
        # Default runner=None → omitted
        assert "runner" not in node
        # Default error_strategy="retry" → None → omitted
        assert "error_strategy" not in node
        # Default max_retries=3 → None → omitted
        assert "max_retries" not in node

    def test_preserves_non_default_values(self):
        flow = FlowModel(
            name="t",
            nodes=[NodeModel(
                id="a", type="code",
                prompt="Do something",
                interactive=True,
                error_strategy="fail",
                max_retries=1,
            )],
        )
        d = _model_to_yaml_dict(flow)
        node = d["nodes"][0]
        assert node["prompt"] == "Do something"
        assert node["interactive"] is True
        assert node["error_strategy"] == "fail"
        assert node["max_retries"] == 1

    def test_edge_condition_omitted_when_none(self):
        flow = FlowModel(
            name="t",
            edges=[EdgeModel(from_node="a", to_node="b")],
        )
        d = _model_to_yaml_dict(flow)
        assert "condition" not in d["edges"][0]
