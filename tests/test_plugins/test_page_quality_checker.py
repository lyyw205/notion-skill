from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.page_quality_checker import PageQualityCheckerPlugin

CONFIG = {"ai": {"api_key": "fake-key", "model": "claude-sonnet-4-20250514"}}


class TestPageQualityCheckerPlugin:
    def setup_method(self):
        self.plugin = PageQualityCheckerPlugin()

    def test_missing_page_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_empty_page_returns_zero_scores(self):
        mock_client = MagicMock()
        mock_client.get_page.return_value = {
            "id": "p1",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": "Empty"}]}},
        }
        mock_client.get_page_blocks.return_value = []

        result = self.plugin.execute(mock_client, CONFIG, page_id="p1")

        assert result["overall"] == 0
        assert result["completeness"] == 0

    def test_quality_check_with_content(self):
        mock_client = MagicMock()
        mock_client.get_page.return_value = {
            "id": "p1",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": "Good Page"}]}},
        }
        mock_client.get_page_blocks.return_value = [
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Introduction"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Some content here."}]}},
            {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Details"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "More details."}]}},
        ]

        with patch("notion_manager.plugins.page_quality_checker.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete_structured.return_value = {
                "completeness": 8,
                "structure": 9,
                "readability": 7,
                "suggestions": ["Add conclusion section"],
            }
            MockAI.return_value = mock_ai
            result = self.plugin.execute(mock_client, CONFIG, page_id="p1")

        assert result["completeness"] == 8
        assert result["structure"] == 9
        assert result["readability"] == 7
        assert result["overall"] == 8.0
        assert len(result["suggestions"]) == 1
        assert result["block_stats"]["headings"] == 2
