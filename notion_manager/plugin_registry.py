from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Type

from notion_manager.plugins.base import Plugin


class PluginRegistry:
    """Registry for discovering, registering, and instantiating plugins."""

    def __init__(self) -> None:
        self._registry: dict[str, Type[Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, plugin_class: Type[Any]) -> None:
        """Register a plugin class under a given name."""
        self._registry[name] = plugin_class

    def get(self, name: str) -> Type[Any] | None:
        """Return the plugin class for name, or None if not registered."""
        return self._registry.get(name)

    def list_plugins(self) -> list[str]:
        """Return sorted list of registered plugin names."""
        return sorted(self._registry.keys())

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
                # Register any class that looks like a Plugin (has name + execute)
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
            except Exception:
                pass  # Skip modules that fail to import

    # ------------------------------------------------------------------
    # Loading enabled plugins
    # ------------------------------------------------------------------

    def load_enabled(self, config: dict[str, Any]) -> dict[str, Plugin]:
        """Instantiate and return only the enabled plugins listed in config."""
        self._autodiscover()
        enabled: list[str] = config.get("enabled_plugins", [])
        loaded: dict[str, Plugin] = {}
        for name in enabled:
            cls = self._registry.get(name)
            if cls is None:
                continue
            try:
                instance: Plugin = cls()
                loaded[name] = instance
            except Exception:
                pass  # Skip plugins that fail to instantiate
        return loaded
