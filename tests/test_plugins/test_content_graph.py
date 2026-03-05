from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.content_graph import ContentGraphPlugin


def _make_page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


def _make_mention_block(target_page_id: str) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "mention",
                    "mention": {
                        "type": "page",
                        "page": {"id": target_page_id},
                    },
                }
            ]
        },
    }


class TestContentGraphPlugin:
    def setup_method(self):
        self.plugin = ContentGraphPlugin()
        self.config = {}

    def test_builds_graph(self):
        """Mock pages with mention blocks linking to each other, verify nodes/edges."""
        mock_client = MagicMock()
        pages = [
            _make_page("p1", "Page One"),
            _make_page("p2", "Page Two"),
        ]
        mock_client.search.return_value = pages

        # p1 mentions p2
        def get_blocks(page_id: str):
            if page_id == "p1":
                return [_make_mention_block("p2")]
            return []

        mock_client.get_page_blocks.side_effect = get_blocks

        result = self.plugin.execute(mock_client, self.config)

        assert result["total_nodes"] == 2
        assert result["total_edges"] == 1
        node_ids = [n["id"] for n in result["nodes"]]
        assert "p1" in node_ids
        assert "p2" in node_ids
        edge = result["edges"][0]
        assert edge["source"] == "p1"
        assert edge["target"] == "p2"
        assert edge["type"] == "mention"

    def test_isolated_pages(self):
        """Pages with no mentions appear in isolated list."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            _make_page("a1", "Alpha"),
            _make_page("a2", "Beta"),
        ]
        # No blocks → no mentions
        mock_client.get_page_blocks.return_value = []

        result = self.plugin.execute(mock_client, self.config)

        assert result["total_edges"] == 0
        isolated_ids = [p["id"] for p in result["isolated"]]
        assert "a1" in isolated_ids
        assert "a2" in isolated_ids
