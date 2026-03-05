from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from notion_manager.plugins.content_scheduler import ContentSchedulerPlugin

CONFIG: dict = {}


def _make_page(pid: str, title: str, status: str, scheduled: str | None = None) -> dict:
    props: dict = {
        "Name": {"type": "title", "title": [{"plain_text": title}]},
        "Status": {"type": "status", "status": {"name": status}},
    }
    if scheduled:
        props["Scheduled Date"] = {"type": "date", "date": {"start": scheduled}}
    return {"id": pid, "properties": props}


class TestContentSchedulerPlugin:
    def setup_method(self):
        self.plugin = ContentSchedulerPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_find_due_pages_dry_run(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(tz=timezone.utc) + timedelta(days=1)).isoformat()

        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Ready Post", "Draft", past),
            _make_page("p2", "Future Post", "Draft", future),
            _make_page("p3", "Already Published", "Published", past),
            _make_page("p4", "No Schedule", "Draft"),
        ]

        result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")

        assert result["dry_run"] is True
        assert result["total_due"] == 1
        assert result["due_pages"][0]["title"] == "Ready Post"
        assert result["total_updated"] == 0

    def test_apply_status_change(self):
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()

        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Ready Post", "Draft", past),
        ]
        mock_client.update_page.return_value = {}

        result = self.plugin.execute(
            mock_client, CONFIG,
            database_id="db-1",
            dry_run=False,
        )

        assert result["total_updated"] == 1
        mock_client.update_page.assert_called_once()
