from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_CATEGORIES_PATH = Path(__file__).resolve().parent.parent / "config" / "plugin_categories.yaml"


class PluginMeta(BaseModel):
    name: str
    description: str = ""
    category: str = "uncategorized"
    tags: list[str] = []
    required_params: list[str] = []
    optional_params: list[str] = []
    requires_ai: bool = False
    requires_notion: bool = True
    risk_level: Literal["safe", "moderate", "destructive"] = "safe"
    version: str = "1.0.0"


def load_categories(path: str | Path | None = None) -> dict[str, Any]:
    """Load plugin_categories.yaml and return the raw dict."""
    p = Path(path) if path else _CATEGORIES_PATH
    if not p.exists():
        logger.warning("plugin_categories.yaml not found at %s", p)
        return {}
    with p.open() as f:
        data = yaml.safe_load(f)
    return data.get("categories", {}) if isinstance(data, dict) else {}


def build_plugin_name_to_category(categories: dict[str, Any]) -> dict[str, str]:
    """Return {plugin_name: category_key} mapping from categories dict."""
    mapping: dict[str, str] = {}
    for cat_key, cat_data in categories.items():
        for plugin_name in cat_data.get("plugins", []):
            mapping[plugin_name] = cat_key
    return mapping


def validate_categories(
    discovered_names: set[str], categories: dict[str, Any]
) -> None:
    """Warn about mismatches between discovered plugins and category YAML."""
    yaml_names: set[str] = set()
    for cat_data in categories.values():
        yaml_names.update(cat_data.get("plugins", []))

    for name in discovered_names - yaml_names:
        logger.warning(
            "Plugin '%s' discovered but missing from plugin_categories.yaml", name
        )
    for name in yaml_names - discovered_names:
        logger.warning(
            "Plugin '%s' in plugin_categories.yaml but not discovered", name
        )


def auto_generate_meta(
    plugin_cls: type,
    name: str,
    name_to_category: dict[str, str],
) -> PluginMeta:
    """Generate a PluginMeta for a plugin class that doesn't define one."""
    description = getattr(plugin_cls, "description", "")
    category = name_to_category.get(name, "uncategorized")

    requires_ai = False
    try:
        import inspect
        src = inspect.getsource(plugin_cls)
        requires_ai = "AIProvider" in src or "ai_provider" in src
    except (OSError, TypeError):
        pass

    return PluginMeta(
        name=name,
        description=description,
        category=category,
        requires_ai=requires_ai,
    )
