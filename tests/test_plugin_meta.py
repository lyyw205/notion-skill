from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import yaml

from notion_manager.plugin_meta import (
    PluginMeta,
    auto_generate_meta,
    build_plugin_name_to_category,
    load_categories,
    validate_categories,
)
from notion_manager.plugin_registry import PluginRegistry


class TestPluginMeta:
    def test_all_plugins_registered(self):
        registry = PluginRegistry()
        registry._autodiscover()
        names = registry.list_plugins()
        assert len(names) == 46, f"Expected 46 plugins, got {len(names)}: {names}"

    def test_plugin_meta_auto_generated(self):
        registry = PluginRegistry()
        registry._autodiscover()
        for name in registry.list_plugins():
            meta = registry.get_meta(name)
            assert meta is not None, f"Plugin '{name}' has no PluginMeta"
            assert isinstance(meta, PluginMeta)
            assert meta.name == name

    def test_category_filter(self):
        registry = PluginRegistry()
        registry._autodiscover()
        content_ai = registry.list_by_category("content-ai")
        assert len(content_ai) == 7, f"Expected 7 content-ai plugins, got {len(content_ai)}: {content_ai}"

    def test_category_yaml_missing_warning(self, caplog):
        """Plugin discovered but missing from YAML should produce WARNING."""
        categories = {
            "test-cat": {"label": "Test", "plugins": ["summarizer"]},
        }
        discovered = {"summarizer", "tagger"}
        with caplog.at_level(logging.WARNING):
            validate_categories(discovered, categories)
        assert any("tagger" in r.message and "missing from" in r.message for r in caplog.records)

    def test_category_yaml_phantom_warning(self, caplog):
        """Plugin in YAML but not discovered should produce WARNING."""
        categories = {
            "test-cat": {"label": "Test", "plugins": ["summarizer", "ghost_plugin"]},
        }
        discovered = {"summarizer"}
        with caplog.at_level(logging.WARNING):
            validate_categories(discovered, categories)
        assert any("ghost_plugin" in r.message and "not discovered" in r.message for r in caplog.records)

    def test_build_name_to_category(self):
        categories = {
            "cat-a": {"label": "A", "plugins": ["p1", "p2"]},
            "cat-b": {"label": "B", "plugins": ["p3"]},
        }
        mapping = build_plugin_name_to_category(categories)
        assert mapping == {"p1": "cat-a", "p2": "cat-a", "p3": "cat-b"}

    def test_load_categories_missing_file(self):
        result = load_categories("/tmp/nonexistent_categories.yaml")
        assert result == {}

    def test_all_categories_correct_count(self):
        registry = PluginRegistry()
        registry._autodiscover()
        expected = {
            "content-ai": 7,
            "search-discovery": 4,
            "workspace-health": 7,
            "automation": 7,
            "analytics": 7,
            "reporting": 6,
            "templates": 6,
            "backup": 2,
        }
        for cat, count in expected.items():
            plugins = registry.list_by_category(cat)
            assert len(plugins) == count, f"{cat}: expected {count}, got {len(plugins)}: {plugins}"
