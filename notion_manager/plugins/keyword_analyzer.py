from __future__ import annotations

import re
from collections import Counter
from typing import Any

from notion_manager.client import NotionClient

STOP_WORDS: set[str] = {
    # Korean particles
    "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "로",
    "에서", "까지", "부터", "만", "보다", "처럼",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "shall", "should", "may",
    "might", "can", "could", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "this", "that", "these",
    "those", "it", "its", "of", "not", "no", "so",
}


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


class KeywordAnalyzerPlugin:
    name = "keyword_analyzer"
    description = "키워드 빈도 분석"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        page_ids: list[str] | None = kwargs.get("page_ids")
        database_id: str | None = kwargs.get("database_id")
        top_k: int = int(kwargs.get("top_k", 20))

        pages: list[dict] = []

        if database_id:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc)}
        elif page_ids:
            for pid in page_ids:
                try:
                    page = client.get_page(pid)
                    pages.append(page)
                except Exception:
                    pass
        else:
            try:
                pages = client.search("", filter_type="page")
            except Exception as exc:
                return {"error": str(exc)}

        all_words: list[str] = []
        pages_analyzed = 0

        for page in pages:
            pid = page.get("id", "")
            try:
                blocks = client.get_page_blocks(pid)
                text = NotionClient.blocks_to_text(blocks)
            except Exception:
                continue
            tokens = re.split(r"[\s\W]+", text)
            for token in tokens:
                word = token.strip()
                if len(word) >= 2 and word.lower() not in STOP_WORDS:
                    all_words.append(word)
            pages_analyzed += 1

        counter = Counter(all_words)
        top_keywords = [
            {"word": word, "count": count}
            for word, count in counter.most_common(top_k)
        ]

        return {
            "total_words": len(all_words),
            "unique_words": len(counter),
            "top_keywords": top_keywords,
            "pages_analyzed": pages_analyzed,
        }


