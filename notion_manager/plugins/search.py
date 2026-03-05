from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into chunks of approximately chunk_size characters."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end
    return chunks


def _get_page_title(page: dict[str, Any]) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class SearchPlugin:
    name = "search"
    description = "노션 콘텐츠 자연어 검색 및 Q&A"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        action: str = kwargs.get("action", "query")

        if action == "index":
            return self._index(client, config)
        elif action == "query":
            question: str | None = kwargs.get("question")
            if not question:
                return {"error": "question required for action=query"}
            top_k: int = kwargs.get("top_k", 5)
            return self._query(client, config, question, top_k)
        else:
            return {"error": f"unknown action: {action}. Use 'index' or 'query'"}

    def _get_collection(self, chroma_path: str = ".chroma") -> Any:
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("chromadb is required for SearchPlugin. Install with: pip install chromadb")

        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection(name="notion_pages")
        return collection

    def _index(self, client: NotionClient, config: dict) -> dict:
        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            collection = self._get_collection(chroma_path)
        except RuntimeError as exc:
            return {"error": str(exc)}

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        total_chunks = 0
        indexed_pages = 0

        for page in pages:
            page_id = page.get("id", "")
            title = _get_page_title(page)

            try:
                blocks = client.get_page_blocks(page_id)
                text = NotionClient.blocks_to_text(blocks)
            except Exception:
                continue

            if not text.strip():
                continue

            chunks = _chunk_text(text)
            chunk_ids = [f"{page_id}__chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {"page_id": page_id, "page_title": title, "chunk_index": i}
                for i in range(len(chunks))
            ]

            try:
                collection.upsert(
                    ids=chunk_ids,
                    documents=chunks,
                    metadatas=metadatas,
                )
                total_chunks += len(chunks)
                indexed_pages += 1
            except Exception:
                continue

        return {
            "action": "index",
            "indexed_pages": indexed_pages,
            "total_chunks": total_chunks,
        }

    def _query(
        self,
        client: NotionClient,
        config: dict,
        question: str,
        top_k: int,
    ) -> dict:
        chroma_path = config.get("search", {}).get("chroma_path", ".chroma")

        try:
            collection = self._get_collection(chroma_path)
        except RuntimeError as exc:
            return {"error": str(exc)}

        try:
            results = collection.query(query_texts=[question], n_results=top_k)
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
            sources.append(
                {
                    "page_id": meta.get("page_id", ""),
                    "title": meta.get("page_title", ""),
                    "relevance": round(relevance, 4),
                }
            )

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

        return {"question": question, "answer": answer, "sources": sources}


