from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.usage_analyzer import UsageAnalyzerPlugin


def _make_page(page_id: str, title: str, last_edited: str) -> dict:
    return {
        "id": page_id,
        "last_edited_time": last_edited,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


class TestUsageAnalyzerPlugin:
    def setup_method(self):
        self.plugin = UsageAnalyzerPlugin()
        self.config = {}

    def test_usage_analysis(self):
        """Mock search returning pages with varied last_edited_time, verify active/stale/abandoned counts."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Recent Page", "2026-03-04T10:00:00.000Z"),   # 1 day ago
            _make_page("p2", "Stale Page", "2026-02-18T10:00:00.000Z"),    # 15 days ago
            _make_page("p3", "Old Page", "2026-01-04T10:00:00.000Z"),      # ~60 days ago
        ]

        result = self.plugin.execute(mock_client, self.config)

        assert result["total_pages"] == 3
        assert result["active"] == 1
        assert result["stale"] == 1
        assert result["abandoned"] == 1
        assert "most_active" in result
        assert "least_active" in result
        mock_client.search.assert_called_once_with("", filter_type="page")

    def test_empty_workspace(self):
        """Search returns [] → all counts 0."""
        mock_client = MagicMock()
        mock_client.search.return_value = []

        result = self.plugin.execute(mock_client, self.config)

        assert result["total_pages"] == 0
        assert result["active"] == 0
        assert result["stale"] == 0
        assert result["abandoned"] == 0
        assert result["most_active"] == []
        assert result["least_active"] == []
