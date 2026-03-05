from __future__ import annotations

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


class ReadingNotesPlugin:
    name = "reading_notes"
    description = "독서 노트 핵심 인사이트 추출"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            page = client.get_page(page_id)
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"error": str(exc)}

        title = _get_title(page)
        text = NotionClient.blocks_to_text(blocks)

        try:
            result = ai.extract_reading_notes(text)
        except Exception as exc:
            return {"error": str(exc)}

        return {
            "page_id": page_id,
            "title": title,
            "key_insights": result.get("key_insights", []),
            "main_concepts": result.get("main_concepts", []),
            "quotes": result.get("quotes", []),
            "summary": result.get("summary", ""),
        }


