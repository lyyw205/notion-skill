from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from notion_manager.plugins.semantic_search import SemanticSearchPlugin


def _make_chroma_mock(documents: list, metadatas: list, distances: list) -> MagicMock:
    """Build a mock chromadb module with a collection that returns given results."""
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


class TestSemanticSearchPlugin:
    def setup_method(self):
        self.plugin = SemanticSearchPlugin()
        self.config = {"search": {"chroma_path": ".chroma-test"}}

    def test_search_success(self):
        """Mock chromadb collection.query; verify results list is populated."""
        docs = ["Page content about Python", "Another page about testing"]
        metas = [
            {"page_id": "p1", "page_title": "Python Guide"},
            {"page_id": "p2", "page_title": "Testing Guide"},
        ]
        dists = [0.1, 0.3]

        mock_chromadb, mock_collection = _make_chroma_mock(docs, metas, dists)

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            result = self.plugin.execute(
                MagicMock(), self.config, query="Python testing", top_k=2
            )

        assert result.get("query") == "Python testing"
        results = result.get("results", [])
        assert len(results) == 2
        assert results[0]["page_id"] == "p1"
        assert results[0]["title"] == "Python Guide"
        assert results[0]["relevance"] == round(1.0 - 0.1, 4)
        mock_collection.query.assert_called_once()

    def test_no_results(self):
        """Empty query results should return an empty results list."""
        mock_chromadb, _ = _make_chroma_mock([], [], [])

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            result = self.plugin.execute(
                MagicMock(), self.config, query="nonexistent topic"
            )

        assert result.get("results") == []
        assert result.get("query") == "nonexistent topic"
