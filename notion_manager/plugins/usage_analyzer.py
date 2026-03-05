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


class UsageAnalyzerPlugin:
    name = "usage_analyzer"
    description = "워크스페이스 사용 패턴 분석"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": str(exc)}

        now = datetime.now(timezone.utc)
        active = 0
        stale = 0
        abandoned = 0
        page_records: list[dict] = []

        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)
            last_edited_str = page.get("last_edited_time", "")
            try:
                last_edited = datetime.fromisoformat(last_edited_str.replace("Z", "+00:00"))
                days_ago = (now - last_edited).days
            except Exception:
                last_edited = now
                days_ago = 0

            if days_ago <= 7:
                active += 1
                bucket = "active"
            elif days_ago <= 30:
                stale += 1
                bucket = "stale"
            else:
                abandoned += 1
                bucket = "abandoned"

            page_records.append({
                "id": pid,
                "title": title,
                "last_edited": last_edited_str,
                "days_ago": days_ago,
                "bucket": bucket,
            })

        sorted_records = sorted(page_records, key=lambda r: r["days_ago"])
        most_active = [
            {"id": r["id"], "title": r["title"], "last_edited": r["last_edited"]}
            for r in sorted_records[:5]
        ]
        least_active = [
            {"id": r["id"], "title": r["title"], "last_edited": r["last_edited"]}
            for r in sorted_records[-5:]
        ]

        return {
            "total_pages": len(pages),
            "active": active,
            "stale": stale,
            "abandoned": abandoned,
            "most_active": most_active,
            "least_active": least_active,
        }


