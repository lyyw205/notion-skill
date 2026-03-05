from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


def _build_property_value(name: str, value: Any) -> dict[str, Any]:
    """Build a Notion property value dict from a Python value."""
    if isinstance(value, bool):
        return {"checkbox": value}
    elif isinstance(value, (int, float)):
        return {"number": value}
    elif isinstance(value, list):
        return {"multi_select": [{"name": str(v)} for v in value]}
    else:
        return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}


class BulkUpdaterPlugin:
    name = "bulk_updater"
    description = "DB 속성 일괄 업데이트"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        filter_conditions: dict[str, Any] | None = kwargs.get("filter_conditions")
        updates: dict[str, Any] = kwargs.get("updates", {})

        if not database_id:
            return {"error": "database_id is required"}
        if not updates:
            return {"error": "updates dict is required and must not be empty"}

        try:
            pages = client.query_database(database_id, filter=filter_conditions)
        except Exception as exc:
            return {"error": str(exc), "database_id": database_id}

        # Build Notion properties payload
        properties: dict[str, Any] = {
            name: _build_property_value(name, value)
            for name, value in updates.items()
        }

        updated_count = 0
        errors: list[dict[str, Any]] = []

        for page in pages:
            pid = page.get("id", "")
            try:
                client.update_page(pid, properties)
                updated_count += 1
            except Exception as exc:
                errors.append({"page_id": pid, "error": str(exc)})

        return {
            "updated_count": updated_count,
            "database_id": database_id,
            "updates_applied": updates,
            "errors": errors,
        }


PLUGIN_CLASS = BulkUpdaterPlugin
