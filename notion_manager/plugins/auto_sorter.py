from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


class AutoSorterPlugin:
    name = "auto_sorter"
    description = "날짜 기반 DB 자동 정렬"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        sort_property: str = kwargs.get("sort_property", "Date")
        direction: str = kwargs.get("direction", "descending")

        if not database_id:
            return {"error": "database_id is required"}

        sorts = [{"property": sort_property, "direction": direction}]

        try:
            results = client.query_database(database_id, sorts=sorts)
        except Exception as exc:
            return {"error": str(exc), "database_id": database_id}

        return {
            "database_id": database_id,
            "sorted_count": len(results),
            "sort_property": sort_property,
            "direction": direction,
        }


