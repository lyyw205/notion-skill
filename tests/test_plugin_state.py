from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from notion_manager.plugin_state import (
    get_plugin_state,
    load_effective_plugins,
    reset_plugin_state,
    toggle_plugin,
)


def _make_config(enabled: list[str] | None = None) -> dict:
    return {"plugins": {"enabled": enabled or ["summarizer", "tagger", "backup"]}}


class TestPluginState:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.state_path = str(Path(self._tmpdir) / "plugin_state.json")

    def test_missing_state_file(self):
        config = _make_config()
        result = load_effective_plugins(config, self.state_path)
        assert result == ["summarizer", "tagger", "backup"]

    def test_toggle_persists(self):
        toggle_plugin("summarizer", False, self.state_path)
        state = get_plugin_state(self.state_path)
        assert state["overrides"]["summarizer"]["enabled"] is False

    def test_yaml_override_disable(self):
        config = _make_config(["summarizer", "tagger"])
        toggle_plugin("summarizer", False, self.state_path)
        result = load_effective_plugins(config, self.state_path)
        assert "summarizer" not in result
        assert "tagger" in result

    def test_yaml_override_enable(self):
        config = _make_config(["summarizer"])
        toggle_plugin("new_plugin", True, self.state_path)
        result = load_effective_plugins(config, self.state_path)
        assert "summarizer" in result
        assert "new_plugin" in result

    def test_reset_restores_default(self):
        config = _make_config(["summarizer", "tagger"])
        toggle_plugin("summarizer", False, self.state_path)
        assert "summarizer" not in load_effective_plugins(config, self.state_path)

        reset_plugin_state("summarizer", self.state_path)
        assert "summarizer" in load_effective_plugins(config, self.state_path)

    def test_default_yaml_untouched(self):
        yaml_path = Path("config/default.yaml")
        if not yaml_path.exists():
            return
        hash_before = hashlib.sha256(yaml_path.read_bytes()).hexdigest()

        toggle_plugin("summarizer", False, self.state_path)
        toggle_plugin("tagger", True, self.state_path)
        reset_plugin_state("summarizer", self.state_path)

        hash_after = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
        assert hash_before == hash_after
