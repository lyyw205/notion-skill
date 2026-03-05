from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class ContentSchedulerPlugin:
    name = "content_scheduler"
    description = "예약 시간 도래 시 페이지 상태 자동 변경 (CLI 수동 실행)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        schedule_property: str = kwargs.get("schedule_property", "Scheduled Date")
        status_property: str = kwargs.get("status_property", "Status")
        target_status: str = kwargs.get("target_status", "Published")
        dry_run: bool = kwargs.get("dry_run", True)

        now = datetime.now(tz=timezone.utc)

        try:
            pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        due_pages: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []

        for page in pages:
            props = page.get("properties", {})

            # Check current status - skip if already target status
            status_prop = props.get(status_property, {})
            ptype = status_prop.get("type", "")
            current_status = ""
            if ptype == "status":
                current_status = (status_prop.get("status") or {}).get("name", "")
            elif ptype == "select":
                current_status = (status_prop.get("select") or {}).get("name", "")

            if current_status == target_status:
                continue

            # Check schedule date
            sched_prop = props.get(schedule_property, {})
            if sched_prop.get("type") != "date":
                continue

            date_obj = sched_prop.get("date") or {}
            raw = date_obj.get("start")
            if not raw:
                continue

            try:
                if "T" in raw:
                    sched_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                else:
                    sched_dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if sched_dt > now:
                continue

            pid = page.get("id", "")
            title = _extract_title(page)
            entry = {
                "page_id": pid,
                "title": title,
                "scheduled_date": raw,
                "current_status": current_status,
            }
            due_pages.append(entry)

            if not dry_run:
                update_props: dict[str, Any] = {}
                if ptype == "status":
                    update_props[status_property] = {"status": {"name": target_status}}
                elif ptype == "select":
                    update_props[status_property] = {"select": {"name": target_status}}

                if update_props:
                    try:
                        client.update_page(pid, update_props)
                        updated.append(entry)
                    except Exception:
                        continue

        return {
            "database_id": database_id,
            "dry_run": dry_run,
            "due_pages": due_pages,
            "updated": updated,
            "total_due": len(due_pages),
            "total_updated": len(updated),
        }


