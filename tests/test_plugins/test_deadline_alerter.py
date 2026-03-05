from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from notion_manager.plugins.deadline_alerter import DeadlineAlerterPlugin


def _make_task(task_id: str, title: str, status: str, due: datetime | None = None) -> dict:
    props: dict = {
        "Name": {"type": "title", "title": [{"plain_text": title}]},
        "Status": {"type": "status", "status": {"name": status}},
    }
    if due is not None:
        props["Date"] = {"type": "date", "date": {"start": due.isoformat()}}
    return {"id": task_id, "properties": props}


CONFIG = {"ai": {"api_key": "fake-key", "model": "claude-sonnet-4-20250514"}}


class TestDeadlineAlerterPlugin:
    def setup_method(self):
        self.plugin = DeadlineAlerterPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_bucket_classification(self):
        now = datetime.now(tz=timezone.utc)
        pages = [
            _make_task("t1", "Overdue", "In Progress", now - timedelta(days=1)),
            _make_task("t2", "Due Today", "In Progress", now + timedelta(hours=2)),
            _make_task("t3", "In 2 Days", "Not Started", now + timedelta(days=2)),
            _make_task("t4", "In 5 Days", "Not Started", now + timedelta(days=5)),
            _make_task("t5", "Far Away", "Not Started", now + timedelta(days=30)),
            _make_task("t6", "Done", "Done", now - timedelta(days=1)),
        ]

        mock_client = MagicMock()
        mock_client.query_database.return_value = pages

        with patch("notion_manager.plugins.deadline_alerter.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete_structured.return_value = []
            MockAI.return_value = mock_ai
            result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")

        assert result["counts"]["overdue"] == 1
        assert result["counts"]["today"] == 1
        assert result["counts"]["within_3_days"] == 1
        assert result["counts"]["within_7_days"] == 1
        # "Far Away" and "Done" not in any bucket
        assert result["total_urgent"] == 4

    def test_no_date_property_skipped(self):
        pages = [_make_task("t1", "No Date", "In Progress")]
        mock_client = MagicMock()
        mock_client.query_database.return_value = pages

        with patch("notion_manager.plugins.deadline_alerter.AIProvider") as MockAI:
            MockAI.return_value = MagicMock()
            result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")

        assert result["total_urgent"] == 0

    def test_completed_tasks_excluded(self):
        now = datetime.now(tz=timezone.utc)
        pages = [_make_task("t1", "Done Task", "completed", now - timedelta(days=1))]
        mock_client = MagicMock()
        mock_client.query_database.return_value = pages

        with patch("notion_manager.plugins.deadline_alerter.AIProvider") as MockAI:
            MockAI.return_value = MagicMock()
            result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")

        assert result["counts"]["overdue"] == 0
