from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


class PageRecommenderPlugin:
    name = "page_recommender"
    description = "관련 페이지 추천"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        page_id: str | None = kwargs.get("page_id")
        top_k: int = kwargs.get("top_k", 5)

        if not page_id:
            return {"error": "page_id required"}

        try:
            import chromadb
        except ImportError:
            return {"error": "chromadb is required for PageRecommenderPlugin. Install with: pip install chromadb"}

        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            collection = chroma_client.get_or_create_collection("notion_pages")
        except Exception as exc:
            return {"error": f"ChromaDB error: {exc}"}

        # Get page text to use as query
        try:
            blocks = client.get_page_blocks(page_id)
            page_text = NotionClient.blocks_to_text(blocks)
        except Exception as exc:
            return {"error": f"failed to fetch page: {exc}"}

        if not page_text.strip():
            return {"page_id": page_id, "recommendations": [], "reason": "source page has no text"}

        # Query for similar content, fetch more to allow filtering out source page
        fetch_k = top_k + 10
        try:
            results = collection.query(query_texts=[page_text[:2000]], n_results=fetch_k)
        except Exception as exc:
            return {"error": f"query failed: {exc}"}

        documents: list[str] = results.get("documents", [[]])[0]
        metadatas: list[dict] = results.get("metadatas", [[]])[0]
        distances: list[float] = results.get("distances", [[]])[0]

        recommendations: list[dict] = []
        seen_page_ids: set[str] = set()

        for meta, dist in zip(metadatas, distances):
            pid = meta.get("page_id", "")
            if pid == page_id:
                continue
            if pid in seen_page_ids:
                continue
            seen_page_ids.add(pid)
            relevance = max(0.0, 1.0 - dist)
            recommendations.append({
                "page_id": pid,
                "title": meta.get("page_title", ""),
                "relevance": round(relevance, 4),
            })
            if len(recommendations) >= top_k:
                break

        return {
            "page_id": page_id,
            "recommendations": recommendations,
        }


PLUGIN_CLASS = PageRecommenderPlugin
