from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich)
    return page.get("id", "")


class DBStatsPlugin:
    name = "db_stats"
    description = "DB 통계 요약"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        try:
            items = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        properties_summary: dict[str, Any] = {}
        status_distribution: dict[str, int] = {}

        for item in items:
            props = item.get("properties", {})
            for prop_name, prop_val in props.items():
                ptype = prop_val.get("type", "")
                if prop_name not in properties_summary:
                    properties_summary[prop_name] = {"type": ptype, "stats": {}}

                stats = properties_summary[prop_name]["stats"]

                if ptype == "select":
                    sel = prop_val.get("select")
                    val = sel.get("name", "None") if sel else "None"
                    stats[val] = stats.get(val, 0) + 1
                    if prop_name.lower() in ("status", "상태"):
                        status_distribution[val] = status_distribution.get(val, 0) + 1

                elif ptype == "multi_select":
                    for sel in prop_val.get("multi_select", []):
                        val = sel.get("name", "")
                        stats[val] = stats.get(val, 0) + 1

                elif ptype == "checkbox":
                    val = prop_val.get("checkbox", False)
                    key = "true" if val else "false"
                    stats[key] = stats.get(key, 0) + 1

                elif ptype == "number":
                    num = prop_val.get("number")
                    if num is not None:
                        if "values" not in stats:
                            stats["values"] = []
                        stats["values"].append(num)

        # Finalize number stats
        for prop_name, summary in properties_summary.items():
            if summary["type"] == "number" and "values" in summary["stats"]:
                vals = summary["stats"].pop("values")
                if vals:
                    summary["stats"]["min"] = min(vals)
                    summary["stats"]["max"] = max(vals)
                    summary["stats"]["avg"] = sum(vals) / len(vals)
                    summary["stats"]["count"] = len(vals)

        return {
            "database_id": database_id,
            "total_items": len(items),
            "properties_summary": properties_summary,
            "status_distribution": status_distribution,
        }


