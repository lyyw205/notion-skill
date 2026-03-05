from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.summarizer import SummarizerPlugin


def _make_blocks(text: str) -> list[dict]:
    """Helper to build a minimal paragraph block list with given text."""
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestSummarizerPlugin:
    def setup_method(self):
        self.plugin = SummarizerPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_summarize_short_page(self):
        """Pages with < 100 chars of text should be skipped."""
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks("Short text.")

        with patch("notion_manager.plugins.summarizer.AIProvider"):
            result = self.plugin.execute(
                mock_client, self.config, page_id="page-abc"
            )

        assert result["skipped"] is True
        assert result["reason"] == "text too short"
        assert result["summary"] is None

    def test_summarize_success(self):
        """Long enough page should be summarized via AI."""
        long_text = "A" * 150
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks(long_text)

        with patch("notion_manager.plugins.summarizer.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.summarize.return_value = "This is the summary."
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-xyz"
            )

        assert result["summary"] == "This is the summary."
        assert result["inserted"] is False
        assert result["page_id"] == "page-xyz"
        mock_ai_instance.summarize.assert_called_once()

    def test_summarize_with_insert(self):
        """When insert=True, append_blocks should be called."""
        long_text = "B" * 200
        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = _make_blocks(long_text)
        mock_client.append_blocks.return_value = {}

        with patch("notion_manager.plugins.summarizer.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.summarize.return_value = "Inserted summary."
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client, self.config, page_id="page-ins", insert=True
            )

        assert result["inserted"] is True
        mock_client.append_blocks.assert_called_once()

    def test_summarize_no_page_id_or_db(self):
        """Missing both page_id and database_id returns error."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.summarizer.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result

    def test_summarize_database(self):
        """database_id causes all pages to be summarized."""
        long_text = "C" * 150
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            {"id": "p1"},
            {"id": "p2"},
        ]
        mock_client.get_page_blocks.return_value = _make_blocks(long_text)

        with patch("notion_manager.plugins.summarizer.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.summarize.return_value = "DB summary."
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client, self.config, database_id="db-1"
            )

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert item["summary"] == "DB summary."
