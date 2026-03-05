from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


class ContentGraphPlugin:
    name = "content_graph"
    description = "콘텐츠 연결 그래프 분석"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": str(exc)}

        nodes: list[dict] = []
        edges: list[dict] = []
        connection_count: dict[str, int] = {}

        page_map: dict[str, str] = {}
        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)
            page_map[pid] = title
            nodes.append({"id": pid, "title": title})
            connection_count[pid] = 0

        for page in pages:
            source_id = page.get("id", "")
            try:
                blocks = client.get_page_blocks(source_id)
            except Exception:
                continue
            for block in blocks:
                # Check for mention in rich_text
                btype = block.get("type", "")
                content = block.get(btype, {})
                rich_texts = content.get("rich_text", [])
                for rt in rich_texts:
                    if rt.get("type") == "mention":
                        mention = rt.get("mention", {})
                        if mention.get("type") == "page":
                            target_id = mention.get("page", {}).get("id", "")
                            if target_id and target_id != source_id:
                                edges.append({"source": source_id, "target": target_id, "type": "mention"})
                                connection_count[source_id] = connection_count.get(source_id, 0) + 1
                                if target_id in connection_count:
                                    connection_count[target_id] = connection_count.get(target_id, 0) + 1
                # Check for link_to_page block type
                if btype == "link_to_page":
                    link = block.get("link_to_page", {})
                    target_id = link.get("page_id", "")
                    if target_id and target_id != source_id:
                        edges.append({"source": source_id, "target": target_id, "type": "link"})
                        connection_count[source_id] = connection_count.get(source_id, 0) + 1
                        if target_id in connection_count:
                            connection_count[target_id] = connection_count.get(target_id, 0) + 1

        sorted_by_connections = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)
        most_connected = [
            {"id": pid, "title": page_map.get(pid, pid), "connections": count}
            for pid, count in sorted_by_connections[:5]
        ]
        isolated = [
            {"id": pid, "title": page_map.get(pid, pid)}
            for pid, count in connection_count.items()
            if count == 0
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "most_connected": most_connected,
            "isolated": isolated,
        }


PLUGIN_CLASS = ContentGraphPlugin
