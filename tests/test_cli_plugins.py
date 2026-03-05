from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from notion_manager.cli import cli


def _invoke(*args, config_path="config/default.yaml"):
    runner = CliRunner()
    return runner.invoke(cli, ["--config", config_path] + list(args))


class TestCLIPluginsList:
    def test_plugins_list_grouped(self):
        result = _invoke("plugins", "list")
        assert result.exit_code == 0
        assert "[Content AI]" in result.output
        assert "[Automation]" in result.output
        assert "[ON]" in result.output or "[OFF]" in result.output

    def test_plugins_list_category_filter(self):
        result = _invoke("plugins", "list", "--category", "content-ai")
        assert result.exit_code == 0
        assert "summarizer" in result.output
        assert "backup" not in result.output

    def test_plugins_list_json(self):
        result = _invoke("plugins", "list", "--format", "json")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 46
        assert all("name" in d and "enabled" in d for d in data)


class TestCLIPluginsEnableDisable:
    def test_enable_disable_roundtrip(self):
        """Test toggle via plugin_state functions directly (CLI uses local imports)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "plugin_state.json")
            from notion_manager.plugin_state import toggle_plugin, load_effective_plugins
            config = {"plugins": {"enabled": ["summarizer", "tagger"]}}

            toggle_plugin("summarizer", False, state_path)
            result = load_effective_plugins(config, state_path)
            assert "summarizer" not in result

            toggle_plugin("summarizer", True, state_path)
            result = load_effective_plugins(config, state_path)
            assert "summarizer" in result


class TestCLIPluginsInfo:
    def test_info_shows_meta(self):
        result = _invoke("plugins", "info", "summarizer")
        assert result.exit_code == 0
        assert "summarizer" in result.output
        assert "Category" in result.output


class TestCLIPluginsHistory:
    def test_history_empty(self):
        with patch("notion_manager.execution_tracker.ExecutionTracker") as MockTracker:
            mock_instance = MagicMock()
            mock_instance.get_history.return_value = []
            MockTracker.return_value = mock_instance
            # The CLI does a local import, so we need to patch at the source
            with patch("notion_manager.execution_tracker.ExecutionTracker", return_value=mock_instance):
                result = _invoke("plugins", "history")
        # history command creates its own tracker, just test the CLI invocation works
        assert result.exit_code == 0
