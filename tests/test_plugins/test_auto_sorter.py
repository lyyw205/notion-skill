from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.auto_sorter import AutoSorterPlugin


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


class TestAutoSorterPlugin:
    def setup_method(self):
        self.plugin = AutoSorterPlugin()
        self.config = {}

    def test_sort_success(self):
        """query_database is called with correct sorts; sorted_count matches results."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Alpha"),
            _make_page("p2", "Beta"),
            _make_page("p3", "Gamma"),
        ]

        result = self.plugin.execute(
            mock_client,
            self.config,
            database_id="db-001",
            sort_property="Date",
            direction="descending",
        )

        assert result["sorted_count"] == 3
        assert result["database_id"] == "db-001"
        assert result["sort_property"] == "Date"
        assert result["direction"] == "descending"
        mock_client.query_database.assert_called_once_with(
            "db-001", sorts=[{"property": "Date", "direction": "descending"}]
        )

    def test_missing_database_id(self):
        """When database_id is not provided, an error is returned."""
        mock_client = MagicMock()

        result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
        mock_client.query_database.assert_not_called()
