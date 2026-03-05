from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.hierarchy_optimizer import HierarchyOptimizerPlugin


def _make_page(pid: str, title: str, parent: dict) -> dict:
    return {
        "id": pid,
        "last_edited_time": "2025-01-01T00:00:00.000Z",
        "parent": parent,
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


class TestHierarchyOptimizerPlugin:
    def setup_method(self):
        self.plugin = HierarchyOptimizerPlugin()
        # No AI key so suggestions branch is skipped
        self.config = {}

    def test_flat_structure(self):
        """All pages at root level: stats are calculated, no too_deep pages."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("p1", "Page One", {"type": "workspace", "workspace": True}),
            _make_page("p2", "Page Two", {"type": "workspace", "workspace": True}),
            _make_page("p3", "Page Three", {"type": "workspace", "workspace": True}),
        ]

        result = self.plugin.execute(mock_client, self.config, max_depth=5)

        assert "stats" in result
        stats = result["stats"]
        assert stats["total_pages"] == 3
        assert stats["max_depth"] == 0
        assert stats["too_deep"] == []

    def test_deep_pages_detected(self):
        """Pages nested deeper than max_depth are flagged in too_deep."""
        mock_client = MagicMock()
        # Build a chain: workspace -> p1 -> p2 -> p3 (depth 2)
        mock_client.search.return_value = [
            _make_page("p1", "Root", {"type": "workspace", "workspace": True}),
            _make_page("p2", "Child", {"type": "page_id", "page_id": "p1"}),
            _make_page("p3", "Grandchild", {"type": "page_id", "page_id": "p2"}),
        ]

        # max_depth=1 → p3 at depth 2 should be flagged
        result = self.plugin.execute(mock_client, self.config, max_depth=1)

        stats = result["stats"]
        deep_ids = [d["id"] for d in stats["too_deep"]]
        assert "p3" in deep_ids
