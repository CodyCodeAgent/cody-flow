"""SQLite storage for flow definitions and run history."""

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
    definition: dict[str, Any]  # full flow JSON including nodes, edges, UI positions
    created_at: float
    updated_at: float


class FlowStorage:
    """SQLite-backed storage for flow definitions."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path.home() / ".codyflow" / "codyflow.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
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

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

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
