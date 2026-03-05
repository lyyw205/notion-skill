from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


class TaggerPlugin:
    name = "tagger"
    description = "페이지 내용 기반 자동 태그 분류"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        available_tags: list[str] | None = kwargs.get("available_tags")
        tag_property: str = kwargs.get("tag_property", "Tags")

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"page_id": page_id, "error": str(exc), "tags": [], "updated": False}

        text = NotionClient.blocks_to_text(blocks)

        try:
            tags = ai.classify_tags(text, available_tags)
        except Exception as exc:
            return {"page_id": page_id, "error": str(exc), "tags": [], "updated": False}

        multi_select_value = [{"name": tag} for tag in tags]
        properties = {tag_property: {"multi_select": multi_select_value}}

        try:
            client.update_page(page_id, properties)
            updated = True
        except Exception as exc:
            return {
                "page_id": page_id,
                "tags": tags,
                "updated": False,
                "update_error": str(exc),
            }

        return {"page_id": page_id, "tags": tags, "updated": updated}


PLUGIN_CLASS = TaggerPlugin
