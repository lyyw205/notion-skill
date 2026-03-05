from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class PageQualityCheckerPlugin:
    name = "page_quality_checker"
    description = "AI 기반 페이지 콘텐츠 품질 평가 (완성도/구조/가독성)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        page_id: str | None = kwargs.get("page_id")
        if not page_id:
            return {"error": "page_id required"}

        try:
            page = client.get_page(page_id)
            blocks = client.get_page_blocks(page_id)
        except Exception as exc:
            return {"error": str(exc)}

        title = _extract_title(page)
        text = NotionClient.blocks_to_text(blocks)

        if not text.strip():
            return {
                "page_id": page_id,
                "title": title,
                "completeness": 0,
                "structure": 0,
                "readability": 0,
                "overall": 0,
                "suggestions": ["페이지에 콘텐츠가 없습니다."],
            }

        block_types = [b.get("type", "") for b in blocks]
        stats = {
            "total_blocks": len(blocks),
            "headings": sum(1 for t in block_types if t.startswith("heading")),
            "paragraphs": block_types.count("paragraph"),
            "lists": sum(1 for t in block_types if "list" in t),
            "todos": block_types.count("to_do"),
            "char_count": len(text),
        }

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        import json
        prompt = (
            "다음 노션 페이지의 콘텐츠 품질을 평가해주세요.\n\n"
            f"제목: {title}\n"
            f"블록 통계: {json.dumps(stats, ensure_ascii=False)}\n"
            f"본문 (앞 3000자):\n{text[:3000]}\n\n"
            "다음 JSON 형태로 응답해주세요:\n"
            "{\n"
            '  "completeness": 1-10 (내용의 완성도),\n'
            '  "structure": 1-10 (헤딩/섹션 구조화 정도),\n'
            '  "readability": 1-10 (가독성, 문단 길이, 명확성),\n'
            '  "suggestions": ["개선 제안 1", "개선 제안 2", ...]\n'
            "}\n"
            "Return only valid JSON."
        )

        try:
            result = ai._complete_structured(prompt, fallback={})
        except Exception as exc:
            return {"page_id": page_id, "title": title, "error": str(exc)}

        completeness = result.get("completeness", 5)
        structure = result.get("structure", 5)
        readability = result.get("readability", 5)
        overall = round((completeness + structure + readability) / 3, 1)

        return {
            "page_id": page_id,
            "title": title,
            "completeness": completeness,
            "structure": structure,
            "readability": readability,
            "overall": overall,
            "suggestions": result.get("suggestions", []),
            "block_stats": stats,
        }


