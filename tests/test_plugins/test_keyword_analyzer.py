from __future__ import annotations

from unittest.mock import MagicMock, patch

import notion_manager.client as _client_mod
from notion_manager.plugins.keyword_analyzer import KeywordAnalyzerPlugin


def _make_page(page_id: str) -> dict:
    return {"id": page_id, "properties": {}}


class TestKeywordAnalyzerPlugin:
    def setup_method(self):
        self.plugin = KeywordAnalyzerPlugin()
        self.config = {}

    def test_keyword_frequency(self):
        """Mock pages with known text, verify top keywords match expected."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1"),
            _make_page("p2"),
        ]
        # p1 has "python python python", p2 has "python notion"
        texts = ["python python python", "python notion"]
        mock_client.get_page_blocks.side_effect = [[], []]

        call_count = {"n": 0}

        def fake_blocks_to_text(blocks):
            idx = call_count["n"]
            call_count["n"] += 1
            return texts[idx]

        with patch.object(_client_mod.NotionClient, "blocks_to_text", staticmethod(fake_blocks_to_text)):
            result = self.plugin.execute(mock_client, self.config)

        assert result["pages_analyzed"] == 2
        words = [kw["word"] for kw in result["top_keywords"]]
        counts = {kw["word"]: kw["count"] for kw in result["top_keywords"]}
        assert "python" in words
        assert counts["python"] == 4
        assert "notion" in words

    def test_stop_words_filtered(self):
        """Text with common stop words should not appear in results."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_page("p1")]
        mock_client.get_page_blocks.return_value = []

        stop_heavy_text = "the and or but is are was were it its of in on at by for"

        with patch.object(
            _client_mod.NotionClient,
            "blocks_to_text",
            staticmethod(lambda b: stop_heavy_text),
        ):
            result = self.plugin.execute(mock_client, self.config)

        words = [kw["word"] for kw in result["top_keywords"]]
        stop_words = {"the", "and", "or", "but", "is", "are", "was", "were", "it", "its", "of", "in", "on", "at", "by", "for"}
        for w in words:
            assert w.lower() not in stop_words, f"Stop word '{w}' appeared in results"
