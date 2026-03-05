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


class BulletConverterPlugin:
    name = "bullet_converter"
    description = "장문 → 글머리 변환"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        replace: bool = kwargs.get("replace", False)

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
            bullet_points = ai.convert_to_bullets(text)
        except Exception as exc:
            return {"error": str(exc)}

        replaced = False
        if replace:
            # Delete existing blocks and append bullet list blocks
            for block in blocks:
                try:
                    client._call(client._client.blocks.delete, block_id=block["id"])
                except Exception:
                    pass

            new_blocks = [
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": point}}]
                    },
                }
                for point in bullet_points
            ]
            try:
                client.append_blocks(page_id, new_blocks)
                replaced = True
            except Exception as exc:
                return {
                    "page_id": page_id,
                    "original_chars": original_chars,
                    "bullet_points": bullet_points,
                    "replaced": False,
                    "replace_error": str(exc),
                }

        return {
            "page_id": page_id,
            "original_chars": original_chars,
            "bullet_points": bullet_points,
            "replaced": replaced,
        }


