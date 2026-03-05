from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from notion_manager.plugins.recurring_task_generator import RecurringTaskGeneratorPlugin

CONFIG: dict = {}


class TestRecurringTaskGeneratorPlugin:
    def setup_method(self):
        self.plugin = RecurringTaskGeneratorPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_missing_tasks(self):
        result = self.plugin.execute(MagicMock(), CONFIG, database_id="db-1")
        assert "error" in result

    def test_create_weekly_task(self):
        mock_client = MagicMock()
        mock_client.query_database.return_value = []
        mock_client.create_page.return_value = {"id": "new-page-1"}

        today = datetime.date.today()
        expected_due = today + datetime.timedelta(weeks=1)

        result = self.plugin.execute(
            mock_client, CONFIG,
            database_id="db-1",
            tasks=[{"title": "Weekly Standup", "interval": "weekly"}],
        )

        assert result["total_created"] == 1
        assert result["created"][0]["interval"] == "weekly"
        assert result["created"][0]["due_date"] == expected_due.isoformat()
        mock_client.create_page.assert_called_once()

    def test_skip_duplicate_task(self):
        today = datetime.date.today()
        due = today + datetime.timedelta(weeks=1)
        existing_title = f"Weekly Standup ({due.isoformat()})"

        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            {"id": "existing", "properties": {
                "Name": {"type": "title", "title": [{"plain_text": existing_title}]}
            }}
        ]

        result = self.plugin.execute(
            mock_client, CONFIG,
            database_id="db-1",
            tasks=[{"title": "Weekly Standup", "interval": "weekly"}],
        )

        assert result["total_created"] == 0
        assert result["total_skipped"] == 1
        assert result["skipped"][0]["reason"] == "already exists"

    def test_unknown_interval_skipped(self):
        mock_client = MagicMock()
        mock_client.query_database.return_value = []

        result = self.plugin.execute(
            mock_client, CONFIG,
            database_id="db-1",
            tasks=[{"title": "Bad Interval", "interval": "yearly"}],
        )

        assert result["total_skipped"] == 1
        assert "unknown interval" in result["skipped"][0]["reason"]
