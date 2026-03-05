from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class Cache:
    """SQLite-backed key/value cache with per-entry TTL."""

    def __init__(self, db_path: str = ".cache/notion_manager.db") -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key       TEXT PRIMARY KEY,
                    value     TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_hours  REAL NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        """Return cached value if present and not expired, else None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, created_at, ttl_hours FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        age_hours = (time.time() - row["created_at"]) / 3600.0
        if age_hours > row["ttl_hours"]:
            return None
        return json.loads(row["value"])

    def set(self, key: str, value: Any, ttl_hours: float = 24.0) -> None:
        """Store value under key with a TTL in hours."""
        serialized = json.dumps(value)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache (key, value, created_at, ttl_hours)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    created_at = excluded.created_at,
                    ttl_hours  = excluded.ttl_hours
                """,
                (key, serialized, now, ttl_hours),
            )
            conn.commit()

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache."""
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    def clear_expired(self) -> int:
        """Delete all expired entries. Returns number of rows removed."""
        now = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE (? - created_at) / 3600.0 > ttl_hours",
                (now,),
            )
            conn.commit()
            return cursor.rowcount
