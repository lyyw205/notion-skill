from __future__ import annotations

from unittest.mock import MagicMock

from notion_manager.plugins.property_normalizer import PropertyNormalizerPlugin

CONFIG: dict = {}


class TestPropertyNormalizerPlugin:
    def setup_method(self):
        self.plugin = PropertyNormalizerPlugin()

    def test_missing_database_id(self):
        result = self.plugin.execute(MagicMock(), CONFIG)
        assert "error" in result

    def test_detect_similar_select_options(self):
        mock_client = MagicMock()
        mock_client.get_database.return_value = {
            "properties": {
                "Category": {
                    "type": "select",
                    "select": {
                        "options": [
                            {"name": "Development"},
                            {"name": "Developement"},
                            {"name": "Design"},
                        ]
                    },
                }
            }
        }

        result = self.plugin.execute(mock_client, CONFIG, database_id="db-1", threshold=0.8)

        assert result["total_suggestions"] == 1
        assert result["suggestions"][0]["option_a"] == "Development"
        assert result["suggestions"][0]["option_b"] == "Developement"
        assert result["dry_run"] is True
        assert result["total_applied"] == 0

    def test_no_similar_options(self):
        mock_client = MagicMock()
        mock_client.get_database.return_value = {
            "properties": {
                "Type": {
                    "type": "select",
                    "select": {
                        "options": [
                            {"name": "Bug"},
                            {"name": "Feature"},
                            {"name": "Enhancement"},
                        ]
                    },
                }
            }
        }

        result = self.plugin.execute(mock_client, CONFIG, database_id="db-1")
        assert result["total_suggestions"] == 0

    def test_dry_run_false_applies_changes(self):
        mock_client = MagicMock()
        mock_client.get_database.return_value = {
            "properties": {
                "Tag": {
                    "type": "multi_select",
                    "multi_select": {
                        "options": [
                            {"name": "python"},
                            {"name": "pythno"},
                        ]
                    },
                }
            }
        }
        mock_client.query_database.return_value = [
            {
                "id": "p1",
                "properties": {
                    "Tag": {
                        "type": "multi_select",
                        "multi_select": [{"name": "pythno"}],
                    }
                },
            }
        ]
        mock_client.update_page.return_value = {}

        result = self.plugin.execute(
            mock_client, CONFIG, database_id="db-1", dry_run=False, threshold=0.8
        )

        assert result["total_applied"] == 1
        mock_client.update_page.assert_called_once()
