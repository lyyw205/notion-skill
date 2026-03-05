from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class ChangelogTrackerPlugin:
    name = "changelog_tracker"
    description = "워크스페이스 변경사항 diff + SQLite 스냅샷"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        db_path: str = kwargs.get("db_path") or config.get("changelog", {}).get("db_path", "changelog.db")

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": str(exc)}

        current: dict[str, dict[str, str]] = {}
        for page in pages:
            pid = page.get("id", "")
            title = _extract_title(page)
            last_edited = page.get("last_edited_time", "")
            current[pid] = {"title": title, "last_edited_time": last_edited}

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS snapshots ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  timestamp TEXT NOT NULL,"
            "  data TEXT NOT NULL"
            ")"
        )

        cursor = conn.execute(
            "SELECT data FROM snapshots ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        previous: dict[str, dict[str, str]] = {}
        if row:
            try:
                previous = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                pass

        added: list[dict[str, str]] = []
        modified: list[dict[str, str]] = []
        removed: list[dict[str, str]] = []

        prev_ids = set(previous.keys())
        curr_ids = set(current.keys())

        for pid in curr_ids - prev_ids:
            added.append({"page_id": pid, **current[pid]})

        for pid in prev_ids - curr_ids:
            removed.append({"page_id": pid, **previous[pid]})

        for pid in curr_ids & prev_ids:
            if current[pid]["last_edited_time"] != previous[pid]["last_edited_time"]:
                modified.append({
                    "page_id": pid,
                    "title": current[pid]["title"],
                    "previous_edit": previous[pid]["last_edited_time"],
                    "current_edit": current[pid]["last_edited_time"],
                })

        now = datetime.now(tz=timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO snapshots (timestamp, data) VALUES (?, ?)",
            (now, json.dumps(current, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

        return {
            "snapshot_time": now,
            "total_pages": len(current),
            "added": added,
            "modified": modified,
            "removed": removed,
            "counts": {
                "added": len(added),
                "modified": len(modified),
                "removed": len(removed),
            },
        }


