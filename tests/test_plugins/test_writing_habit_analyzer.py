from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.writing_habit_analyzer import WritingHabitAnalyzerPlugin


def _make_page(page_id: str, created_time: str) -> dict:
    return {
        "id": page_id,
        "created_time": created_time,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": f"Page {page_id}"}]},
        },
    }


class TestWritingHabitAnalyzerPlugin:
    def setup_method(self):
        self.plugin = WritingHabitAnalyzerPlugin()
        self.config = {}

    def test_habit_analysis(self):
        """Mock pages with varied created_time, verify by_hour/by_weekday populated."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            # 2026-03-02 is a Monday, hour 10
            _make_page("p1", "2026-03-02T10:00:00.000Z"),
            # 2026-03-02 is a Monday, hour 10
            _make_page("p2", "2026-03-02T10:30:00.000Z"),
            # 2026-03-03 is a Tuesday, hour 14
            _make_page("p3", "2026-03-03T14:00:00.000Z"),
        ]

        result = self.plugin.execute(mock_client, self.config)

        assert result["total_pages"] == 3
        assert isinstance(result["by_hour"], dict)
        assert isinstance(result["by_weekday"], dict)
        assert isinstance(result["by_month"], dict)
        # hour 10 should have count 2
        assert result["by_hour"][10] == 2
        # Monday should appear
        assert result["by_weekday"]["Monday"] >= 2
        # month key
        assert "2026-03" in result["by_month"]

    def test_most_productive(self):
        """Verify most_productive_hour and most_productive_day match the most common values."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            # 3 pages on Wednesday at hour 9
            _make_page("p1", "2026-03-04T09:00:00.000Z"),  # Wednesday
            _make_page("p2", "2026-03-04T09:15:00.000Z"),  # Wednesday
            _make_page("p3", "2026-03-04T09:45:00.000Z"),  # Wednesday
            # 1 page on Thursday at hour 15
            _make_page("p4", "2026-03-05T15:00:00.000Z"),  # Thursday
        ]

        result = self.plugin.execute(mock_client, self.config)

        assert result["most_productive_hour"] == 9
        assert result["most_productive_day"] == "Wednesday"
