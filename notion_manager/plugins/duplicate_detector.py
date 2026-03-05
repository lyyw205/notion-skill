from __future__ import annotations

import difflib
from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class DuplicateDetectorPlugin:
    name = "duplicate_detector"
    description = "중복 페이지 탐지"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        threshold: float = kwargs.get("threshold", 0.8)

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        # Build list of (id, title) pairs
        page_data: list[dict[str, Any]] = []
        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)
            page_data.append({"id": pid, "title": title, "page": page})

        duplicates: list[dict[str, Any]] = []
        total = len(page_data)

        # Compare all pairs by title similarity
        for i in range(total):
            for j in range(i + 1, total):
                a = page_data[i]
                b = page_data[j]
                title_sim = difflib.SequenceMatcher(
                    None, a["title"].lower(), b["title"].lower()
                ).ratio()
                if title_sim >= threshold:
                    # Also compare content for stronger signal
                    content_sim = title_sim
                    try:
                        blocks_a = client.get_page_blocks(a["id"])
                        blocks_b = client.get_page_blocks(b["id"])
                        text_a = NotionClient.blocks_to_text(blocks_a)
                        text_b = NotionClient.blocks_to_text(blocks_b)
                        if text_a or text_b:
                            content_sim = difflib.SequenceMatcher(
                                None, text_a, text_b
                            ).ratio()
                    except Exception:
                        pass

                    avg_sim = (title_sim + content_sim) / 2
                    if avg_sim >= threshold:
                        duplicates.append(
                            {
                                "pages": [a["id"], b["id"]],
                                "similarity": round(avg_sim, 4),
                                "titles": [a["title"], b["title"]],
                            }
                        )

        return {
            "duplicates": duplicates,
            "total_checked": total,
        }


