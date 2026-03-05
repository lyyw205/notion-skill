from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


class SentimentAnalyzerPlugin:
    name = "sentiment_analyzer"
    description = "콘텐츠 감정 분석 및 트렌드 추적"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        page_id: str | None = kwargs.get("page_id")
        database_id: str | None = kwargs.get("database_id")

        if page_id:
            try:
                blocks = client.get_page_blocks(page_id)
            except Exception as exc:
                return {"error": str(exc), "page_id": page_id}
            text = NotionClient.blocks_to_text(blocks)
            try:
                result = ai.analyze_sentiment(text)
            except Exception as exc:
                return {"error": str(exc), "page_id": page_id}
            return {
                "page_id": page_id,
                "sentiment": result.get("sentiment", "neutral"),
                "score": result.get("score", 0.0),
                "keywords": result.get("keywords", []),
            }

        if database_id:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc), "database_id": database_id}

            trend: list[dict] = []
            distribution: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
            total_score = 0.0

            for page in pages:
                pid = page.get("id", "")
                title = _get_title(page)
                try:
                    blocks = client.get_page_blocks(pid)
                    text = NotionClient.blocks_to_text(blocks)
                    result = ai.analyze_sentiment(text)
                    sentiment = result.get("sentiment", "neutral")
                    score = result.get("score", 0.0)
                except Exception:
                    sentiment = "neutral"
                    score = 0.0
                distribution[sentiment] = distribution.get(sentiment, 0) + 1
                total_score += score
                trend.append({"page_id": pid, "title": title, "sentiment": sentiment, "score": score})

            total = len(pages)
            avg_score = total_score / total if total > 0 else 0.0
            return {
                "database_id": database_id,
                "total_analyzed": total,
                "average_score": avg_score,
                "sentiment_distribution": distribution,
                "trend": trend,
            }

        return {"error": "page_id or database_id required"}


PLUGIN_CLASS = SentimentAnalyzerPlugin
