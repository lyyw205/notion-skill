from __future__ import annotations

import datetime
from typing import Any

from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return ""


class RecurringTaskGeneratorPlugin:
    name = "recurring_task_generator"
    description = "반복 규칙 기반 태스크 페이지 자동 생성"

    INTERVALS = {
        "daily": datetime.timedelta(days=1),
        "weekly": datetime.timedelta(weeks=1),
        "biweekly": datetime.timedelta(weeks=2),
        "monthly": datetime.timedelta(days=30),
    }

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        tasks: list[dict[str, Any]] = kwargs.get("tasks", [])
        if not tasks:
            return {"error": "tasks list required (each: {title, interval, date_property?})"}

        date_property: str = kwargs.get("date_property", "Date")
        today = datetime.date.today()
        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        try:
            existing_pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        existing_titles: set[str] = set()
        for page in existing_pages:
            existing_titles.add(_extract_title(page).strip().lower())

        for task in tasks:
            title = task.get("title", "")
            interval = task.get("interval", "weekly")
            if not title:
                continue

            delta = self.INTERVALS.get(interval)
            if delta is None:
                skipped.append({"title": title, "reason": f"unknown interval: {interval}"})
                continue

            due_date = today + delta
            full_title = f"{title} ({due_date.isoformat()})"

            if full_title.strip().lower() in existing_titles:
                skipped.append({"title": full_title, "reason": "already exists"})
                continue

            properties: dict[str, Any] = {
                "title": {
                    "title": [{"type": "text", "text": {"content": full_title}}]
                },
            }
            properties[date_property] = {
                "date": {"start": due_date.isoformat()}
            }

            try:
                page = client.create_page(
                    parent={"database_id": database_id},
                    properties=properties,
                )
                created.append({
                    "page_id": page.get("id", ""),
                    "title": full_title,
                    "due_date": due_date.isoformat(),
                    "interval": interval,
                })
            except Exception as exc:
                skipped.append({"title": full_title, "reason": str(exc)})

        return {
            "database_id": database_id,
            "created": created,
            "skipped": skipped,
            "total_created": len(created),
            "total_skipped": len(skipped),
        }


