"""Tests for ExecutionLogger."""

import json

import pytest

from codyflow.engine.logger import ExecutionLogger
from codyflow.nodes.base import NodeResult


@pytest.fixture
def logger(tmp_path):
    return ExecutionLogger(str(tmp_path))


class TestExecutionLogger:
    def test_creates_logs_dir(self, tmp_path):
        logs_dir = tmp_path / "new_logs"
        ExecutionLogger(str(logs_dir))
        assert logs_dir.exists()

    def test_run_id_is_unique(self, tmp_path):
        l1 = ExecutionLogger(str(tmp_path))
        l2 = ExecutionLogger(str(tmp_path))
        assert l1.run_id != l2.run_id

    def test_log_event_writes_jsonl(self, logger, tmp_path):
        logger.log_event({"event": "test", "data": "hello"})
        content = logger.run_log.read_text()
        lines = [line for line in content.splitlines() if line.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event"] == "test"
        assert parsed["data"] == "hello"
        assert "timestamp" in parsed
        assert "run_id" in parsed

    def test_log_node_start(self, logger, tmp_path):
        logger.log_node_start("node_1", "code", "Do something")
        # Check JSONL
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "node_start"
        assert parsed["node_id"] == "node_1"
        assert parsed["prompt_length"] == len("Do something")
        # Check prompt file
        prompt_file = tmp_path / f"{logger.run_id}_node_1_prompt.md"
        assert prompt_file.exists()
        assert prompt_file.read_text() == "Do something"

    def test_log_node_complete(self, logger, tmp_path):
        result = NodeResult(
            node_id="node_1",
            output="Result text",
            output_files=["out.md"],
            metadata={"key": "val"},
        )
        logger.log_node_complete("node_1", result, 3.14)
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "node_complete"
        assert parsed["duration_seconds"] == 3.14
        assert parsed["output_length"] == len("Result text")
        # Check output file
        output_file = tmp_path / f"{logger.run_id}_node_1_output.md"
        assert output_file.read_text() == "Result text"

    def test_log_node_error(self, logger):
        logger.log_node_error("node_1", "Connection failed", 2, "traceback...")
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "node_error"
        assert parsed["error"] == "Connection failed"
        assert parsed["attempt"] == 2

    def test_log_route_decision(self, logger):
        logger.log_route_decision("judge_1", "passed", "All good")
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "route_decision"
        assert parsed["route"] == "passed"
        assert parsed["reasoning"] == "All good"

    def test_log_flow_start(self, logger):
        logger.log_flow_start("my-flow", "Build something", 3)
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "flow_start"
        assert parsed["flow_name"] == "my-flow"
        assert parsed["node_count"] == 3

    def test_log_flow_complete(self, logger):
        logger.log_flow_complete(["a", "b"], 2, 45.67)
        content = logger.run_log.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event"] == "flow_complete"
        assert parsed["completed_nodes"] == ["a", "b"]
        assert parsed["iteration"] == 2
        assert parsed["total_duration_seconds"] == 45.67

    def test_multiple_events_appended(self, logger):
        logger.log_event({"event": "first"})
        logger.log_event({"event": "second"})
        lines = [line for line in logger.run_log.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == "first"
        assert json.loads(lines[1])["event"] == "second"
