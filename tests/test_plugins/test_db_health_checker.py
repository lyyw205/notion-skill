from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.db_health_checker import DBHealthCheckerPlugin


def _make_schema(*prop_names: str) -> dict:
    """Build a minimal DB schema dict with the given property names as title/rich_text."""
    props = {}
    for name in prop_names:
        props[name] = {"type": "rich_text"}
    return {"properties": props}


def _make_item(page_id: str, filled_props: dict[str, str], empty_props: list[str]) -> dict:
    """Build a DB item with some filled and some empty rich_text properties."""
    properties: dict = {}
    for name, value in filled_props.items():
        properties[name] = {
            "type": "rich_text",
            "rich_text": [{"plain_text": value}],
        }
    for name in empty_props:
        properties[name] = {
            "type": "rich_text",
            "rich_text": [],
        }
    return {"id": page_id, "properties": properties}


class TestDBHealthCheckerPlugin:
    def setup_method(self):
        self.plugin = DBHealthCheckerPlugin()
        self.config = {}

    def test_health_check(self):
        """Mock DB with some empty properties, verify issues detected and health_score < 1.0."""
        mock_client = MagicMock()
        mock_client.get_database.return_value = _make_schema("Title", "Notes", "Tags")
        mock_client.query_database.return_value = [
            _make_item("i1", {"Title": "Item 1", "Notes": "Some notes"}, ["Tags"]),
            _make_item("i2", {"Title": "Item 2"}, ["Notes", "Tags"]),
        ]

        result = self.plugin.execute(mock_client, self.config, database_id="db-1")

        assert result["database_id"] == "db-1"
        assert result["total_items"] == 2
        assert result["health_score"] < 1.0
        issues = result["issues"]
        assert "empty_properties" in issues
        # Tags is empty for both items → unused_properties should include "Tags"
        assert "Tags" in issues["unused_properties"]

    def test_missing_database_id(self):
        """No database_id should return an error dict."""
        mock_client = MagicMock()
        result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "database_id required"
