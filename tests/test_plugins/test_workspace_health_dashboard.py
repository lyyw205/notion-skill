from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.plugins.workspace_health_dashboard import WorkspaceHealthDashboardPlugin

CONFIG: dict = {}


class TestWorkspaceHealthDashboardPlugin:
    def setup_method(self):
        self.plugin = WorkspaceHealthDashboardPlugin()

    def test_score_duplicates_no_dupes(self):
        score = self.plugin._score_duplicates({"duplicates": [], "total_checked": 100})
        assert score == 100.0

    def test_score_duplicates_some_dupes(self):
        score = self.plugin._score_duplicates({"duplicates": [1, 2], "total_checked": 100})
        assert score == 80.0

    def test_score_empties(self):
        score = self.plugin._score_empties({"empty_pages": [1], "total_checked": 50})
        assert score == 90.0

    def test_grade_assignment(self):
        # Mock PluginRegistry to return mock plugins
        with patch("notion_manager.plugins.workspace_health_dashboard.PluginRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.discover.return_value = None

            # Return None for all plugins to test graceful degradation
            mock_registry.get.return_value = None
            MockReg.return_value = mock_registry

            result = self.plugin.execute(MagicMock(), CONFIG)

        # All plugins not found => errors, score 0
        assert result["overall_score"] == 0.0
        assert result["plugins_evaluated"] == 0
        assert len(result["errors"]) == 6

    def test_with_working_plugin(self):
        mock_duplicate_plugin = MagicMock()
        mock_duplicate_instance = MagicMock()
        mock_duplicate_instance.execute.return_value = {
            "duplicates": [],
            "total_checked": 50,
        }
        mock_duplicate_plugin.return_value = mock_duplicate_instance

        with patch("notion_manager.plugins.workspace_health_dashboard.PluginRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.discover.return_value = None

            def get_plugin(name):
                if name == "duplicate_detector":
                    return mock_duplicate_plugin
                return None

            mock_registry.get.side_effect = get_plugin
            MockReg.return_value = mock_registry

            result = self.plugin.execute(MagicMock(), CONFIG)

        assert result["plugins_evaluated"] == 1
        assert result["scores"]["duplicate_detector"]["score"] == 100.0
        assert result["overall_score"] == 100.0
