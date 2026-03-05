from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from notion_manager.plugins.weekly_review import WeeklyReviewPlugin


def _make_page(page_id: str, title: str, days_ago: int = 2) -> dict:
    edited = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
    return {
        "id": page_id,
        "last_edited_time": edited + "T00:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


class TestWeeklyReviewPlugin:
    def setup_method(self):
        self.plugin = WeeklyReviewPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_review_success(self):
        """Mock search with recent pages and AI; verify review_content is populated."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Page One", days_ago=1),
            _make_page("p2", "Page Two", days_ago=3),
        ]
        mock_client._client.pages.create.return_value = {"id": "review-page"}

        with patch("notion_manager.plugins.weekly_review.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_weekly_review.return_value = "Great week overall."
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, create_page=False
            )

        assert result.get("review_content") == "Great week overall."
        assert result.get("pages_edited") == 2
        assert "week" in result

    def test_no_activity(self):
        """Pages edited more than 7 days ago should result in pages_edited=0."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("old1", "Old Page", days_ago=10),
            _make_page("old2", "Another Old", days_ago=14),
        ]

        with patch("notion_manager.plugins.weekly_review.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_weekly_review.return_value = "Nothing happened."
            MockAI.return_value = mock_ai

            result = self.plugin.execute(mock_client, self.config, create_page=False)

        assert result.get("pages_edited") == 0
