from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from notion_manager.plugins.daily_journal import DailyJournalPlugin


class TestDailyJournalPlugin:
    def setup_method(self):
        self.plugin = DailyJournalPlugin()
        self.config = {}

    def test_create_journal(self):
        """Mock pages.create returning a new page id; verify created_page_id and date."""
        mock_client = MagicMock()
        mock_client._client.pages.create.return_value = {"id": "new-page"}

        result = self.plugin.execute(mock_client, self.config, parent_page_id="parent-123")

        assert result.get("created_page_id") == "new-page"
        assert result.get("date") == datetime.date.today().isoformat()
        mock_client._client.pages.create.assert_called_once()

    def test_missing_parent(self):
        """No parent_page_id should return error."""
        mock_client = MagicMock()

        result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
