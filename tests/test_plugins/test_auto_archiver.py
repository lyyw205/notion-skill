from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from notion_manager.plugins.auto_archiver import AutoArchiverPlugin


def _make_page(pid: str, title: str, days_ago: int) -> dict:
    edited = datetime.now(tz=UTC) - timedelta(days=days_ago)
    return {
        "id": pid,
        "last_edited_time": edited.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestAutoArchiverPlugin:
    def setup_method(self):
        self.plugin = AutoArchiverPlugin()
        self.config = {}

    def test_dry_run_default(self):
        """Old pages are found as candidates but not actually archived (dry_run=True)."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Old Page", days_ago=120),
        ]

        result = self.plugin.execute(mock_client, self.config, days=90, dry_run=True)

        assert result["dry_run"] is True
        assert result["count"] == 1
        assert any(c["id"] == "p1" for c in result["candidates"])
        # archived key should not be present in dry_run mode
        assert "archived" not in result
        mock_client._client.pages.update.assert_not_called()

    def test_execute_archives(self):
        """With dry_run=False, pages get archived via the Notion API."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p2", "Stale Page", days_ago=200),
        ]

        result = self.plugin.execute(mock_client, self.config, days=90, dry_run=False)

        assert result["dry_run"] is False
        assert result["count"] == 1
        assert "archived" in result
        mock_client._client.pages.update.assert_called_once_with(
            page_id="p2", archived=True
        )

    def test_recent_pages_skipped(self):
        """Pages edited within the threshold are not included as candidates."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p3", "Recent Page", days_ago=10),
        ]

        result = self.plugin.execute(mock_client, self.config, days=90, dry_run=True)

        assert result["count"] == 0
        assert result["candidates"] == []
