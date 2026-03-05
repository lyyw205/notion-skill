from __future__ import annotations

import time
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError


class NotionClient:
    """Notion API client with rate limiting and exponential-backoff retries."""

    def __init__(
        self,
        token: str,
        requests_per_second: int = 3,
        max_retries: int = 5,
        backoff_factor: float = 2.0,
    ) -> None:
        self._client = Client(auth=token)
        self._min_interval = 1.0 / requests_per_second
        self._last_call: float = 0.0
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _call(self, fn, *args, **kwargs) -> Any:
        """Execute a Notion SDK call with rate-limiting and retry logic."""
        delay = 1.0
        for attempt in range(self._max_retries):
            self._rate_wait()
            try:
                return fn(*args, **kwargs)
            except APIResponseError as exc:
                if attempt == self._max_retries - 1:
                    raise
                # Retry on rate-limit (429) or server errors (5xx)
                if exc.status in (429,) or (exc.status is not None and exc.status >= 500):
                    time.sleep(delay)
                    delay *= self._backoff_factor
                else:
                    raise

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._call(self._client.pages.retrieve, page_id=page_id)

    def get_page_blocks(self, page_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = self._call(self._client.blocks.children.list, **kwargs)
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return results

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._call(
            self._client.pages.update, page_id=page_id, properties=properties
        )

    def create_page(
        self,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            kwargs["children"] = children
        return self._call(self._client.pages.create, **kwargs)

    def append_blocks(self, page_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        return self._call(
            self._client.blocks.children.append, block_id=page_id, children=blocks
        )

    def search(
        self, query: str, filter_type: str | None = None
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"query": query}
        if filter_type:
            kwargs["filter"] = {"value": filter_type, "property": "object"}
        response = self._call(self._client.search, **kwargs)
        return response.get("results", [])

    def get_database(self, db_id: str) -> dict[str, Any]:
        return self._call(self._client.databases.retrieve, database_id=db_id)

    def query_database(
        self,
        db_id: str,
        filter: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"database_id": db_id, "page_size": 100}
            if filter:
                kwargs["filter"] = filter
            if sorts:
                kwargs["sorts"] = sorts
            if cursor:
                kwargs["start_cursor"] = cursor
            response = self._call(self._client.databases.query, **kwargs)
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        return results

    # ------------------------------------------------------------------
    # Block text extraction
    # ------------------------------------------------------------------

    @staticmethod
    def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
        """Recursively extract plain text from a list of Notion blocks."""
        lines: list[str] = []

        def _rich_text_to_str(rich_texts: list[dict[str, Any]]) -> str:
            return "".join(rt.get("plain_text", "") for rt in rich_texts)

        def _extract(block: dict[str, Any]) -> None:
            btype = block.get("type", "")
            content = block.get(btype, {})
            rich_texts: list[dict[str, Any]] = content.get("rich_text", [])
            if rich_texts:
                lines.append(_rich_text_to_str(rich_texts))
            # Recurse into children if present
            children: list[dict[str, Any]] = block.get("children", [])
            for child in children:
                _extract(child)

        for block in blocks:
            _extract(block)

        return "\n".join(lines)
