from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Type

from notion_manager.plugin_meta import (
    PluginMeta,
    auto_generate_meta,
    build_plugin_name_to_category,
    load_categories,
    validate_categories,
)
from notion_manager.plugins.base import Plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for discovering, registering, and instantiating plugins."""

    def __init__(self) -> None:
        self._registry: dict[str, Type[Any]] = {}
        self._meta: dict[str, PluginMeta] = {}
        self._categories: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, plugin_class: Type[Any]) -> None:
        """Register a plugin class under a given name."""
        self._registry[name] = plugin_class

    def get(self, name: str) -> Type[Any] | None:
        """Return the plugin class for name, or None if not registered."""
        return self._registry.get(name)

    def get_meta(self, name: str) -> PluginMeta | None:
        """Return the PluginMeta for a given plugin name."""
        return self._meta.get(name)

    def list_plugins(self) -> list[str]:
        """Return sorted list of registered plugin names."""
        return sorted(self._registry.keys())

    def list_by_category(self, category: str) -> list[str]:
        """Return plugin names belonging to a specific category."""
        return sorted(
            name
            for name, meta in self._meta.items()
            if meta.category == category
        )

    def get_categories(self) -> dict[str, Any]:
        """Return loaded categories dict."""
        return self._categories

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    def _autodiscover(self) -> None:
        """Import all modules under notion_manager.plugins to trigger registration."""
        import notion_manager.plugins as plugins_pkg

        pkg_path = plugins_pkg.__path__
        pkg_name = plugins_pkg.__name__

        for module_info in pkgutil.iter_modules(pkg_path):
            full_name = f"{pkg_name}.{module_info.name}"
            if full_name.endswith(".base"):
                continue
            try:
                module = importlib.import_module(full_name)
                for attr_name in dir(module):
                    obj = getattr(module, attr_name)
                    if (
                        isinstance(obj, type)
                        and hasattr(obj, "name")
                        and hasattr(obj, "execute")
                        and obj.__name__ != "Plugin"
                    ):
                        plugin_name: str = getattr(obj, "name", attr_name)
                        if plugin_name not in self._registry:
                            self._registry[plugin_name] = obj
            except Exception as exc:
                logger.debug("Failed to import %s: %s", full_name, exc)

        # Load categories and cross-validate
        self._categories = load_categories()
        if self._categories:
            validate_categories(set(self._registry.keys()), self._categories)

        # Auto-generate PluginMeta for all discovered plugins
        name_to_cat = build_plugin_name_to_category(self._categories)
        for name, cls in self._registry.items():
            existing_meta = getattr(cls, "meta", None)
            if isinstance(existing_meta, PluginMeta):
                self._meta[name] = existing_meta
            else:
                self._meta[name] = auto_generate_meta(cls, name, name_to_cat)

    # ------------------------------------------------------------------
    # Loading enabled plugins
    # ------------------------------------------------------------------

    def load_enabled(self, config: dict[str, Any]) -> dict[str, Plugin]:
        """Instantiate and return only the enabled plugins listed in config."""
        self._autodiscover()

        from notion_manager.plugin_state import load_effective_plugins

        enabled: list[str] = load_effective_plugins(config)
        loaded: dict[str, Plugin] = {}
        for name in enabled:
            cls = self._registry.get(name)
            if cls is None:
                logger.warning("Plugin '%s' enabled in config but not discovered", name)
                continue
            try:
                instance: Plugin = cls()
                loaded[name] = instance
            except Exception:
                pass
        return loaded
