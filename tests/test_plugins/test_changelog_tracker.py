from __future__ import annotations

import json
import sqlite3
import tempfile
from unittest.mock import MagicMock

from notion_manager.plugins.changelog_tracker import ChangelogTrackerPlugin

CONFIG: dict = {}


class TestChangelogTrackerPlugin:
    def setup_method(self):
        self.plugin = ChangelogTrackerPlugin()

    def test_first_snapshot_no_diff(self):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "id": "p1",
                "last_edited_time": "2026-03-01T10:00:00Z",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "Page A"}]}},
            }
        ]

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        result = self.plugin.execute(mock_client, CONFIG, db_path=db_path)

        assert result["total_pages"] == 1
        assert result["counts"]["added"] == 1
        assert result["counts"]["modified"] == 0
        assert result["counts"]["removed"] == 0

    def test_detect_modified_page(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Seed previous snapshot
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, data TEXT)"
        )
        previous = {"p1": {"title": "Page A", "last_edited_time": "2026-03-01T10:00:00Z"}}
        conn.execute("INSERT INTO snapshots (timestamp, data) VALUES (?, ?)", ("t1", json.dumps(previous)))
        conn.commit()
        conn.close()

        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "id": "p1",
                "last_edited_time": "2026-03-05T12:00:00Z",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "Page A"}]}},
            }
        ]

        result = self.plugin.execute(mock_client, CONFIG, db_path=db_path)

        assert result["counts"]["modified"] == 1
        assert result["counts"]["added"] == 0

    def test_detect_removed_page(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, data TEXT)"
        )
        previous = {
            "p1": {"title": "Page A", "last_edited_time": "2026-03-01T10:00:00Z"},
            "p2": {"title": "Page B", "last_edited_time": "2026-03-01T10:00:00Z"},
        }
        conn.execute("INSERT INTO snapshots (timestamp, data) VALUES (?, ?)", ("t1", json.dumps(previous)))
        conn.commit()
        conn.close()

        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "id": "p1",
                "last_edited_time": "2026-03-01T10:00:00Z",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "Page A"}]}},
            }
        ]

        result = self.plugin.execute(mock_client, CONFIG, db_path=db_path)

        assert result["counts"]["removed"] == 1
        assert result["counts"]["added"] == 0
