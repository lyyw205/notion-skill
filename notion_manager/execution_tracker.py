from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator


class ExecutionTracker:
    """SQLite-based plugin execution history tracker."""

    def __init__(self, db_path: str = "data/executions.db") -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS plugin_executions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                status      TEXT NOT NULL,
                kwargs_json TEXT,
                result_json TEXT,
                error_msg   TEXT,
                duration_ms INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_exec_plugin
                ON plugin_executions(plugin_name);
            CREATE INDEX IF NOT EXISTS idx_exec_started
                ON plugin_executions(started_at);
            """
        )
        self._conn.commit()

    def start(self, plugin_name: str, kwargs: dict[str, Any] | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO plugin_executions
               (plugin_name, started_at, status, kwargs_json)
               VALUES (?, ?, 'running', ?)""",
            (plugin_name, now, json.dumps(kwargs or {})),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish(self, execution_id: int, result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = self._conn.execute(
            "SELECT started_at FROM plugin_executions WHERE id = ?",
            (execution_id,),
        ).fetchone()
        duration_ms = 0
        if row:
            started = datetime.fromisoformat(row["started_at"])
            duration_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
        self._conn.execute(
            """UPDATE plugin_executions
               SET finished_at = ?, status = 'success',
                   result_json = ?, duration_ms = ?
               WHERE id = ?""",
            (now, json.dumps(result), duration_ms, execution_id),
        )
        self._conn.commit()

    def fail(self, execution_id: int, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = self._conn.execute(
            "SELECT started_at FROM plugin_executions WHERE id = ?",
            (execution_id,),
        ).fetchone()
        duration_ms = 0
        if row:
            started = datetime.fromisoformat(row["started_at"])
            duration_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
        self._conn.execute(
            """UPDATE plugin_executions
               SET finished_at = ?, status = 'error',
                   error_msg = ?, duration_ms = ?
               WHERE id = ?""",
            (now, error, duration_ms, execution_id),
        )
        self._conn.commit()

    def get_history(
        self,
        plugin_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if plugin_name:
            rows = self._conn.execute(
                """SELECT * FROM plugin_executions
                   WHERE plugin_name = ?
                   ORDER BY started_at DESC LIMIT ? OFFSET ?""",
                (plugin_name, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM plugin_executions
                   ORDER BY started_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self, plugin_name: str) -> dict[str, Any]:
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
                 AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms END) as avg_duration_ms
               FROM plugin_executions
               WHERE plugin_name = ?""",
            (plugin_name,),
        ).fetchone()
        total = row["total"] if row else 0
        successes = row["successes"] if row else 0
        avg_dur = row["avg_duration_ms"] if row else 0
        success_rate = round(successes / total * 100, 2) if total > 0 else 0.0
        return {
            "total": total,
            "successes": successes,
            "success_rate": success_rate,
            "avg_duration_ms": round(avg_dur, 2) if avg_dur else 0,
        }

    @contextmanager
    def track(
        self, plugin_name: str, kwargs: dict[str, Any] | None = None
    ) -> Generator[dict[str, Any], None, None]:
        ctx: dict[str, Any] = {}
        exec_id = self.start(plugin_name, kwargs)
        ctx["execution_id"] = exec_id
        try:
            yield ctx
            result = ctx.get("result", {})
            self.finish(exec_id, result)
        except Exception as exc:
            self.fail(exec_id, str(exc))
            raise

    def close(self) -> None:
        self._conn.close()
