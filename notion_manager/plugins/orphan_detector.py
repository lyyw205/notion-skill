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


def _collect_mentioned_ids(blocks: list[dict[str, Any]]) -> set[str]:
    """Scan blocks for page mentions and link_to_page references."""
    ids: set[str] = set()

    def _scan(block: dict[str, Any]) -> None:
        btype = block.get("type", "")

        # link_to_page block type
        if btype == "link_to_page":
            link_data = block.get("link_to_page", {})
            ref_id = link_data.get("page_id") or link_data.get("database_id")
            if ref_id:
                ids.add(ref_id)

        # Scan rich_text in any block content for mentions
        content = block.get(btype, {})
        if isinstance(content, dict):
            rich_texts: list[dict[str, Any]] = content.get("rich_text", [])
            for rt in rich_texts:
                if rt.get("type") == "mention":
                    mention = rt.get("mention", {})
                    if mention.get("type") == "page":
                        ref_id = mention.get("page", {}).get("id")
                        if ref_id:
                            ids.add(ref_id)
                    elif mention.get("type") == "database":
                        ref_id = mention.get("database", {}).get("id")
                        if ref_id:
                            ids.add(ref_id)

        # Recurse into children
        for child in block.get("children", []):
            _scan(child)

    for block in blocks:
        _scan(block)

    return ids


class OrphanDetectorPlugin:
    name = "orphan_detector"
    description = "고아 페이지 탐지 (링크되지 않은 페이지)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        total_pages = len(pages)

        # Identify workspace-root pages (parent is workspace)
        workspace_page_ids: set[str] = set()
        all_page_ids: set[str] = set()

        for page in pages:
            pid = page.get("id", "")
            all_page_ids.add(pid)
            parent = page.get("parent", {})
            if parent.get("type") == "workspace":
                workspace_page_ids.add(pid)

        # Collect all referenced page IDs by scanning blocks
        referenced_ids: set[str] = set()

        for page in pages:
            pid = page.get("id", "")
            try:
                blocks = client.get_page_blocks(pid)
                found = _collect_mentioned_ids(blocks)
                referenced_ids.update(found)
            except Exception:
                continue

        # Also any page that is a child of another page is referenced by parent relationship
        for page in pages:
            parent = page.get("parent", {})
            parent_type = parent.get("type", "")
            if parent_type == "page_id":
                child_id = page.get("id", "")
                referenced_ids.add(child_id)

        # Orphans: workspace-root pages not referenced anywhere
        orphan_pages: list[dict[str, Any]] = []
        for page in pages:
            pid = page.get("id", "")
            if pid in workspace_page_ids and pid not in referenced_ids:
                orphan_pages.append(
                    {
                        "id": pid,
                        "title": _get_title(page),
                        "last_edited": page.get("last_edited_time", ""),
                    }
                )

        return {
            "orphan_pages": orphan_pages,
            "total_pages": total_pages,
            "orphan_count": len(orphan_pages),
        }


PLUGIN_CLASS = OrphanDetectorPlugin
