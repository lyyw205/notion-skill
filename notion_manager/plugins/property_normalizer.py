from __future__ import annotations

import difflib
from collections import defaultdict
from typing import Any

from notion_manager.client import NotionClient


class PropertyNormalizerPlugin:
    name = "property_normalizer"
    description = "Select/Multi-Select 속성의 오타 및 유사 태그 탐지/정규화"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        threshold: float = kwargs.get("threshold", 0.8)
        dry_run: bool = kwargs.get("dry_run", True)

        try:
            db = client.get_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        properties = db.get("properties", {})
        target_props: list[dict[str, Any]] = []

        for prop_name, prop_def in properties.items():
            ptype = prop_def.get("type", "")
            if ptype == "select":
                options = prop_def.get("select", {}).get("options", [])
                names = [opt.get("name", "") for opt in options if opt.get("name")]
                target_props.append({"name": prop_name, "type": "select", "options": names})
            elif ptype == "multi_select":
                options = prop_def.get("multi_select", {}).get("options", [])
                names = [opt.get("name", "") for opt in options if opt.get("name")]
                target_props.append({"name": prop_name, "type": "multi_select", "options": names})

        suggestions: list[dict[str, Any]] = []
        for prop in target_props:
            names = prop["options"]
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    ratio = difflib.SequenceMatcher(
                        None, names[i].lower(), names[j].lower()
                    ).ratio()
                    if ratio >= threshold and names[i] != names[j]:
                        suggestions.append({
                            "property": prop["name"],
                            "type": prop["type"],
                            "option_a": names[i],
                            "option_b": names[j],
                            "similarity": round(ratio, 4),
                            "suggestion": f"'{names[j]}' → '{names[i]}'",
                        })

        applied: list[dict[str, Any]] = []
        if not dry_run and suggestions:
            try:
                pages = client.query_database(database_id)
            except Exception as exc:
                return {"error": str(exc), "suggestions": suggestions}

            rename_map: dict[str, dict[str, str]] = defaultdict(dict)
            for s in suggestions:
                rename_map[s["property"]][s["option_b"]] = s["option_a"]

            for page in pages:
                page_id = page.get("id", "")
                props = page.get("properties", {})
                updates: dict[str, Any] = {}

                for prop_name, mapping in rename_map.items():
                    prop = props.get(prop_name, {})
                    ptype = prop.get("type", "")

                    if ptype == "select":
                        current = (prop.get("select") or {}).get("name", "")
                        if current in mapping:
                            updates[prop_name] = {"select": {"name": mapping[current]}}

                    elif ptype == "multi_select":
                        current_opts = prop.get("multi_select", [])
                        new_opts = []
                        changed = False
                        for opt in current_opts:
                            name = opt.get("name", "")
                            if name in mapping:
                                new_opts.append({"name": mapping[name]})
                                changed = True
                            else:
                                new_opts.append({"name": name})
                        if changed:
                            updates[prop_name] = {"multi_select": new_opts}

                if updates:
                    try:
                        client.update_page(page_id, updates)
                        applied.append({"page_id": page_id, "updates": updates})
                    except Exception:
                        continue

        return {
            "database_id": database_id,
            "dry_run": dry_run,
            "suggestions": suggestions,
            "applied": applied,
            "total_suggestions": len(suggestions),
            "total_applied": len(applied),
        }


