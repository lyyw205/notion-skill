from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


def _extract_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class RelationLinkerPlugin:
    name = "relation_linker"
    description = "콘텐츠 유사도 기반 DB Relation 자동 연결 제안"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        relation_property: str | None = kwargs.get("relation_property")
        if not relation_property:
            return {"error": "relation_property required"}

        similarity_threshold: float = kwargs.get("similarity_threshold", 0.7)
        dry_run: bool = kwargs.get("dry_run", True)

        try:
            import chromadb
        except ImportError:
            return {"error": "chromadb required. Install with: pip install chromadb"}

        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            collection = chroma_client.get_or_create_collection("notion_pages")
        except Exception as exc:
            return {"error": f"ChromaDB error: {exc}"}

        try:
            pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        suggestions: list[dict[str, Any]] = []
        linked: list[dict[str, Any]] = []

        for page in pages:
            pid = page.get("id", "")
            title = _extract_title(page)

            try:
                blocks = client.get_page_blocks(pid)
                text = NotionClient.blocks_to_text(blocks)
            except Exception:
                continue

            if not text.strip():
                continue

            try:
                results = collection.query(query_texts=[text[:1000]], n_results=5)
            except Exception:
                continue

            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for meta, dist in zip(metadatas, distances):
                relevance = max(0.0, 1.0 - dist)
                target_id = meta.get("page_id", "")

                if target_id == pid or relevance < similarity_threshold:
                    continue

                suggestion = {
                    "source_page_id": pid,
                    "source_title": title,
                    "target_page_id": target_id,
                    "target_title": meta.get("page_title", ""),
                    "similarity": round(relevance, 4),
                }
                suggestions.append(suggestion)

                if not dry_run:
                    try:
                        client.update_page(pid, {
                            relation_property: {
                                "relation": [{"id": target_id}]
                            }
                        })
                        linked.append(suggestion)
                    except Exception:
                        continue

        # Deduplicate suggestions (A->B and B->A)
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            pair = tuple(sorted([s["source_page_id"], s["target_page_id"]]))
            if pair not in seen:
                seen.add(pair)
                unique_suggestions.append(s)

        return {
            "database_id": database_id,
            "dry_run": dry_run,
            "suggestions": unique_suggestions,
            "linked": linked,
            "total_suggestions": len(unique_suggestions),
            "total_linked": len(linked),
        }


