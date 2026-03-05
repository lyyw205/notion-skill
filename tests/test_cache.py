from __future__ import annotations

import tempfile
import time
import os

import pytest

from notion_manager.cache import Cache


def make_cache() -> tuple[Cache, str]:
    """Return a Cache instance backed by a temp file and the file path."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    cache = Cache(db_path=tf.name)
    return cache, tf.name


class TestCache:
    def setup_method(self):
        self.cache, self.db_path = make_cache()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def test_set_and_get(self):
        self.cache.set("key1", {"data": "value"})
        result = self.cache.get("key1")
        assert result == {"data": "value"}

    def test_get_expired(self):
        # Store with extremely short TTL (0.00001 hours ≈ 0.036 seconds)
        self.cache.set("expiring", {"x": 1}, ttl_hours=0.00001)
        time.sleep(0.1)
        result = self.cache.get("expiring")
        assert result is None

    def test_get_missing_returns_none(self):
        result = self.cache.get("nonexistent")
        assert result is None

    def test_invalidate(self):
        self.cache.set("to_remove", {"val": 42})
        assert self.cache.get("to_remove") == {"val": 42}
        self.cache.invalidate("to_remove")
        assert self.cache.get("to_remove") is None

    def test_invalidate_nonexistent_is_safe(self):
        # Should not raise
        self.cache.invalidate("ghost_key")

    def test_clear_expired(self):
        self.cache.set("expired1", {"a": 1}, ttl_hours=0.00001)
        self.cache.set("expired2", {"b": 2}, ttl_hours=0.00001)
        self.cache.set("alive", {"c": 3}, ttl_hours=24.0)
        time.sleep(0.1)
        removed = self.cache.clear_expired()
        assert removed == 2
        assert self.cache.get("alive") == {"c": 3}
        assert self.cache.get("expired1") is None
        assert self.cache.get("expired2") is None

    def test_overwrite(self):
        self.cache.set("dup", {"v": 1})
        self.cache.set("dup", {"v": 2})
        result = self.cache.get("dup")
        assert result == {"v": 2}

    def test_set_various_types(self):
        self.cache.set("list_val", [1, 2, 3])
        assert self.cache.get("list_val") == [1, 2, 3]

        self.cache.set("str_val", "hello")
        assert self.cache.get("str_val") == "hello"

        self.cache.set("int_val", 99)
        assert self.cache.get("int_val") == 99
