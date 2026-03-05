from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.content_expander import ContentExpanderPlugin


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestContentExpanderPlugin:
    def setup_method(self):
        self.plugin = ContentExpanderPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_expand_success(self):
        """Mock client + AI, verify expanded_content returned and inserted=True."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Short note: improve onboarding.")
        mock_client.append_blocks.return_value = {}

        expanded = (
            "## Onboarding Improvement\n\n"
            "### Overview\nThe current onboarding process needs improvement.\n\n"
            "### Key Actions\n- Revise welcome email\n- Add tutorial video\n"
        )

        with patch("notion_manager.plugins.content_expander.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.expand_content.return_value = expanded
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-ce", style="formal"
            )

        assert result["page_id"] == "page-ce"
        assert result["expanded_content"] == expanded
        assert result["inserted"] is True
        assert result["expanded_chars"] == len(expanded)
        assert result["original_chars"] > 0
        mock_ai.expand_content.assert_called_once()
        mock_client.append_blocks.assert_called_once()

    def test_missing_page_id(self):
        """No page_id should return an error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.content_expander.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "page_id required"
