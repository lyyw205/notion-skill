from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.status_reporter import StatusReporterPlugin

CONFIG = {"ai": {"api_key": "fake-key", "model": "claude-sonnet-4-20250514"}}


def _make_page(pid: str, title: str, status: str) -> dict:
    return {
        "id": pid,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
            "Status": {"type": "status", "status": {"name": status}},
        },
    }


class TestStatusReporterPlugin:
    def setup_method(self):
        self.plugin = StatusReporterPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_single_database_report(self):
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Task A", "Done"),
            _make_page("p2", "Task B", "In Progress"),
            _make_page("p3", "Task C", "Done"),
        ]

        with patch("notion_manager.plugins.status_reporter.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete_structured.return_value = {
                "summary": "Good progress",
                "progress_rates": [{"database_id": "db-1", "rate": 66.7}],
                "blockers": [],
                "next_actions": ["Finish Task B"],
            }
            MockAI.return_value = mock_ai
            result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")

        assert result["total_databases"] == 1
        assert result["databases"][0]["total"] == 3
        assert result["databases"][0]["by_status"]["Done"] == 2

    def test_multiple_databases(self):
        mock_client = MagicMock()
        mock_client.query_database.side_effect = [
            [_make_page("p1", "A", "Done")],
            [_make_page("p2", "B", "Todo"), _make_page("p3", "C", "Todo")],
        ]

        with patch("notion_manager.plugins.status_reporter.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete_structured.return_value = {"summary": "ok"}
            MockAI.return_value = mock_ai
            result = self.plugin.execute(
                mock_client, CONFIG, database_ids=["db-1", "db-2"]
            )

        assert result["total_databases"] == 2
        assert result["databases"][0]["total"] == 1
        assert result["databases"][1]["total"] == 2
