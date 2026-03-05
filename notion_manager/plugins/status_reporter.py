from __future__ import annotations

from collections import defaultdict
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


def _extract_status(page: dict[str, Any], status_property: str) -> str:
    props = page.get("properties", {})
    prop = props.get(status_property, {})
    ptype = prop.get("type", "")
    if ptype == "status":
        return (prop.get("status") or {}).get("name", "Unknown")
    elif ptype == "select":
        return (prop.get("select") or {}).get("name", "Unknown")
    return "Unknown"


class StatusReporterPlugin:
    name = "status_reporter"
    description = "프로젝트 DB 상태 종합 보고서 자동 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_ids: list[str] = kwargs.get("database_ids", [])
        if not database_ids:
            database_id = kwargs.get("database_id")
            if database_id:
                database_ids = [database_id]
            else:
                return {"error": "database_ids or database_id required"}

        status_property: str = kwargs.get("status_property", "Status")

        db_reports: list[dict[str, Any]] = []
        for db_id in database_ids:
            try:
                pages = client.query_database(db_id)
            except Exception as exc:
                db_reports.append({"database_id": db_id, "error": str(exc)})
                continue

            total = len(pages)
            by_status: dict[str, int] = defaultdict(int)
            titles_by_status: dict[str, list[str]] = defaultdict(list)

            for page in pages:
                status = _extract_status(page, status_property)
                by_status[status] += 1
                titles_by_status[status].append(_extract_title(page))

            db_reports.append({
                "database_id": db_id,
                "total": total,
                "by_status": dict(by_status),
                "sample_titles": {k: v[:5] for k, v in titles_by_status.items()},
            })

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=ai_config.get("max_tokens", 2048),
        )

        import json
        prompt = (
            "다음 프로젝트 DB 상태 데이터를 분석하고 종합 보고서를 작성해주세요.\n\n"
            f"{json.dumps(db_reports, ensure_ascii=False, indent=2)}\n\n"
            "다음 JSON으로 응답:\n"
            "{\n"
            '  "summary": "전체 요약 (2-3문장)",\n'
            '  "progress_rates": [{"database_id": "...", "rate": 0.0}],\n'
            '  "blockers": ["블로커 1", ...],\n'
            '  "next_actions": ["다음 액션 1", ...]\n'
            "}\n"
            "Return only valid JSON."
        )

        try:
            ai_report = ai._complete_structured(prompt, fallback={})
        except Exception as exc:
            ai_report = {"error": str(exc)}

        return {
            "databases": db_reports,
            "ai_report": ai_report,
            "total_databases": len(database_ids),
        }


