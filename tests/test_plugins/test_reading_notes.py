from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.reading_notes import ReadingNotesPlugin


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


class TestReadingNotesPlugin:
    def setup_method(self):
        self.plugin = ReadingNotesPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_extract_success(self):
        """Mock client + AI, verify key_insights extracted."""
        mock_client = MagicMock()
        mock_client.get_page.return_value = _make_page("page-rn")
        mock_client.get_page_blocks.return_value = _make_blocks(
            "Chapter 1: The power of habits. Habits form through cue, routine, reward loops."
        )

        ai_response = {
            "key_insights": ["Habits consist of cue-routine-reward loops"],
            "main_concepts": ["habit loop", "cue", "routine", "reward"],
            "quotes": ["Small habits make a big difference"],
            "summary": "Book explores habit formation mechanisms.",
        }

        with patch("notion_manager.plugins.reading_notes.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.extract_reading_notes.return_value = ai_response
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, page_id="page-rn")

        assert result["page_id"] == "page-rn"
        assert result["title"] == "Title"
        assert result["key_insights"] == ["Habits consist of cue-routine-reward loops"]
        assert result["main_concepts"] == ["habit loop", "cue", "routine", "reward"]
        assert result["quotes"] == ["Small habits make a big difference"]
        assert result["summary"] == "Book explores habit formation mechanisms."
        mock_client.get_page.assert_called_once_with("page-rn")
        mock_client.get_page_blocks.assert_called_once_with("page-rn")

    def test_missing_page_id(self):
        """No page_id should return an error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.reading_notes.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "page_id required"
