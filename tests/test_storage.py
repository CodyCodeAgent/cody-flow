"""Tests for FlowStorage CRUD operations."""

import tempfile
import os

import pytest

from codyflow.storage import FlowStorage


@pytest.fixture
def storage(tmp_path):
    """Create a FlowStorage with a temp database."""
    db_path = str(tmp_path / "test.db")
    s = FlowStorage(db_path=db_path)
    yield s
    s.close()


class TestFlowStorage:
    def test_list_empty(self, storage):
        assert storage.list_flows() == []

    def test_save_and_get(self, storage):
        definition = {"name": "test", "nodes": [], "edges": []}
        flow_id = storage.save_flow("test-flow", "A test", definition)
        assert isinstance(flow_id, int)

        flow = storage.get_flow(flow_id)
        assert flow is not None
        assert flow.name == "test-flow"
        assert flow.description == "A test"
        assert flow.definition == definition

    def test_list_flows(self, storage):
        storage.save_flow("flow-1", "", {"nodes": []})
        storage.save_flow("flow-2", "", {"nodes": []})
        flows = storage.list_flows()
        assert len(flows) == 2
        # Newest first
        assert flows[0].name == "flow-2"

    def test_update_flow(self, storage):
        fid = storage.save_flow("original", "desc", {"v": 1})
        storage.save_flow("updated", "new desc", {"v": 2}, flow_id=fid)

        flow = storage.get_flow(fid)
        assert flow.name == "updated"
        assert flow.definition == {"v": 2}

        # Should still be only 1 flow
        assert len(storage.list_flows()) == 1

    def test_delete_flow(self, storage):
        fid = storage.save_flow("to-delete", "", {})
        assert storage.delete_flow(fid) is True
        assert storage.get_flow(fid) is None
        assert len(storage.list_flows()) == 0

    def test_delete_nonexistent(self, storage):
        assert storage.delete_flow(999) is False

    def test_get_nonexistent(self, storage):
        assert storage.get_flow(999) is None

    def test_connection_reuse(self, storage):
        """Verify that _conn() returns the same connection object."""
        conn1 = storage._conn()
        conn2 = storage._conn()
        assert conn1 is conn2

    def test_close_and_reconnect(self, storage):
        storage.save_flow("test", "", {})
        storage.close()
        # After close, next call should reconnect
        flows = storage.list_flows()
        assert len(flows) == 1
