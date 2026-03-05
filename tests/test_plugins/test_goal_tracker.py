from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.goal_tracker import GoalTrackerPlugin


def _make_goal(page_id: str, title: str, progress: float | None, target: float | None) -> dict:
    properties: dict = {
        "Name": {"type": "title", "title": [{"plain_text": title}]},
    }
    if progress is not None:
        properties["Progress"] = {"type": "number", "number": progress}
    else:
        properties["Progress"] = {"type": "number", "number": None}
    if target is not None:
        properties["Target"] = {"type": "number", "number": target}
    else:
        properties["Target"] = {"type": "number", "number": None}
    return {"id": page_id, "properties": properties}


class TestGoalTrackerPlugin:
    def setup_method(self):
        self.plugin = GoalTrackerPlugin()
        # No api_key → AI insights skipped
        self.config = {}

    def test_goal_tracking(self):
        """Mock DB with progress/target number properties, verify achievement_rate calculated."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_goal("g1", "Goal A", progress=100.0, target=100.0),  # rate=1.0 completed
            _make_goal("g2", "Goal B", progress=50.0, target=100.0),   # rate=0.5 in_progress
            _make_goal("g3", "Goal C", progress=200.0, target=100.0),  # rate=2.0 completed
        ]

        result = self.plugin.execute(mock_client, self.config, database_id="db-goals")

        assert result["database_id"] == "db-goals"
        assert result["total_goals"] == 3
        assert result["completed"] == 2
        assert result["in_progress"] == 1
        # achievement_rate = (1.0 + 0.5 + 2.0) / 3 = 1.1666...
        assert abs(result["achievement_rate"] - (3.5 / 3)) < 1e-6
        goals = result["goals"]
        assert len(goals) == 3
        rates = {g["title"]: g["rate"] for g in goals}
        assert rates["Goal A"] == 1.0
        assert rates["Goal B"] == 0.5
        assert rates["Goal C"] == 2.0
        # No AI config → ai_insights is None
        assert result["ai_insights"] is None

    def test_missing_database_id(self):
        """No database_id should return an error dict."""
        mock_client = MagicMock()
        result = self.plugin.execute(mock_client, self.config)
        assert "error" in result
        assert result["error"] == "database_id required"
