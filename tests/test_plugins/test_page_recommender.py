from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from notion_manager.plugins.page_recommender import PageRecommenderPlugin


def _make_chroma_mock(metadatas: list, distances: list) -> tuple:
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["doc text"] * len(metadatas)],
        "metadatas": [metadatas],
        "distances": [distances],
    }
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_chroma_client

    return mock_chromadb, mock_collection


class TestPageRecommenderPlugin:
    def setup_method(self):
        self.plugin = PageRecommenderPlugin()
        self.config = {"search": {"chroma_path": ".chroma-test"}}

    def test_recommend_success(self):
        """Mock client and chromadb; verify recommendations list is populated."""
        mock_client = MagicMock()
        # blocks_to_text is a static method — patch it on the class
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Some page content here."}]}}
        ]

        metas = [
            {"page_id": "src-page", "page_title": "Source"},   # same page — should be filtered
            {"page_id": "rec1", "page_title": "Recommended One"},
            {"page_id": "rec2", "page_title": "Recommended Two"},
        ]
        dists = [0.0, 0.2, 0.35]

        mock_chromadb, mock_collection = _make_chroma_mock(metas, dists)

        with patch.dict(sys.modules, {"chromadb": mock_chromadb}):
            with patch("notion_manager.plugins.page_recommender.NotionClient") as MockNC:
                MockNC.blocks_to_text.return_value = "Some page content here."

                result = self.plugin.execute(
                    mock_client, self.config, page_id="src-page", top_k=5
                )

        assert result.get("page_id") == "src-page"
        recs = result.get("recommendations", [])
        # src-page itself must be excluded
        rec_ids = [r["page_id"] for r in recs]
        assert "src-page" not in rec_ids
        assert "rec1" in rec_ids
        assert "rec2" in rec_ids

    def test_missing_page_id(self):
        """No page_id kwarg should return error without calling chromadb."""
        mock_client = MagicMock()

        result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
