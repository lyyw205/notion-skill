from __future__ import annotations

import difflib
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


class PageMergerPlugin:
    name = "page_merger"
    description = "중복/관련 페이지 AI 병합 (dry_run 기본)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        source_page_id: str | None = kwargs.get("source_page_id")
        target_page_id: str | None = kwargs.get("target_page_id")
        dry_run: bool = kwargs.get("dry_run", True)

        if not source_page_id or not target_page_id:
            return {"error": "source_page_id and target_page_id required"}

        if source_page_id == target_page_id:
            return {"error": "source and target must be different pages"}

        try:
            source_page = client.get_page(source_page_id)
            target_page = client.get_page(target_page_id)
            source_blocks = client.get_page_blocks(source_page_id)
            target_blocks = client.get_page_blocks(target_page_id)
        except Exception as exc:
            return {"error": str(exc)}

        source_title = _extract_title(source_page)
        target_title = _extract_title(target_page)
        source_text = NotionClient.blocks_to_text(source_blocks)
        target_text = NotionClient.blocks_to_text(target_blocks)

        similarity = difflib.SequenceMatcher(None, source_text, target_text).ratio()

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=ai_config.get("max_tokens", 2048),
        )

        prompt = (
            "다음 두 노션 페이지의 콘텐츠를 분석하고 병합된 버전을 만들어주세요.\n\n"
            f"## 페이지 A: {source_title}\n{source_text[:2000]}\n\n"
            f"## 페이지 B: {target_title}\n{target_text[:2000]}\n\n"
            "중복 내용은 제거하고, 양쪽의 고유한 정보를 모두 포함해주세요.\n"
            "병합된 텍스트만 반환해주세요."
        )

        try:
            merged_content = ai._complete(prompt).strip()
        except Exception as exc:
            return {"error": f"AI merge failed: {exc}"}

        diff_lines = list(difflib.unified_diff(
            source_text.splitlines(),
            merged_content.splitlines(),
            fromfile=source_title,
            tofile="merged",
            lineterm="",
        ))

        result: dict[str, Any] = {
            "source_page_id": source_page_id,
            "target_page_id": target_page_id,
            "source_title": source_title,
            "target_title": target_title,
            "similarity": round(similarity, 4),
            "merged_content": merged_content,
            "diff": "\n".join(diff_lines[:100]),
            "dry_run": dry_run,
            "applied": False,
        }

        if not dry_run:
            try:
                # Archive source by prefixing title
                client.update_page(source_page_id, {
                    "title": {
                        "title": [{"type": "text", "text": {"content": f"[Archived] {source_title}"}}]
                    }
                })
                # Append merged content to target
                client.append_blocks(target_page_id, [
                    {
                        "object": "block",
                        "type": "divider",
                        "divider": {},
                    },
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": f"병합됨: {source_title}"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": merged_content[:2000]}}]
                        },
                    },
                ])
                result["applied"] = True
            except Exception as exc:
                result["apply_error"] = str(exc)

        return result


