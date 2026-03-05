from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.meeting_template import MeetingTemplatePlugin


class TestMeetingTemplatePlugin:
    def setup_method(self):
        self.plugin = MeetingTemplatePlugin()
        self.config = {}

    def test_create_meeting(self):
        """Mock create_page; verify created_page_id and title."""
        mock_client = MagicMock()
        mock_client.create_page.return_value = {"id": "meeting-page-id"}

        result = self.plugin.execute(
            mock_client,
            self.config,
            parent_page_id="parent-abc",
            title="Sprint Planning",
            attendees=["Alice", "Bob"],
            agenda=["Review backlog", "Assign tasks"],
        )

        assert result.get("created_page_id") == "meeting-page-id"
        assert result.get("title") == "Sprint Planning"
        mock_client.create_page.assert_called_once()

    def test_missing_parent(self):
        """No parent_page_id should return error."""
        mock_client = MagicMock()

        result = self.plugin.execute(mock_client, self.config, title="Some Meeting")

        assert "error" in result
