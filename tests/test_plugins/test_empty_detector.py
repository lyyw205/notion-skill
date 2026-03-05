from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.empty_detector import EmptyDetectorPlugin


def _make_page(pid: str, title: str) -> dict:
    return {
        "id": pid,
        "last_edited_time": "2025-01-01T00:00:00.000Z",
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestEmptyDetectorPlugin:
    def setup_method(self):
        self.plugin = EmptyDetectorPlugin()
        self.config = {}

    def test_detects_empty(self):
        """A page with no blocks (zero chars) appears in empty_pages."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_page("p1", "Empty Page")]
        mock_client.get_page_blocks.return_value = []

        import notion_manager.plugins.empty_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: "")

        try:
            result = self.plugin.execute(mock_client, self.config, min_chars=100)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert any(p["id"] == "p1" for p in result["empty_pages"])
        assert result["incomplete_pages"] == []

    def test_detects_incomplete(self):
        """A page with short text (< 100 chars) appears in incomplete_pages."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_page("p2", "Short Page")]
        mock_client.get_page_blocks.return_value = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hi"}]}}
        ]

        import notion_manager.plugins.empty_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: "Hi")

        try:
            result = self.plugin.execute(mock_client, self.config, min_chars=100)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert result["empty_pages"] == []
        assert any(p["id"] == "p2" for p in result["incomplete_pages"])

    def test_full_page_ok(self):
        """A page with > 100 chars appears in neither list."""
        mock_client = MagicMock()
        mock_client.search.return_value = [_make_page("p3", "Full Page")]
        mock_client.get_page_blocks.return_value = []
        long_text = "A" * 150

        import notion_manager.plugins.empty_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: long_text)

        try:
            result = self.plugin.execute(mock_client, self.config, min_chars=100)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert result["empty_pages"] == []
        assert result["incomplete_pages"] == []
        assert result["total_checked"] == 1
