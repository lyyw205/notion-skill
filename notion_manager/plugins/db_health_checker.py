from __future__ import annotations

import difflib
from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


def _is_empty_value(prop_value: dict[str, Any]) -> bool:
    ptype = prop_value.get("type", "")
    val = prop_value.get(ptype)
    if val is None:
        return True
    if isinstance(val, list) and len(val) == 0:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, dict) and not val:
        return True
    return False


def _get_select_values(items: list[dict[str, Any]], prop_name: str) -> list[str]:
    values: list[str] = []
    for item in items:
        props = item.get("properties", {})
        prop = props.get(prop_name, {})
        ptype = prop.get("type", "")
        if ptype == "select":
            sel = prop.get("select")
            if sel and sel.get("name"):
                values.append(sel["name"])
        elif ptype == "multi_select":
            for s in prop.get("multi_select", []):
                if s.get("name"):
                    values.append(s["name"])
    return values


class DBHealthCheckerPlugin:
    name = "db_health_checker"
    description = "데이터베이스 헬스체크"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        try:
            db_schema = client.get_database(database_id)
            items = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc), "database_id": database_id}

        schema_props = db_schema.get("properties", {})
        total_items = len(items)
        num_properties = len(schema_props)

        empty_properties: dict[str, int] = {}
        unused_properties: list[str] = []
        inconsistent_values: dict[str, list[list[str]]] = {}

        for prop_name in schema_props:
            empty_count = 0
            for item in items:
                prop_val = item.get("properties", {}).get(prop_name, {})
                if _is_empty_value(prop_val):
                    empty_count += 1
            if empty_count > 0:
                empty_properties[prop_name] = empty_count
            if total_items > 0 and empty_count == total_items:
                unused_properties.append(prop_name)

            # Check for similar select/multi_select values
            prop_schema = schema_props[prop_name]
            ptype = prop_schema.get("type", "")
            if ptype in ("select", "multi_select"):
                values = _get_select_values(items, prop_name)
                unique_values = list(set(values))
                similar_pairs: list[list[str]] = []
                for i, v1 in enumerate(unique_values):
                    for v2 in unique_values[i + 1:]:
                        ratio = difflib.SequenceMatcher(None, v1.lower(), v2.lower()).ratio()
                        if ratio > 0.8:
                            similar_pairs.append([v1, v2])
                if similar_pairs:
                    inconsistent_values[prop_name] = similar_pairs

        total_issues = sum(empty_properties.values()) + len(unused_properties) + sum(
            len(pairs) for pairs in inconsistent_values.values()
        )
        denominator = total_items * num_properties if total_items > 0 and num_properties > 0 else 1
        health_score = max(0.0, 1.0 - (total_issues / denominator))

        return {
            "database_id": database_id,
            "total_items": total_items,
            "issues": {
                "empty_properties": empty_properties,
                "unused_properties": unused_properties,
                "inconsistent_values": inconsistent_values,
            },
            "health_score": health_score,
        }


PLUGIN_CLASS = DBHealthCheckerPlugin
