from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.db_stats import DBStatsPlugin


def _make_item(page_id: str, status: str, done: bool) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Status": {
                "type": "select",
                "select": {"name": status},
            },
            "Done": {
                "type": "checkbox",
                "checkbox": done,
            },
            "Name": {"type": "title", "title": [{"plain_text": f"Item {page_id}"}]},
        },
    }


class TestDBStatsPlugin:
    def setup_method(self):
        self.plugin = DBStatsPlugin()
        self.config = {}

    def test_stats_success(self):
        """Mock query_database with items having select/checkbox properties, verify counts."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_item("p1", "In Progress", False),
            _make_item("p2", "Done", True),
            _make_item("p3", "In Progress", True),
        ]

        result = self.plugin.execute(mock_client, self.config, database_id="db-abc")

        assert result["database_id"] == "db-abc"
        assert result["total_items"] == 3

        # Status select distribution
        status_stats = result["properties_summary"]["Status"]["stats"]
        assert status_stats["In Progress"] == 2
        assert status_stats["Done"] == 1

        # status_distribution should track "Status" field (lowercase == "status")
        assert result["status_distribution"]["In Progress"] == 2
        assert result["status_distribution"]["Done"] == 1

        # Checkbox stats
        done_stats = result["properties_summary"]["Done"]["stats"]
        assert done_stats["true"] == 2
        assert done_stats["false"] == 1

        mock_client.query_database.assert_called_once_with("db-abc")

    def test_missing_database_id(self):
        """No database_id should return an error dict."""
        mock_client = MagicMock()
        result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "database_id required"
