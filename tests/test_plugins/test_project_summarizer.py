from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from notion_manager.plugins.project_summarizer import ProjectSummarizerPlugin


def _make_item(page_id: str, status: str, days_ago: int = 1) -> dict:
    edited = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return {
        "id": page_id,
        "last_edited_time": edited.isoformat().replace("+00:00", "Z"),
        "properties": {
            "Status": {
                "type": "select",
                "select": {"name": status},
            },
            "Name": {"type": "title", "title": [{"plain_text": f"Project {page_id}"}]},
        },
    }


class TestProjectSummarizerPlugin:
    def setup_method(self):
        self.plugin = ProjectSummarizerPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_project_summary(self):
        """Mock DB with items in different statuses, verify by_status and progress_rate."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_item("p1", "Done"),
            _make_item("p2", "Done"),
            _make_item("p3", "In Progress"),
            _make_item("p4", "Not Started"),
        ]

        ai_response = {
            "summary": "Good progress overall.",
            "priorities": ["Finish In Progress items"],
            "blockers": [],
            "next_actions": ["Review p3"],
        }

        with patch("notion_manager.plugins.project_summarizer.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.analyze_tasks.return_value = ai_response
            MockAI.return_value = mock_ai

            result = self.plugin.execute(
                mock_client, self.config, database_id="db-proj"
            )

        assert result["database_id"] == "db-proj"
        assert result["total_projects"] == 4
        assert result["by_status"]["Done"] == 2
        assert result["by_status"]["In Progress"] == 1
        assert result["by_status"]["Not Started"] == 1
        # 2 done out of 4 = 0.5
        assert result["progress_rate"] == 0.5
        assert result["ai_summary"] == ai_response
        mock_client.query_database.assert_called_once_with("db-proj")

    def test_missing_database_id(self):
        """No database_id should return an error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.project_summarizer.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "database_id required"
