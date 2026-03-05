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


class ContentExpanderPlugin:
    name = "content_expander"
    description = "짧은 메모를 구조화된 문서로 확장"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        style: str = kwargs.get("style", "formal")

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"error": str(exc)}

        text = NotionClient.blocks_to_text(blocks)
        original_chars = len(text)

        try:
            expanded_content = ai.expand_content(text, style)
        except Exception as exc:
            return {"error": str(exc)}

        expanded_chars = len(expanded_content)
        inserted = False

        new_block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": expanded_content}}]
            },
        }
        try:
            client.append_blocks(page_id, [new_block])
            inserted = True
        except Exception as exc:
            return {
                "page_id": page_id,
                "original_chars": original_chars,
                "expanded_chars": expanded_chars,
                "expanded_content": expanded_content,
                "inserted": False,
                "insert_error": str(exc),
            }

        return {
            "page_id": page_id,
            "original_chars": original_chars,
            "expanded_chars": expanded_chars,
            "expanded_content": expanded_content,
            "inserted": inserted,
        }


PLUGIN_CLASS = ContentExpanderPlugin
