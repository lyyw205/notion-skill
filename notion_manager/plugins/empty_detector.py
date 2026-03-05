from __future__ import annotations

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


class EmptyDetectorPlugin:
    name = "empty_detector"
    description = "빈 페이지/미완성 페이지 감지"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        min_chars: int = kwargs.get("min_chars", 100)

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        empty_pages: list[dict[str, Any]] = []
        incomplete_pages: list[dict[str, Any]] = []
        total_checked = len(pages)

        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)

            try:
                blocks = client.get_page_blocks(pid)
                text = NotionClient.blocks_to_text(blocks)
            except Exception as exc:
                incomplete_pages.append(
                    {"id": pid, "title": title, "char_count": 0, "error": str(exc)}
                )
                continue

            char_count = len(text.strip())

            if char_count == 0:
                empty_pages.append({"id": pid, "title": title})
            elif char_count < min_chars:
                incomplete_pages.append(
                    {"id": pid, "title": title, "char_count": char_count}
                )

        return {
            "empty_pages": empty_pages,
            "incomplete_pages": incomplete_pages,
            "total_checked": total_checked,
        }


PLUGIN_CLASS = EmptyDetectorPlugin
