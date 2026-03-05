from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.release_notes import ReleaseNotesPlugin


def _make_page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
        },
    }


class TestReleaseNotesPlugin:
    def setup_method(self):
        self.plugin = ReleaseNotesPlugin()
        self.config = {"ai": {"api_key": "fake-key", "model": "claude-opus-4-5"}}

    def test_generate_notes(self):
        """Mock DB query and AI; verify release_notes string is returned."""
        mock_client = MagicMock()
        mock_client.query_database.return_value = [
            _make_page("c1", "Fix login bug"),
            _make_page("c2", "Add dark mode"),
        ]
        mock_client.get_page_blocks.return_value = []

        with patch("notion_manager.plugins.release_notes.AIProvider") as MockAI:
            mock_ai = MagicMock()
            mock_ai.generate_release_notes.return_value = "## v1.2.0\n- Fix login bug\n- Add dark mode"
            MockAI.return_value = mock_ai

            with patch("notion_manager.plugins.release_notes.NotionClient") as MockNC:
                MockNC.blocks_to_text.return_value = ""

                result = self.plugin.execute(
                    mock_client, self.config, database_id="db-changes", version="1.2.0"
                )

        assert "release_notes" in result
        assert result["release_notes"] == "## v1.2.0\n- Fix login bug\n- Add dark mode"
        assert result.get("version") == "1.2.0"

    def test_missing_database_id(self):
        """No database_id should return error."""
        mock_client = MagicMock()

        with patch("notion_manager.plugins.release_notes.AIProvider"):
            result = self.plugin.execute(mock_client, self.config)

        assert "error" in result
