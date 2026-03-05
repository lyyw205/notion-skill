from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_plain_text(rich_texts: list[dict[str, Any]]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_texts)


def _extract_status(page: dict[str, Any], status_property: str) -> str:
    props = page.get("properties", {})
    prop = props.get(status_property, {})
    ptype = prop.get("type", "")

    if ptype == "status":
        status_obj = prop.get("status") or {}
        return status_obj.get("name", "Unknown")
    elif ptype == "select":
        select_obj = prop.get("select") or {}
        return select_obj.get("name", "Unknown")
    elif ptype == "rich_text":
        return _get_plain_text(prop.get("rich_text", []))
    return "Unknown"


def _extract_date(page: dict[str, Any], date_property: str) -> datetime | None:
    props = page.get("properties", {})
    prop = props.get(date_property, {})
    ptype = prop.get("type", "")

    if ptype == "date":
        date_obj = prop.get("date") or {}
        raw = date_obj.get("start")
        if raw:
            try:
                if "T" in raw:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return _get_plain_text(prop.get("title", []))
    return page.get("id", "untitled")


def _iso_week_key(dt: datetime) -> str:
    return dt.strftime("%Y-W%W")


class TaskAnalyzerPlugin:
    name = "task_analyzer"
    description = "태스크 DB 완료율 및 생산성 분석"

    # Status values treated as "completed"
    COMPLETED_STATUSES = {"done", "completed", "complete", "완료", "닫힘", "closed"}
    IN_PROGRESS_STATUSES = {"in progress", "in-progress", "doing", "진행중", "진행 중"}

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        status_property: str = kwargs.get("status_property", "Status")
        date_property: str = kwargs.get("date_property", "Date")

        try:
            pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": f"failed to query database: {exc}"}

        now = datetime.now(tz=timezone.utc)
        four_weeks_ago = datetime(
            now.year, now.month, now.day, tzinfo=timezone.utc
        )
        # subtract 28 days
        import datetime as dt_module
        four_weeks_ago = now - dt_module.timedelta(weeks=4)

        total_tasks = len(pages)
        completed = 0
        in_progress = 0
        not_started = 0
        overdue = 0
        tasks_by_status: dict[str, int] = defaultdict(int)
        overdue_tasks: list[str] = []
        weekly_completions: dict[str, int] = defaultdict(int)
        completion_times: list[float] = []  # in days

        for page in pages:
            title = _extract_title(page)
            status = _extract_status(page, status_property)
            status_lower = status.lower()
            tasks_by_status[status] += 1

            is_completed = status_lower in self.COMPLETED_STATUSES
            is_in_progress = status_lower in self.IN_PROGRESS_STATUSES

            if is_completed:
                completed += 1
            elif is_in_progress:
                in_progress += 1
            else:
                not_started += 1

            due_date = _extract_date(page, date_property)
            if due_date:
                if not is_completed and due_date < now:
                    overdue += 1
                    overdue_tasks.append(title)

                if is_completed and due_date >= four_weeks_ago:
                    week_key = _iso_week_key(due_date)
                    weekly_completions[week_key] += 1

        completion_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0.0

        metrics: dict[str, Any] = {
            "database_id": database_id,
            "total_tasks": total_tasks,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "overdue": overdue,
            "completion_rate": round(completion_rate, 2),
            "tasks_by_status": dict(tasks_by_status),
            "overdue_tasks": overdue_tasks,
            "weekly_trend": dict(weekly_completions),
        }

        if completion_times:
            metrics["avg_completion_time"] = round(
                sum(completion_times) / len(completion_times), 2
            )
        else:
            metrics["avg_completion_time"] = None

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            ai_result = ai.analyze_tasks(metrics)
            metrics["ai_insights"] = ai_result
        except Exception as exc:
            metrics["ai_insights"] = {"error": str(exc)}

        return metrics


