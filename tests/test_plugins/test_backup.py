from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from notion_manager.plugins.backup import BackupPlugin


def _make_page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": title}],
            }
        },
    }


def _make_blocks(text: str) -> list[dict]:
    return [
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": text}]},
        }
    ]


class TestBackupPlugin:
    def setup_method(self):
        self.plugin = BackupPlugin()

    def test_backup_markdown(self):
        """Backup with markdown format should create .md files and index.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "backup": {
                    "format": "markdown",
                    "backup_dir": tmpdir,
                }
            }
            mock_client = MagicMock()
            pages = [_make_page("aabbccdd-1234", "My Page")]
            mock_client.get_page.return_value = pages[0]
            mock_client.get_page_blocks.return_value = _make_blocks("Hello from markdown.")

            result = self.plugin.execute(
                mock_client,
                config,
                page_ids=["aabbccdd-1234"],
            )

            assert result["format"] == "markdown"
            assert result["page_count"] == 1
            backup_dir = Path(result["backup_dir"])
            assert backup_dir.exists()

            # index.json must exist
            index_path = backup_dir / "index.json"
            assert index_path.exists()
            index_data = json.loads(index_path.read_text())
            assert index_data["format"] == "markdown"
            assert index_data["page_count"] == 1

            # At least one .md file
            md_files = list(backup_dir.glob("*.md"))
            assert len(md_files) == 1
            content = md_files[0].read_text()
            assert "My Page" in content

    def test_backup_json(self):
        """Backup with json format should create .json files (besides index.json)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "backup": {
                    "format": "json",
                    "backup_dir": tmpdir,
                }
            }
            mock_client = MagicMock()
            pages = [_make_page("11223344-abcd", "Another Page")]
            mock_client.get_page.return_value = pages[0]
            mock_client.get_page_blocks.return_value = _make_blocks("JSON content here.")

            result = self.plugin.execute(
                mock_client,
                config,
                page_ids=["11223344-abcd"],
            )

            assert result["format"] == "json"
            assert result["page_count"] == 1
            backup_dir = Path(result["backup_dir"])

            # Expect page json file + index.json
            json_files = list(backup_dir.glob("*.json"))
            # One page file + index.json = 2
            assert len(json_files) == 2

            # Page json must contain "page" and "blocks" keys
            page_jsons = [f for f in json_files if f.name != "index.json"]
            assert len(page_jsons) == 1
            data = json.loads(page_jsons[0].read_text())
            assert "page" in data
            assert "blocks" in data

    def test_backup_multiple_pages(self):
        """Multiple page_ids should produce multiple output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"backup": {"format": "json", "backup_dir": tmpdir}}
            mock_client = MagicMock()

            page1 = _make_page("aaaaaaaa-0001", "Page One")
            page2 = _make_page("bbbbbbbb-0002", "Page Two")

            def get_page_side_effect(pid):
                return page1 if "aaaa" in pid else page2

            mock_client.get_page.side_effect = get_page_side_effect
            mock_client.get_page_blocks.return_value = _make_blocks("content")

            result = self.plugin.execute(
                mock_client,
                config,
                page_ids=["aaaaaaaa-0001", "bbbbbbbb-0002"],
            )

            assert result["page_count"] == 2
            backup_dir = Path(result["backup_dir"])
            page_files = [f for f in backup_dir.glob("*.json") if f.name != "index.json"]
            assert len(page_files) == 2

    def test_backup_no_page_ids_uses_search(self):
        """When page_ids is not given, client.search should be called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"backup": {"format": "json", "backup_dir": tmpdir}}
            mock_client = MagicMock()
            mock_client.search.return_value = [_make_page("cccccccc-0003", "Searched Page")]
            mock_client.get_page_blocks.return_value = []

            result = self.plugin.execute(mock_client, config)

        mock_client.search.assert_called_once_with("", filter_type="page")
        assert result["page_count"] == 1
