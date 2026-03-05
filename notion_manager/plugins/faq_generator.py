from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class FAQGeneratorPlugin:
    name = "faq_generator"
    description = "문서 기반 FAQ 자동 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        page_id: str | None = kwargs.get("page_id")
        database_id: str | None = kwargs.get("database_id")
        create_page: bool = kwargs.get("create_page", False)
        parent_page_id: str | None = kwargs.get("parent_page_id")

        source_pages: list[str] = []
        all_text_parts: list[str] = []

        if database_id:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc)}
            for page in pages:
                pid = page.get("id", "")
                try:
                    blocks = client.get_page_blocks(pid)
                    text = NotionClient.blocks_to_text(blocks)
                    if text.strip():
                        all_text_parts.append(text)
                        source_pages.append(pid)
                except Exception:
                    continue
        elif page_id:
            try:
                blocks = client.get_page_blocks(page_id)
                text = NotionClient.blocks_to_text(blocks)
                all_text_parts.append(text)
                source_pages.append(page_id)
            except Exception as exc:
                return {"error": str(exc)}
        else:
            return {"error": "page_id or database_id required"}

        combined_text = "\n\n".join(all_text_parts)

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            faqs = ai.generate_faq(combined_text)
        except Exception as exc:
            return {"error": str(exc)}

        created_page_id: str | None = None

        if create_page and parent_page_id:
            children: list[dict] = []
            for faq in faqs:
                q = faq.get("question", "")
                a = faq.get("answer", "")
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": q}}]
                    },
                })
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": a}}]
                    },
                })
            try:
                page = client.create_page(
                    parent={"page_id": parent_page_id},
                    properties={
                        "title": {
                            "title": [{"type": "text", "text": {"content": "FAQ"}}]
                        }
                    },
                    children=children,
                )
                created_page_id = page.get("id", "")
            except Exception as exc:
                return {
                    "source_pages": source_pages,
                    "faqs": faqs,
                    "created_page_id": None,
                    "create_error": str(exc),
                }

        return {
            "source_pages": source_pages,
            "faqs": faqs,
            "created_page_id": created_page_id,
        }


