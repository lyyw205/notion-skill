from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


class SemanticSearchPlugin:
    name = "semantic_search"
    description = "임베딩 기반 시맨틱 검색"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        query: str | None = kwargs.get("query")
        top_k: int = kwargs.get("top_k", 5)

        if not query:
            return {"error": "query required"}

        try:
            import chromadb
        except ImportError:
            return {"error": "chromadb is required for SemanticSearchPlugin. Install with: pip install chromadb"}

        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            collection = chroma_client.get_or_create_collection("notion_pages")
        except Exception as exc:
            return {"error": f"ChromaDB error: {exc}"}

        try:
            results = collection.query(query_texts=[query], n_results=top_k)
        except Exception as exc:
            return {"error": f"query failed: {exc}"}

        documents: list[str] = results.get("documents", [[]])[0]
        metadatas: list[dict] = results.get("metadatas", [[]])[0]
        distances: list[float] = results.get("distances", [[]])[0]

        output_results: list[dict] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            relevance = max(0.0, 1.0 - dist)
            output_results.append({
                "page_id": meta.get("page_id", ""),
                "title": meta.get("page_title", ""),
                "snippet": doc[:300],
                "relevance": round(relevance, 4),
            })

        return {
            "query": query,
            "results": output_results,
        }


PLUGIN_CLASS = SemanticSearchPlugin
