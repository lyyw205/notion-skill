from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.translator import TranslatorPlugin


def _make_page(page_id: str = "abc") -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Title"}]}
        },
    }


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestTranslatorPlugin:
    def setup_method(self):
        self.plugin = TranslatorPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_translate_success(self):
        """Mock client + AI, verify translated_content returned."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = _make_page("page-tr")
        mock_client.get_page_blocks.return_value = _make_blocks("안녕하세요. 오늘 회의에 대해 알려드립니다.")

        translated = "Hello. I would like to inform you about today's meeting."

        with patch("notion_manager.plugins.translator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.translate.return_value = translated
            MockAI.return_value = mock_ai

            # create_page=False to skip page creation
            result = self.plugin.execute(
                mock_client, self.config, page_id="page-tr", target_lang="en", create_page=False
            )

        assert result["page_id"] == "page-tr"
        assert result["target_lang"] == "en"
        assert result["translated_content"] == translated
        assert result["new_page_id"] is None
        mock_ai.translate.assert_called_once()

    def test_create_page(self):
        """create_page=True should attempt new page creation via client.create_page."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = _make_page("page-tr2")
        mock_client.get_page_blocks.return_value = _make_blocks("한국어 텍스트입니다.")
        mock_client.create_page.return_value = {"id": "new-page-id"}

        translated = "This is Korean text."

        with patch("notion_manager.plugins.translator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.translate.return_value = translated
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-tr2", target_lang="en", create_page=True
            )

        assert result["new_page_id"] == "new-page-id"
        assert result["translated_content"] == translated
        mock_client.create_page.assert_called_once()
