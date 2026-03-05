from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class RateLimitSettings(BaseSettings):
    requests_per_second: int = 3
    max_retries: int = 5
    backoff_factor: float = 2.0


class AISettings(BaseSettings):
    model: str = "claude-opus-4-5"
    max_tokens: int = 1024


class CacheSettings(BaseSettings):
    db_path: str = ".cache/notion_manager.db"
    ttl: int = 24  # hours


class BackupSettings(BaseSettings):
    output_dir: str = "backups"
    format: str = "json"


class SearchSettings(BaseSettings):
    collection: str = "notion_pages"
    model: str = "text-embedding-3-small"
    top_k: int = 5


class Settings(BaseSettings):
    notion_token: str = Field(default="", alias="NOTION_TOKEN")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    ai: AISettings = Field(default_factory=AISettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    enabled_plugins: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "ignore"}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(config_path: str = "config/default.yaml") -> dict[str, Any]:
    """Load config from YAML file and merge with env var overrides."""
    yaml_data: dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        with path.open() as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                yaml_data = loaded

    env_overrides: dict[str, Any] = {}
    notion_token = os.getenv("NOTION_TOKEN", "")
    if notion_token:
        env_overrides["notion_token"] = notion_token
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_api_key:
        env_overrides["anthropic_api_key"] = anthropic_api_key

    merged = _deep_merge(yaml_data, env_overrides)
    return merged
