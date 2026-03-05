from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.duplicate_detector import DuplicateDetectorPlugin


def _make_page(pid: str, title: str, parent_type: str = "workspace") -> dict:
    return {
        "id": pid,
        "last_edited_time": "2025-01-01T00:00:00.000Z",
        "parent": {"type": parent_type, "workspace": True},
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestDuplicateDetectorPlugin:
    def setup_method(self):
        self.plugin = DuplicateDetectorPlugin()
        self.config = {}

    def test_no_duplicates(self):
        """Pages with completely different titles produce an empty duplicates list."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Meeting Notes"),
            _make_page("p2", "Project Roadmap"),
            _make_page("p3", "Budget 2025"),
        ]
        mock_client.get_page_blocks.return_value = []
        mock_client.blocks_to_text = MagicMock(return_value="")

        # Patch the static method on NotionClient via the module
        import notion_manager.plugins.duplicate_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: "")

        try:
            result = self.plugin.execute(mock_client, self.config, threshold=0.8)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert result["duplicates"] == []
        assert result["total_checked"] == 3

    def test_finds_duplicates(self):
        """Pages with nearly identical titles are detected as duplicates."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Meeting Notes"),
            _make_page("p2", "Meeting Notes"),
        ]
        mock_client.get_page_blocks.return_value = []

        import notion_manager.plugins.duplicate_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: "")

        try:
            result = self.plugin.execute(mock_client, self.config, threshold=0.8)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert len(result["duplicates"]) == 1
        dup = result["duplicates"][0]
        assert set(dup["pages"]) == {"p1", "p2"}
        assert dup["similarity"] >= 0.8

    def test_threshold_filter(self):
        """A pair with ~0.7 similarity should not appear when threshold=0.8."""
        mock_client = MagicMock()
        # "apple pie" vs "apple tart" → moderate similarity, below 0.8
        mock_client.search.return_value = [
            _make_page("p1", "apple pie recipe"),
            _make_page("p2", "banana bread recipe"),
        ]
        mock_client.get_page_blocks.return_value = []

        import notion_manager.plugins.duplicate_detector as mod
        original = mod.NotionClient.blocks_to_text
        mod.NotionClient.blocks_to_text = staticmethod(lambda blocks: "")

        try:
            result = self.plugin.execute(mock_client, self.config, threshold=0.8)
        finally:
            mod.NotionClient.blocks_to_text = original

        assert result["duplicates"] == []
