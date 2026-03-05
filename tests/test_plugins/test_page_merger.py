from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.page_merger import PageMergerPlugin

CONFIG = {"ai": {"api_key": "fake-key", "model": "claude-sonnet-4-20250514"}}


def _make_page(pid: str, title: str) -> dict:
    return {
        "id": pid,
        "properties": {"Name": {"type": "title", "title": [{"plain_text": title}]}},
    }


class TestPageMergerPlugin:
    def setup_method(self):
        self.plugin = PageMergerPlugin()

    def test_missing_page_ids(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_same_page_ids(self):
        result = self.plugin.execute(
            MagicMock(), CONFIG, source_page_id="p1", target_page_id="p1"
        )
        assert "error" in result

    def test_dry_run_returns_diff(self):
        mock_client = MagicMock()
        mock_client.get_page.side_effect = [
            _make_page("p1", "Page A"),
            _make_page("p2", "Page B"),
        ]
        mock_client.get_page_blocks.side_effect = [
            [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content A"}]}}],
            [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content B"}]}}],
        ]

        with patch("notion_manager.plugins.page_merger.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete.return_value = "Merged content of A and B"
            MockAI.return_value = mock_ai
            result = self.plugin.execute(
                mock_client, CONFIG,
                source_page_id="p1", target_page_id="p2",
            )

        assert result["dry_run"] is True
        assert result["applied"] is False
        assert "merged_content" in result
        assert result["similarity"] >= 0

    def test_apply_merge(self):
        mock_client = MagicMock()
        mock_client.get_page.side_effect = [
            _make_page("p1", "Page A"),
            _make_page("p2", "Page B"),
        ]
        mock_client.get_page_blocks.side_effect = [
            [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content A"}]}}],
            [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content B"}]}}],
        ]
        mock_client.update_page.return_value = {}
        mock_client.append_blocks.return_value = {}

        with patch("notion_manager.plugins.page_merger.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai._complete.return_value = "Merged"
            MockAI.return_value = mock_ai
            result = self.plugin.execute(
                mock_client, CONFIG,
                source_page_id="p1", target_page_id="p2",
                dry_run=False,
            )

        assert result["applied"] is True
        mock_client.update_page.assert_called_once()
        mock_client.append_blocks.assert_called_once()
