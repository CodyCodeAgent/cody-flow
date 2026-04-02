"""SQLite storage for flow definitions and tasks."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FlowRecord:
    """A saved flow definition."""
    id: int
    name: str
    description: str
    definition: dict[str, Any]
    created_at: float
    updated_at: float


@dataclass
class TaskRecord:
    """A task instance — a flow run with specific inputs."""
    id: str
    flow_id: int | None
    flow_name: str
    flow_snapshot: dict[str, Any]  # full flow definition at time of run
    workdir: str
    user_input: str
    status: str   # running | completed | failed | stopped
    created_at: float
    updated_at: float
    log_path: str


class FlowStorage:
    """SQLite-backed storage for flow definitions and tasks."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path.home() / ".codyflow" / "codyflow.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    definition TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    flow_id INTEGER,
                    flow_name TEXT NOT NULL,
                    flow_snapshot TEXT NOT NULL,
                    workdir TEXT NOT NULL,
                    user_input TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    log_path TEXT NOT NULL
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
        return self._connection

    def close(self):
        """Close the persistent connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def list_flows(self) -> list[FlowRecord]:
        """List all saved flows, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, name, description, definition, created_at, updated_at "
                "FROM flows ORDER BY updated_at DESC"
            ).fetchall()
        return [
            FlowRecord(
                id=r[0], name=r[1], description=r[2],
                definition=json.loads(r[3]),
                created_at=r[4], updated_at=r[5],
            )
            for r in rows
        ]

    def get_flow(self, flow_id: int) -> FlowRecord | None:
        """Get a single flow by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, name, description, definition, created_at, updated_at "
                "FROM flows WHERE id = ?", (flow_id,)
            ).fetchone()
        if not row:
            return None
        return FlowRecord(
            id=row[0], name=row[1], description=row[2],
            definition=json.loads(row[3]),
            created_at=row[4], updated_at=row[5],
        )

    def save_flow(self, name: str, description: str, definition: dict, flow_id: int | None = None) -> int:
        """Save a flow. If flow_id is given, update; otherwise insert.

        Returns the flow ID.
        """
        now = time.time()
        def_json = json.dumps(definition, ensure_ascii=False)

        with self._conn() as conn:
            if flow_id is not None:
                conn.execute(
                    "UPDATE flows SET name=?, description=?, definition=?, updated_at=? "
                    "WHERE id=?",
                    (name, description, def_json, now, flow_id),
                )
                return flow_id
            else:
                cursor = conn.execute(
                    "INSERT INTO flows (name, description, definition, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (name, description, def_json, now, now),
                )
                return cursor.lastrowid

    def delete_flow(self, flow_id: int) -> bool:
        """Delete a flow. Returns True if deleted."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM flows WHERE id = ?", (flow_id,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # Task CRUD
    # -------------------------------------------------------------------------

    def create_task(
        self,
        task_id: str,
        flow_id: int | None,
        flow_name: str,
        flow_snapshot: dict,
        workdir: str,
        user_input: str,
        log_path: str,
    ) -> TaskRecord:
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tasks (id, flow_id, flow_name, flow_snapshot, workdir, "
                "user_input, status, created_at, updated_at, log_path) "
                "VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)",
                (task_id, flow_id, flow_name, json.dumps(flow_snapshot, ensure_ascii=False),
                 workdir, user_input, now, now, log_path),
            )
        return TaskRecord(
            id=task_id, flow_id=flow_id, flow_name=flow_name,
            flow_snapshot=flow_snapshot, workdir=workdir, user_input=user_input,
            status="running", created_at=now, updated_at=now, log_path=log_path,
        )

    def update_task_status(self, task_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), task_id),
            )

    def list_tasks(self) -> list[TaskRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, flow_id, flow_name, flow_snapshot, workdir, user_input, "
                "status, created_at, updated_at, log_path FROM tasks ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, flow_id, flow_name, flow_snapshot, workdir, user_input, "
                "status, created_at, updated_at, log_path FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row else None

    def delete_task(self, task_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_task(row) -> TaskRecord:
        return TaskRecord(
            id=row[0], flow_id=row[1], flow_name=row[2],
            flow_snapshot=json.loads(row[3]),
            workdir=row[4], user_input=row[5], status=row[6],
            created_at=row[7], updated_at=row[8], log_path=row[9],
        )
