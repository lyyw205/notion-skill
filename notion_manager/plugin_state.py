from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_STATE_PATH = "data/plugin_state.json"


def _read_state(state_path: str = _DEFAULT_STATE_PATH) -> dict[str, Any]:
    p = Path(state_path)
    if not p.exists():
        return {"overrides": {}, "updated_at": None}
    with p.open() as f:
        return json.load(f)


def _write_state(state: dict[str, Any], state_path: str = _DEFAULT_STATE_PATH) -> None:
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with p.open("w") as f:
        json.dump(state, f, indent=2)


def load_effective_plugins(
    config: dict[str, Any], state_path: str = _DEFAULT_STATE_PATH
) -> list[str]:
    """Merge YAML defaults with JSON overrides to produce the effective enabled list."""
    yaml_enabled: list[str] = config.get("plugins", {}).get("enabled", [])
    state = _read_state(state_path)
    overrides: dict[str, dict[str, Any]] = state.get("overrides", {})

    result: list[str] = []
    for name in yaml_enabled:
        override = overrides.get(name, {})
        if override.get("enabled", True):
            result.append(name)

    # Add plugins not in YAML but explicitly enabled in overrides
    for name, override in overrides.items():
        if name not in yaml_enabled and override.get("enabled", False):
            result.append(name)

    return result


def toggle_plugin(
    name: str, enabled: bool, state_path: str = _DEFAULT_STATE_PATH
) -> None:
    """Set a plugin's enabled state in the JSON override file."""
    state = _read_state(state_path)
    overrides = state.setdefault("overrides", {})
    overrides[name] = {"enabled": enabled}
    _write_state(state, state_path)


def get_plugin_state(state_path: str = _DEFAULT_STATE_PATH) -> dict[str, Any]:
    """Return current override state."""
    return _read_state(state_path)


def reset_plugin_state(name: str, state_path: str = _DEFAULT_STATE_PATH) -> None:
    """Remove a plugin's override, restoring YAML default."""
    state = _read_state(state_path)
    overrides = state.get("overrides", {})
    overrides.pop(name, None)
    _write_state(state, state_path)
