from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from notion_manager.plugins.task_analyzer import TaskAnalyzerPlugin


def _make_task(
    task_id: str,
    title: str,
    status: str,
    due_date: datetime | None = None,
) -> dict:
    """Build a minimal Notion page dict representing a task."""
    props: dict = {
        "Name": {
            "type": "title",
            "title": [{"plain_text": title}],
        },
        "Status": {
            "type": "status",
            "status": {"name": status},
        },
    }
    if due_date is not None:
        props["Date"] = {
            "type": "date",
            "date": {"start": due_date.isoformat()},
        }
    return {"id": task_id, "properties": props}


CONFIG = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}


class TestTaskAnalyzerPlugin:
    def setup_method(self):
        self.plugin = TaskAnalyzerPlugin()

    def _run(self, pages: list[dict], **kwargs) -> dict:
        mock_client = MagicMock()
        mock_client.query_database.return_value = pages

        with patch("notion_manager.plugins.task_analyzer.AIProvider") as MockAI:
            mock_ai_instance = MagicMock()
            mock_ai_instance.analyze_tasks.return_value = {
                "summary": "ok",
                "priorities": [],
                "blockers": [],
                "next_actions": [],
            }
            MockAI.return_value = mock_ai_instance

            result = self.plugin.execute(
                mock_client, CONFIG, database_id="db-test", **kwargs
            )
        return result

    def test_analyze_basic(self):
        """Verify metrics are calculated correctly from simple task data."""
        pages = [
            _make_task("t1", "Task Done", "Done"),
            _make_task("t2", "Task In Progress", "In Progress"),
            _make_task("t3", "Task Todo", "Not Started"),
            _make_task("t4", "Another Done", "completed"),
        ]

        result = self._run(pages)

        assert result["total_tasks"] == 4
        assert result["completed"] == 2
        assert result["in_progress"] == 1
        assert result["not_started"] == 1
        assert result["overdue"] == 0
        assert result["completion_rate"] == 50.0
        assert "ai_insights" in result

    def test_analyze_missing_database_id(self):
        """Missing database_id kwarg returns error dict."""
        mock_client = MagicMock()
        with patch("notion_manager.plugins.task_analyzer.AIProvider"):
            result = self.plugin.execute(mock_client, CONFIG)
        assert "error" in result

    def test_analyze_with_overdue(self):
        """Tasks past their due date that are not completed should be overdue."""
        now = datetime.now(tz=timezone.utc)
        past = now - timedelta(days=3)
        future = now + timedelta(days=3)

        pages = [
            _make_task("t1", "Overdue Task", "In Progress", due_date=past),
            _make_task("t2", "Future Task", "Not Started", due_date=future),
            _make_task("t3", "Done on time", "Done", due_date=past),
        ]

        result = self._run(pages)

        assert result["overdue"] == 1
        assert "Overdue Task" in result["overdue_tasks"]
        # Completed tasks are NOT counted as overdue even if past due
        assert "Done on time" not in result["overdue_tasks"]

    def test_analyze_all_completed(self):
        """100% completion rate when all tasks are done."""
        pages = [
            _make_task("t1", "A", "done"),
            _make_task("t2", "B", "completed"),
            _make_task("t3", "C", "complete"),
        ]
        result = self._run(pages)
        assert result["completion_rate"] == 100.0
        assert result["overdue"] == 0

    def test_analyze_empty_database(self):
        """Empty database returns 0 for all metrics."""
        result = self._run([])
        assert result["total_tasks"] == 0
        assert result["completion_rate"] == 0.0

    def test_tasks_by_status_counts(self):
        """tasks_by_status should map each status name to its count."""
        pages = [
            _make_task("t1", "A", "Done"),
            _make_task("t2", "B", "Done"),
            _make_task("t3", "C", "In Progress"),
        ]
        result = self._run(pages)
        assert result["tasks_by_status"]["Done"] == 2
        assert result["tasks_by_status"]["In Progress"] == 1

    def test_analyze_client_error(self):
        """Client errors during query_database should return error dict."""
        mock_client = MagicMock()
        mock_client.query_database.side_effect = RuntimeError("DB error")

        with patch("notion_manager.plugins.task_analyzer.AIProvider"):
            result = self.plugin.execute(
                mock_client, CONFIG, database_id="db-err"
            )

        assert "error" in result
