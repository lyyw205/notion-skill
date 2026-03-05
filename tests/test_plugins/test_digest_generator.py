from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from notion_manager.plugins.digest_generator import DigestGeneratorPlugin


def _make_page(page_id: str, days_ago: int) -> dict:
    edited = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return {
        "id": page_id,
        "last_edited_time": edited.isoformat().replace("+00:00", "Z"),
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": f"Page {page_id}"}]}
        },
    }


class TestDigestGeneratorPlugin:
    def setup_method(self):
        self.plugin = DigestGeneratorPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_weekly_digest(self):
        """Mock search returning pages edited in last 7 days, verify digest generated."""
        mock_client = MagicMock()
        # page edited 3 days ago → within weekly window
        mock_client.search.return_value = [_make_page("p1", 3)]

        with patch("notion_manager.plugins.digest_generator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_digest.return_value = "Weekly digest content"
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, period="weekly")

        assert result["period"] == "weekly"
        assert result["pages_changed"] == 1
        assert result["digest"] == "Weekly digest content"
        assert result["created_page_id"] is None
        mock_ai.generate_digest.assert_called_once()

    def test_monthly_digest(self):
        """period='monthly' should use a 30-day date range."""
        mock_client = MagicMock()
        # one page edited 20 days ago → within monthly window but outside weekly
        mock_client.search.return_value = [_make_page("p2", 20)]

        with patch("notion_manager.plugins.digest_generator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_digest.return_value = "Monthly digest content"
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, period="monthly")

        assert result["period"] == "monthly"
        assert result["pages_changed"] == 1
        assert result["digest"] == "Monthly digest content"

        # Verify the date_range spans approximately 30 days
        start = datetime.fromisoformat(result["date_range"]["start"])
        end = datetime.fromisoformat(result["date_range"]["end"])
        assert (end - start).days == 30

    def test_no_changes(self):
        """No pages edited within window → pages_changed=0."""
        mock_client = MagicMock()
        # page edited 60 days ago → outside both windows
        mock_client.search.return_value = [_make_page("p3", 60)]

        with patch("notion_manager.plugins.digest_generator.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_digest.return_value = "No changes digest"
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, period="weekly")

        assert result["pages_changed"] == 0
        # AI is still called (with "변경된 페이지가 없습니다." text)
        mock_ai.generate_digest.assert_called_once()
