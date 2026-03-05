from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.meeting_summarizer import MeetingSummarizerPlugin


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


def _make_page(page_id: str = "abc") -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Title"}]}
        },
    }


class TestMeetingSummarizerPlugin:
    def setup_method(self):
        self.plugin = MeetingSummarizerPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_meeting_summary_success(self):
        """Mock client blocks + AI response, verify decisions/action_items extracted."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks(
            "Meeting notes: decided to launch v2. John will fix the bug by Friday."
        )

        ai_response = {
            "decisions": ["Launch v2"],
            "action_items": ["John will fix the bug by Friday"],
            "attendees": ["John"],
            "summary": "Team decided to launch v2.",
        }

        with patch("notion_manager.plugins.meeting_summarizer.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.summarize_meeting.return_value = ai_response
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, page_id="page-123")

        assert result["page_id"] == "page-123"
        assert result["decisions"] == ["Launch v2"]
        assert result["action_items"] == ["John will fix the bug by Friday"]
        assert result["attendees"] == ["John"]
        assert result["summary"] == "Team decided to launch v2."
        mock_client.get_page_blocks.assert_called_once_with("page-123")
        mock_ai.summarize_meeting.assert_called_once()

    def test_missing_page_id(self):
        """No page_id should return an error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.meeting_summarizer.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "page_id required"
