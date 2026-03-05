from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


class SummarizerPlugin:
    name = "summarizer"
    description = "페이지 내용을 AI로 요약"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        page_id: str | None = kwargs.get("page_id")
        database_id: str | None = kwargs.get("database_id")
        insert: bool = kwargs.get("insert", False)

        if database_id:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc), "database_id": database_id}
            results = []
            for page in pages:
                pid = page.get("id", "")
                result = self._summarize_page(client, ai, pid, insert)
                results.append(result)
            return results

        if page_id:
            return self._summarize_page(client, ai, page_id, insert)

        return {"error": "page_id or database_id required"}

    def _summarize_page(
        self,
        client: NotionClient,
        ai: AIProvider,
        page_id: str,
        insert: bool,
    ) -> dict:
        try:
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"page_id": page_id, "error": str(exc), "summary": None, "inserted": False}

        text = NotionClient.blocks_to_text(blocks)

        if len(text) < 100:
            return {
                "page_id": page_id,
                "summary": None,
                "inserted": False,
                "skipped": True,
                "reason": "text too short",
            }

        try:
            summary = ai.summarize(text)
        except Exception as exc:
            return {"page_id": page_id, "error": str(exc), "summary": None, "inserted": False}

        inserted = False
        if insert:
            callout_block = {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": summary}}],
                    "icon": {"type": "emoji", "emoji": "📝"},
                    "color": "blue_background",
                },
            }
            try:
                client.append_blocks(page_id, [callout_block])
                inserted = True
            except Exception as exc:
                return {
                    "page_id": page_id,
                    "summary": summary,
                    "inserted": False,
                    "insert_error": str(exc),
                }

        return {"page_id": page_id, "summary": summary, "inserted": inserted}


PLUGIN_CLASS = SummarizerPlugin
