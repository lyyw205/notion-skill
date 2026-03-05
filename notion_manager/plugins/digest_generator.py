from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


class DigestGeneratorPlugin:
    name = "digest_generator"
    description = "주간/월간 다이제스트 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        period: str = kwargs.get("period", "weekly")
        create_page: bool = kwargs.get("create_page", False)

        days = 7 if period == "weekly" else 30
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=days)

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            pages = client.search(query="")
        except Exception as exc:
            return {"error": str(exc)}

        changed_pages = []
        for page in pages:
            last_edited = page.get("last_edited_time", "")
            if last_edited:
                try:
                    edited_dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                    if edited_dt >= cutoff:
                        changed_pages.append(page)
                except ValueError:
                    pass

        lines = []
        for page in changed_pages:
            title = _get_title(page)
            edited = page.get("last_edited_time", "")
            lines.append(f"- {title} (수정: {edited})")

        changes_text = "\n".join(lines) if lines else "변경된 페이지가 없습니다."

        try:
            digest = ai.generate_digest(changes_text)
        except Exception as exc:
            return {"error": str(exc)}

        created_page_id: str | None = None
        if create_page:
            title_text = f"{period.capitalize()} Digest ({now.strftime('%Y-%m-%d')})"
            new_page_data = {
                "parent": {"type": "workspace", "workspace": True},
                "properties": {
                    "title": {
                        "title": [{"type": "text", "text": {"content": title_text}}]
                    }
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": digest}}]
                        },
                    }
                ],
            }
            try:
                new_page = client._call(client._client.pages.create, **new_page_data)
                created_page_id = new_page.get("id")
            except Exception as exc:
                return {
                    "period": period,
                    "date_range": {"start": cutoff.isoformat(), "end": now.isoformat()},
                    "pages_changed": len(changed_pages),
                    "digest": digest,
                    "created_page_id": None,
                    "create_error": str(exc),
                }

        return {
            "period": period,
            "date_range": {"start": cutoff.isoformat(), "end": now.isoformat()},
            "pages_changed": len(changed_pages),
            "digest": digest,
            "created_page_id": created_page_id,
        }


PLUGIN_CLASS = DigestGeneratorPlugin
