from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.sentiment_analyzer import SentimentAnalyzerPlugin


def _make_page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


class TestSentimentAnalyzerPlugin:
    def setup_method(self):
        self.plugin = SentimentAnalyzerPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_single_page_sentiment(self):
        """Mock client + AI returning sentiment dict, verify result fields."""
        import notion_manager.client as _client_mod

        mock_client = MagicMock()
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "I am happy today!"}]}}
        ]

        with patch("notion_manager.plugins.sentiment_analyzer.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.analyze_sentiment.return_value = {
                "sentiment": "positive",
                "score": 0.8,
                "keywords": ["happy"],
            }
            MockAI.return_value = mock_ai

            with patch.object(_client_mod.NotionClient, "blocks_to_text", staticmethod(lambda b: "I am happy today!")):
                result = self.plugin.execute(mock_client, self.config, page_id="page-1")

        assert result["page_id"] == "page-1"
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.8
        assert "happy" in result["keywords"]

    def test_database_sentiment(self):
        """Mock search + multiple pages, verify sentiment_distribution and trend."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("p1", "Happy Page"),
            _make_page("p2", "Sad Page"),
            _make_page("p3", "Neutral Page"),
        ]
        mock_client.get_page_blocks.return_value = []

        sentiments = [
            {"sentiment": "positive", "score": 0.9, "keywords": ["great"]},
            {"sentiment": "negative", "score": 0.2, "keywords": ["bad"]},
            {"sentiment": "neutral", "score": 0.5, "keywords": []},
        ]
        call_count = {"n": 0}

        def fake_analyze(text):
            idx = call_count["n"]
            call_count["n"] += 1
            return sentiments[idx]

        with patch("notion_manager.plugins.sentiment_analyzer.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.analyze_sentiment.side_effect = fake_analyze
            MockAI.return_value = mock_ai

            import notion_manager.client as _client_mod
            with patch.object(_client_mod.NotionClient, "blocks_to_text", staticmethod(lambda b: "some text")):
                result = self.plugin.execute(mock_client, self.config, database_id="db-1")

        assert result["database_id"] == "db-1"
        assert result["total_analyzed"] == 3
        dist = result["sentiment_distribution"]
        assert dist["positive"] == 1
        assert dist["negative"] == 1
        assert dist["neutral"] == 1
        assert len(result["trend"]) == 3
