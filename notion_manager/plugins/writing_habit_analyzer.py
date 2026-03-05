from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class WritingHabitAnalyzerPlugin:
    name = "writing_habit_analyzer"
    description = "작성 습관 분석"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": str(exc)}

        by_hour: dict[int, int] = {h: 0 for h in range(24)}
        by_weekday: dict[str, int] = {day: 0 for day in WEEKDAY_NAMES}
        by_month: dict[str, int] = {}

        for page in pages:
            created_str = page.get("created_time", "")
            try:
                dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                continue

            by_hour[dt.hour] = by_hour.get(dt.hour, 0) + 1
            weekday_name = WEEKDAY_NAMES[dt.weekday()]
            by_weekday[weekday_name] = by_weekday.get(weekday_name, 0) + 1
            month_key = dt.strftime("%Y-%m")
            by_month[month_key] = by_month.get(month_key, 0) + 1

        most_productive_hour = max(by_hour, key=lambda h: by_hour[h]) if by_hour else 0
        most_productive_day = max(by_weekday, key=lambda d: by_weekday[d]) if by_weekday else "Monday"

        return {
            "total_pages": len(pages),
            "by_hour": by_hour,
            "by_weekday": by_weekday,
            "by_month": by_month,
            "most_productive_hour": most_productive_hour,
            "most_productive_day": most_productive_day,
        }


PLUGIN_CLASS = WritingHabitAnalyzerPlugin
