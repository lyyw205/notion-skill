from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.tagger import TaggerPlugin


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestTaggerPlugin:
    def setup_method(self):
        self.plugin = TaggerPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_tag_success(self):
        """Should return tags and update the page."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Some content about AI and machine learning.")
        mock_client.update_page.return_value = {}

        with patch("notion_manager.plugins.tagger.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.classify_tags.return_value = ["ai", "machine-learning"]
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-tag-1"
            )

        assert result["tags"] == ["ai", "machine-learning"]
        assert result["updated"] is True
        assert result["page_id"] == "page-tag-1"

        # Verify update_page was called with correct structure
        call_args = mock_client.update_page.call_args
        props = call_args[0][1]  # second positional arg is properties
        assert "Tags" in props
        assert props["Tags"]["multi_select"] == [
            {"name": "ai"},
            {"name": "machine-learning"},
        ]

    def test_tag_with_available_tags(self):
        """available_tags kwarg should be forwarded to AI classify_tags."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Content about finance.")
        mock_client.update_page.return_value = {}

        available = ["finance", "tech", "health"]

        with patch("notion_manager.plugins.tagger.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.classify_tags.return_value = ["finance"]
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client,
                self.config,
                page_id="page-tag-2",
                available_tags=available,
            )

        mock_ai_instance.classify_tags.assert_called_once_with(
            "Content about finance.", available
        )
        assert result["tags"] == ["finance"]

    def test_tag_missing_page_id(self):
        """Missing page_id should return error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.tagger.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result

    def test_tag_custom_property(self):
        """Custom tag_property name should be used when updating page."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Text with custom property.")
        mock_client.update_page.return_value = {}

        with patch("notion_manager.plugins.tagger.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.classify_tags.return_value = ["custom-tag"]
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client,
                self.config,
                page_id="page-tag-3",
                tag_property="Categories",
            )

        call_args = mock_client.update_page.call_args
        props = call_args[0][1]
        assert "Categories" in props
        assert result["updated"] is True

    def test_tag_client_error(self):
        """Client errors during get_page_blocks should return error dict."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.side_effect = RuntimeError("API error")

        with patch("notion_manager.plugins.tagger.AIProvider"):
            result = self.plugin.execute(
                mock_client, self.config, page_id="page-err"
            )

        assert "error" in result
        assert result["updated"] is False
