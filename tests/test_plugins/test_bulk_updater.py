from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.bulk_updater import BulkUpdaterPlugin


def _make_page(pid: str, title: str) -> dict:
    return {
        "id": pid,
        "last_edited_time": "2025-01-01T00:00:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestBulkUpdaterPlugin:
    def setup_method(self):
        self.plugin = BulkUpdaterPlugin()
        self.config = {}

    def test_update_success(self):
        """query_database + update_page are called; updated_count matches page count."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Page One"),
            _make_page("p2", "Page Two"),
        ]
        mock_client.update_page.return_value = {}

        result = self.plugin.execute(
            mock_client,
            self.config,
            database_id="db-001",
            updates={"Status": "Done"},
        )

        assert result["updated_count"] == 2
        assert result["database_id"] == "db-001"
        assert result["errors"] == []
        assert mock_client.update_page.call_count == 2

    def test_missing_database_id(self):
        """When database_id is absent, an error is returned immediately."""
        mock_client = MagicMock()

        result = self.plugin.execute(
            mock_client, self.config, updates={"Status": "Done"}
        )

        assert "error" in result
        mock_client.query_database.assert_not_called()

    def test_missing_updates(self):
        """When updates dict is absent or empty, an error is returned immediately."""
        mock_client = MagicMock()

        result = self.plugin.execute(
            mock_client, self.config, database_id="db-001"
        )

        assert "error" in result
        mock_client.query_database.assert_not_called()
