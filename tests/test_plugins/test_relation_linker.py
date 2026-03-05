from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from notion_manager.plugins.relation_linker import RelationLinkerPlugin

CONFIG = {"search": {"chroma_path": "/tmp/test_chroma"}}


def _patch_chromadb(mock_collection):
    """Create a mock chromadb module and patch it into sys.modules."""
    mock_chroma_mod = MagicMock()
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection
    mock_chroma_mod.PersistentClient.return_value = mock_chroma_client
    return patch.dict(sys.modules, {"chromadb": mock_chroma_mod})


class TestRelationLinkerPlugin:
    def setup_method(self):
        self.plugin = RelationLinkerPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_missing_relation_property(self):
        result = self.plugin.execute(MagicMock(), CONFIG, database_id="db-1")
        assert "error" in result

    def test_suggest_similar_pages(self):
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            {"id": "p1", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Python Guide"}]}}},
        ]
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Python programming tutorial"}]}}
        ]

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Python basics"]],
            "metadatas": [[{"page_id": "p2", "page_title": "Python Basics"}]],
            "distances": [[0.2]],
        }

        with _patch_chromadb(mock_collection):
            # Re-import to pick up mocked chromadb
            import importlib
            import notion_manager.plugins.relation_linker as rl_mod
            importlib.reload(rl_mod)
            plugin = rl_mod.RelationLinkerPlugin()

            result = plugin.execute(
                mock_client, CONFIG,
                database_id="db-1",
                relation_property="Related",
            )

        assert result["total_suggestions"] == 1
        assert result["suggestions"][0]["similarity"] == 0.8
        assert result["dry_run"] is True
        assert result["total_linked"] == 0

    def test_dry_run_false_links_pages(self):
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            {"id": "p1", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Page A"}]}}},
        ]
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content"}]}}
        ]
        mock_client.update_page.return_value = {}

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Similar"]],
            "metadatas": [[{"page_id": "p2", "page_title": "Page B"}]],
            "distances": [[0.1]],
        }

        with _patch_chromadb(mock_collection):
            import importlib
            import notion_manager.plugins.relation_linker as rl_mod
            importlib.reload(rl_mod)
            plugin = rl_mod.RelationLinkerPlugin()

            result = plugin.execute(
                mock_client, CONFIG,
                database_id="db-1",
                relation_property="Related",
                dry_run=False,
            )

        assert result["total_linked"] == 1
        mock_client.update_page.assert_called_once()
