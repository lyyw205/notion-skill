from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.faq_generator import FAQGeneratorPlugin


class TestFAQGeneratorPlugin:
    def setup_method(self):
        self.plugin = FAQGeneratorPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_generate_faq(self):
        """Mock client and AI returning a FAQ list; verify faqs populated."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Some content about our product."}]}}
        ]

        faq_data = [
            {"question": "What is this?", "answer": "It is a product."},
            {"question": "How does it work?", "answer": "Very well."},
        ]

        with patch("notion_manager.plugins.faq_generator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_faq.return_value = faq_data
            MockAI.return_value = mock_ai

            with patch("notion_manager.plugins.faq_generator.NotionClient") as MockNC:
                MockNC.blocks_to_text.return_value = "Some content about our product."

                result = self.plugin.execute(mock_client, self.config, page_id="page-123")

        assert len(result.get("faqs", [])) == 2
        assert result["faqs"][0]["question"] == "What is this?"
        assert "page-123" in result.get("source_pages", [])

    def test_missing_source(self):
        """No page_id or database_id should return error."""
        mock_client = MagicMock()

        with patch("notion_manager.plugins.faq_generator.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
