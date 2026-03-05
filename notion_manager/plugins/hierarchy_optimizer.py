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


class HierarchyOptimizerPlugin:
    name = "hierarchy_optimizer"
    description = "계층 구조 분석 및 정리 제안"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        max_depth: int = kwargs.get("max_depth", 5)

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        # Build id -> page info map and parent map
        page_map: dict[str, dict[str, Any]] = {}
        children_map: dict[str, list[str]] = {}

        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)
            parent = page.get("parent", {})
            parent_type = parent.get("type", "")
            parent_id: str | None = None

            if parent_type == "page_id":
                parent_id = parent.get("page_id")
            elif parent_type == "database_id":
                parent_id = parent.get("database_id")

            page_map[pid] = {
                "id": pid,
                "title": title,
                "parent_id": parent_id,
                "parent_type": parent_type,
            }
            children_map.setdefault(pid, [])
            if parent_id:
                children_map.setdefault(parent_id, [])
                children_map[parent_id].append(pid)

        # Calculate depth for each page (BFS from roots)
        depths: dict[str, int] = {}
        roots = [
            pid
            for pid, info in page_map.items()
            if info["parent_id"] is None or info["parent_id"] not in page_map
        ]

        queue = [(pid, 0) for pid in roots]
        while queue:
            current_id, depth = queue.pop(0)
            depths[current_id] = depth
            for child_id in children_map.get(current_id, []):
                if child_id not in depths:
                    queue.append((child_id, depth + 1))

        # Any page not yet visited gets depth 0
        for pid in page_map:
            if pid not in depths:
                depths[pid] = 0

        too_deep: list[dict[str, Any]] = []
        for pid, depth in depths.items():
            if depth > max_depth:
                info = page_map.get(pid, {})
                too_deep.append(
                    {"id": pid, "title": info.get("title", ""), "depth": depth}
                )

        # Root pages with 0 children = potentially too flat
        root_child_counts = [len(children_map.get(pid, [])) for pid in roots]
        too_flat_roots = sum(1 for c in root_child_counts if c == 0)

        all_depths = list(depths.values())
        avg_depth = sum(all_depths) / len(all_depths) if all_depths else 0.0
        actual_max_depth = max(all_depths) if all_depths else 0

        stats: dict[str, Any] = {
            "max_depth": actual_max_depth,
            "avg_depth": round(avg_depth, 2),
            "total_pages": len(page_map),
            "too_deep": too_deep,
            "too_flat_roots": too_flat_roots,
        }

        suggestions = ""
        ai_config = config.get("ai", {})
        if ai_config.get("api_key"):
            try:
                from notion_manager.ai_provider import AIProvider

                ai = AIProvider(
                    api_key=ai_config["api_key"],
                    model=ai_config.get("model", "claude-opus-4-5"),
                    max_tokens=ai_config.get("max_tokens", 512),
                )
                prompt_data = (
                    f"Notion workspace hierarchy stats:\n"
                    f"- Total pages: {stats['total_pages']}\n"
                    f"- Max depth: {stats['max_depth']} (limit: {max_depth})\n"
                    f"- Average depth: {stats['avg_depth']}\n"
                    f"- Pages too deep: {len(too_deep)}\n"
                    f"- Flat root pages (no children): {too_flat_roots}\n\n"
                    "Provide 3 concise suggestions to improve the hierarchy structure."
                )
                suggestions = ai._complete(prompt_data).strip()
            except Exception:
                pass

        return {"stats": stats, "suggestions": suggestions}


PLUGIN_CLASS = HierarchyOptimizerPlugin
