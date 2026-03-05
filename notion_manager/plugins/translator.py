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


class TranslatorPlugin:
    name = "translator"
    description = "페이지 콘텐츠 다국어 번역"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        target_lang: str = kwargs.get("target_lang", "en")
        create_page: bool = kwargs.get("create_page", True)

        ai = AIProvider(
            api_key=config.get("ai", {}).get("api_key", ""),
            model=config.get("ai", {}).get("model", "claude-sonnet-4-20250514"),
        )

        try:
            page = client.get_page(page_id)
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"error": str(exc)}

        original_title = _get_title(page)
        text = NotionClient.blocks_to_text(blocks)

        try:
            translated_content = ai.translate(text, target_lang)
        except Exception as exc:
            return {"error": str(exc)}

        new_page_id: str | None = None
        if create_page:
            new_title = f"{original_title} [{target_lang.upper()}]"
            new_page_data = {
                "parent": {"page_id": page_id},
                "properties": {
                    "title": {
                        "title": [{"type": "text", "text": {"content": new_title}}]
                    }
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": translated_content}}]
                        },
                    }
                ],
            }
            try:
                new_page = client.create_page(**new_page_data)
                new_page_id = new_page.get("id")
            except Exception as exc:
                return {
                    "page_id": page_id,
                    "target_lang": target_lang,
                    "translated_content": translated_content,
                    "new_page_id": None,
                    "create_error": str(exc),
                }

        return {
            "page_id": page_id,
            "target_lang": target_lang,
            "translated_content": translated_content,
            "new_page_id": new_page_id,
        }


