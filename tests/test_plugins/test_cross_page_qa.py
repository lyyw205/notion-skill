from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from notion_manager.plugins.cross_page_qa import CrossPageQAPlugin


def _make_chroma_mock(documents: list, metadatas: list, distances: list) -> tuple:
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [documents],
        "metadatas": [metadatas],
        "distances": [distances],
    }
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_chroma_client

    return mock_chromadb, mock_collection


class TestCrossPageQAPlugin:
    def setup_method(self):
        self.plugin = CrossPageQAPlugin()
        self.config = {
            "search": {"chroma_path": ".chroma-test"},
            "ai": {"api_key": "fake-key", "model": "claude-opus-4-5"},
        }

    def test_qa_success(self):
        """Mock chromadb and AI; verify answer and sources are returned."""
        docs = ["Context about topic A.", "Context about topic B."]
        metas = [
            {"page_id": "p1", "page_title": "Topic A"},
            {"page_id": "p2", "page_title": "Topic B"},
        ]
        dists = [0.2, 0.4]

        mock_chromadb, mock_collection = _make_chroma_mock(docs, metas, dists)

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            with patch("notion_manager.plugins.cross_page_qa.AIProvider") as MockAI:
                mock_ai = MagicMock()
                mock_ai.answer_question.return_value = "The answer is 42."
                MockAI.return_value = mock_ai

                result = self.plugin.execute(
                    MagicMock(), self.config, question="What is the answer?"
                )

        assert result.get("answer") == "The answer is 42."
        sources = result.get("sources", [])
        assert len(sources) == 2
        assert sources[0]["page_id"] == "p1"
        assert "confidence" in result
        mock_collection.query.assert_called_once()

    def test_missing_question(self):
        """No question kwarg should return error without calling chromadb."""
        mock_client = MagicMock()

        result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
