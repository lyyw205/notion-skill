from __future__ import annotations

import collections
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


class TemplateGeneratorPlugin:
    name = "template_generator"
    description = "페이지 패턴 분석 기반 템플릿 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        page_ids: list[str] | None = kwargs.get("page_ids")

        pages: list[dict] = []

        if database_id:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc)}
        elif page_ids:
            for pid in page_ids:
                try:
                    page = client.get_page(pid)
                    pages.append(page)
                except Exception:
                    continue
        else:
            try:
                pages = client.search("", filter_type="page")
            except Exception as exc:
                return {"error": str(exc)}

        block_type_sequences: list[list[str]] = []

        for page in pages:
            pid = page.get("id", "")
            try:
                blocks = client.get_page_blocks(pid)
            except Exception:
                continue
            seq = [b.get("type", "unknown") for b in blocks]
            if seq:
                block_type_sequences.append(seq)

        # Count block type frequencies across all pages
        type_counter: collections.Counter = collections.Counter()
        for seq in block_type_sequences:
            type_counter.update(seq)

        common_structure = [
            {"block_type": btype, "frequency": count}
            for btype, count in type_counter.most_common()
        ]

        # Build pattern summary for AI
        pattern_text = "\n".join(
            f"- {item['block_type']}: {item['frequency']} times"
            for item in common_structure[:20]
        )
        pages_summary = f"Analyzed {len(block_type_sequences)} pages.\nCommon block types:\n{pattern_text}"

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            template_suggestion = ai.summarize(pages_summary, max_sentences=10)
        except Exception as exc:
            template_suggestion = f"AI error: {exc}"

        return {
            "analyzed_pages": len(block_type_sequences),
            "common_structure": common_structure,
            "template_suggestion": template_suggestion,
        }


