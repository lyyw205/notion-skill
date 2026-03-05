from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.bullet_converter import BulletConverterPlugin


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "id": "block-1",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestBulletConverterPlugin:
    def setup_method(self):
        self.plugin = BulletConverterPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_convert_success(self):
        """Mock client + AI returning bullet list, verify bullet_points in result."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks(
            "This is a long paragraph about project planning and execution strategies."
        )

        bullet_list = ["Plan thoroughly", "Execute step by step", "Review results"]

        with patch("notion_manager.plugins.bullet_converter.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.convert_to_bullets.return_value = bullet_list
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-bc", replace=False
            )

        assert result["page_id"] == "page-bc"
        assert result["bullet_points"] == bullet_list
        assert result["replaced"] is False
        assert result["original_chars"] > 0
        mock_ai.convert_to_bullets.assert_called_once()
        # append_blocks should NOT be called when replace=False
        mock_client.append_blocks.assert_not_called()

    def test_replace_mode(self):
        """replace=True should delete existing blocks and append new bullet blocks."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Long text to replace.")
        mock_client.append_blocks.return_value = {}

        bullet_list = ["First point", "Second point"]

        with patch("notion_manager.plugins.bullet_converter.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.convert_to_bullets.return_value = bullet_list
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-rep", replace=True
            )

        assert result["replaced"] is True
        assert result["bullet_points"] == bullet_list
        mock_client.append_blocks.assert_called_once_with("page-rep", mock_client.append_blocks.call_args[0][1])
        # Verify the appended blocks are bulleted_list_item type
        appended = mock_client.append_blocks.call_args[0][1]
        assert all(b["type"] == "bulleted_list_item" for b in appended)
        assert len(appended) == 2
