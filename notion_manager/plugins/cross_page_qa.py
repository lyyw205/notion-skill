from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


class CrossPageQAPlugin:
    name = "cross_page_qa"
    description = "멀티소스 RAG 기반 Q&A"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        question: str | None = kwargs.get("question")
        page_ids: list[str] | None = kwargs.get("page_ids")
        top_k: int = kwargs.get("top_k", 10)

        if not question:
            return {"error": "question required"}

        try:
            import chromadb
        except ImportError:
            return {"error": "chromadb is required for CrossPageQAPlugin. Install with: pip install chromadb"}

        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            collection = chroma_client.get_or_create_collection("notion_pages")
        except Exception as exc:
            return {"error": f"ChromaDB error: {exc}"}

        try:
            query_kwargs: dict[str, Any] = {"query_texts": [question], "n_results": top_k}
            if page_ids:
                query_kwargs["where"] = {"page_id": {"$in": page_ids}}
            results = collection.query(**query_kwargs)
        except Exception as exc:
            return {"error": f"query failed: {exc}"}

        documents: list[str] = results.get("documents", [[]])[0]
        metadatas: list[dict] = results.get("metadatas", [[]])[0]
        distances: list[float] = results.get("distances", [[]])[0]

        context_parts: list[str] = []
        sources: list[dict] = []

        for doc, meta, dist in zip(documents, metadatas, distances):
            context_parts.append(doc)
            relevance = max(0.0, 1.0 - dist)
            sources.append({
                "page_id": meta.get("page_id", ""),
                "title": meta.get("page_title", ""),
                "relevance": round(relevance, 4),
            })

        context = "\n\n---\n\n".join(context_parts)

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            answer = ai.answer_question(question, context)
        except Exception as exc:
            return {"question": question, "error": str(exc), "sources": sources}

        # Estimate confidence from average relevance of top sources
        confidence = 0.0
        if sources:
            confidence = round(sum(s["relevance"] for s in sources) / len(sources), 4)

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
        }


