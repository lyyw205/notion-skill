from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich)
    return page.get("id", "")


class ProjectSummarizerPlugin:
    name = "project_summarizer"
    description = "프로젝트 진행 요약"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        status_property: str = kwargs.get("status_property", "Status")

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            items = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        by_status: dict[str, list[dict[str, Any]]] = {}
        now = datetime.now(tz=timezone.utc)

        for item in items:
            props = item.get("properties", {})
            status_val = "Unknown"
            sp = props.get(status_property, {})
            stype = sp.get("type", "")
            if stype == "select":
                sel = sp.get("select")
                if sel:
                    status_val = sel.get("name", "Unknown")
            elif stype == "status":
                st = sp.get("status")
                if st:
                    status_val = st.get("name", "Unknown")

            if status_val not in by_status:
                by_status[status_val] = []
            by_status[status_val].append(item)

        total = len(items)
        completed_keywords = {"done", "completed", "완료", "complete", "finished"}
        completed = sum(
            len(v) for k, v in by_status.items()
            if k.lower() in completed_keywords
        )
        progress_rate = (completed / total) if total > 0 else 0.0

        # Find bottlenecks: items with old last_edited_time in non-completed statuses
        bottlenecks: list[dict[str, Any]] = []
        for status_val, status_items in by_status.items():
            if status_val.lower() in completed_keywords:
                continue
            for item in status_items:
                last_edited = item.get("last_edited_time", "")
                if last_edited:
                    try:
                        edited_dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                        days_stuck = (now - edited_dt).days
                        if days_stuck >= 7:
                            bottlenecks.append({
                                "page_id": item.get("id", ""),
                                "title": _get_title(item),
                                "status": status_val,
                                "days_stuck": days_stuck,
                            })
                    except ValueError:
                        pass

        tasks_data: dict[str, Any] = {
            "total": total,
            "by_status": {k: len(v) for k, v in by_status.items()},
            "progress_rate": progress_rate,
            "bottlenecks_count": len(bottlenecks),
        }

        try:
            ai_summary = ai.analyze_tasks(tasks_data)
        except Exception as exc:
            ai_summary = {"error": str(exc)}

        return {
            "database_id": database_id,
            "total_projects": total,
            "by_status": {k: len(v) for k, v in by_status.items()},
            "progress_rate": progress_rate,
            "bottlenecks": bottlenecks,
            "ai_summary": ai_summary,
        }


