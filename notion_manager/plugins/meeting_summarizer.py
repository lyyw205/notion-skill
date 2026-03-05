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


class MeetingSummarizerPlugin:
    name = "meeting_summarizer"
    description = "회의록 요약 (결정사항/액션아이템 추출)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"error": str(exc)}

        text = NotionClient.blocks_to_text(blocks)

        try:
            result = ai.summarize_meeting(text)
        except Exception as exc:
            return {"error": str(exc)}

        return {
            "page_id": page_id,
            "decisions": result.get("decisions", []),
            "action_items": result.get("action_items", []),
            "attendees": result.get("attendees", []),
            "summary": result.get("summary", ""),
        }


PLUGIN_CLASS = MeetingSummarizerPlugin
