from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.orphan_detector import OrphanDetectorPlugin


def _make_workspace_page(pid: str, title: str) -> dict:
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


def _make_child_page(pid: str, title: str, parent_id: str) -> dict:
    return {
        "id": pid,
        "last_edited_time": "2025-01-01T00:00:00.000Z",
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestOrphanDetectorPlugin:
    def setup_method(self):
        self.plugin = OrphanDetectorPlugin()
        self.config = {}

    def test_finds_orphans(self):
        """Workspace-root pages not referenced by any other page are orphans."""
        mock_client = MagicMock()
        # p1 and p2 are both at workspace root; neither references the other
        mock_client.search.return_value = [
            _make_workspace_page("p1", "Orphan One"),
            _make_workspace_page("p2", "Orphan Two"),
        ]
        # No blocks contain any links
        mock_client.get_page_blocks.return_value = []

        result = self.plugin.execute(mock_client, self.config)

        orphan_ids = {p["id"] for p in result["orphan_pages"]}
        assert "p1" in orphan_ids
        assert "p2" in orphan_ids
        assert result["orphan_count"] == 2

    def test_no_orphans(self):
        """A workspace-root page referenced as a child is not an orphan."""
        mock_client = MagicMock()
        # p1 is at workspace root; p2 is a child of p1
        mock_client.search.return_value = [
            _make_workspace_page("p1", "Root Page"),
            _make_child_page("p2", "Child Page", parent_id="p1"),
        ]
        # No inline block mentions needed; parent relationship covers p2
        mock_client.get_page_blocks.return_value = []

        result = self.plugin.execute(mock_client, self.config)

        # p1 is at workspace root and not referenced → orphan
        # p2 is a child page → referenced via parent relationship → not orphan
        orphan_ids = {p["id"] for p in result["orphan_pages"]}
        assert "p2" not in orphan_ids
        assert result["total_pages"] == 2
