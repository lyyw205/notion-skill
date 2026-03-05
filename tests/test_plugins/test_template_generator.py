from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.template_generator import TemplateGeneratorPlugin


def _make_page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


class TestTemplateGeneratorPlugin:
    def setup_method(self):
        self.plugin = TemplateGeneratorPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_analyze_success(self):
        """Pages with blocks should produce a populated common_structure."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Page One"),
            _make_page("p2", "Page Two"),
        ]

        def get_blocks(page_id: str):
            if page_id == "p1":
                return [{"type": "paragraph"}, {"type": "heading_2"}]
            return [{"type": "paragraph"}, {"type": "to_do"}]

        mock_client.get_page_blocks.side_effect = get_blocks

        with patch("notion_manager.plugins.template_generator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.summarize.return_value = "Use paragraphs and headings."
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config)

        assert result.get("analyzed_pages", 0) == 2
        common = result.get("common_structure", [])
        assert len(common) > 0
        block_types = [item["block_type"] for item in common]
        assert "paragraph" in block_types
        assert result.get("template_suggestion") == "Use paragraphs and headings."

    def test_missing_pages(self):
        """When search raises an exception, an error key is returned."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("not found")

        with patch("notion_manager.plugins.template_generator.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
