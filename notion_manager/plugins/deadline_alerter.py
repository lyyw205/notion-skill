from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


def _extract_date(page: dict[str, Any], date_property: str) -> datetime | None:
    props = page.get("properties", {})
    prop = props.get(date_property, {})
    if prop.get("type") == "date":
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


def _extract_status(page: dict[str, Any], status_property: str) -> str:
    props = page.get("properties", {})
    prop = props.get(status_property, {})
    ptype = prop.get("type", "")
    if ptype == "status":
        return (prop.get("status") or {}).get("name", "Unknown")
    elif ptype == "select":
        return (prop.get("select") or {}).get("name", "Unknown")
    return "Unknown"


COMPLETED_STATUSES = {"done", "completed", "complete", "완료", "닫힘", "closed"}


class DeadlineAlerterPlugin:
    name = "deadline_alerter"
    description = "마감일 기반 시간 버킷별 액션 리포트 (오늘/3일/7일/초과)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        date_property: str = kwargs.get("date_property", "Date")
        status_property: str = kwargs.get("status_property", "Status")

        try:
            pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        now = datetime.now(tz=timezone.utc)
        today_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
        three_days = today_end + timedelta(days=3)
        seven_days = today_end + timedelta(days=7)

        buckets: dict[str, list[dict[str, Any]]] = {
            "overdue": [],
            "today": [],
            "within_3_days": [],
            "within_7_days": [],
        }

        for page in pages:
            status = _extract_status(page, status_property)
            if status.lower() in COMPLETED_STATUSES:
                continue

            due = _extract_date(page, date_property)
            if due is None:
                continue

            title = _extract_title(page)
            entry = {"page_id": page.get("id", ""), "title": title, "due": due.isoformat()}

            if due < now:
                buckets["overdue"].append(entry)
            elif due <= today_end:
                buckets["today"].append(entry)
            elif due <= three_days:
                buckets["within_3_days"].append(entry)
            elif due <= seven_days:
                buckets["within_7_days"].append(entry)

        # AI priority scoring
        ai_priorities: list[dict[str, Any]] = []
        urgent_items = buckets["overdue"] + buckets["today"] + buckets["within_3_days"]
        if urgent_items:
            ai_config = config.get("ai", {})
            ai = AIProvider(
                api_key=ai_config.get("api_key", ""),
                model=ai_config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=ai_config.get("max_tokens", 1024),
            )
            import json
            prompt = (
                "다음 마감 임박 태스크 목록을 분석하고, 각 태스크에 1-10 우선순위 점수를 매겨주세요.\n"
                "기준: 마감일 긴급도, 제목에서 추정되는 중요도.\n"
                "Return as JSON array: [{\"title\": \"...\", \"priority_score\": N, \"reason\": \"...\"}]\n\n"
                f"{json.dumps(urgent_items, ensure_ascii=False)}"
            )
            try:
                ai_priorities = ai._complete_structured(prompt, fallback=[])
            except Exception:
                ai_priorities = []

        return {
            "database_id": database_id,
            "buckets": {k: v for k, v in buckets.items()},
            "counts": {k: len(v) for k, v in buckets.items()},
            "total_urgent": sum(len(v) for v in buckets.values()),
            "ai_priorities": ai_priorities,
        }


