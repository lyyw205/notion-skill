from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return title_list[0].get("plain_text", "")
    return page.get("id", "")


def _get_number(page: dict[str, Any], prop_name: str) -> float | None:
    props = page.get("properties", {})
    prop = props.get(prop_name, {})
    if prop.get("type") == "number":
        val = prop.get("number")
        if val is not None:
            return float(val)
    return None


class GoalTrackerPlugin:
    name = "goal_tracker"
    description = "목표 달성도 추적 (OKR)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict | list:
        database_id: str | None = kwargs.get("database_id")
        if not database_id:
            return {"error": "database_id required"}

        progress_property: str = kwargs.get("progress_property", "Progress")
        target_property: str = kwargs.get("target_property", "Target")

        try:
            items = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc), "database_id": database_id}

        goals: list[dict] = []
        total_rate = 0.0
        completed = 0
        in_progress = 0

        for item in items:
            pid = item.get("id", "")
            title = _get_title(item)
            progress = _get_number(item, progress_property)
            target = _get_number(item, target_property)

            if progress is not None and target is not None and target > 0:
                rate = progress / target
            elif progress is not None and target is None:
                rate = progress  # treat as direct ratio
            else:
                rate = 0.0

            if rate >= 1.0:
                completed += 1
                status = "completed"
            else:
                in_progress += 1
                status = "in_progress"

            total_rate += rate
            goals.append({
                "page_id": pid,
                "title": title,
                "progress": progress,
                "target": target,
                "rate": rate,
                "status": status,
            })

        total_goals = len(items)
        achievement_rate = total_rate / total_goals if total_goals > 0 else 0.0

        ai_insights: str | None = None
        ai_config = config.get("ai", {})
        api_key = ai_config.get("api_key", "")
        if api_key:
            try:
                ai = AIProvider(
                    api_key=api_key,
                    model=ai_config.get("model", "claude-opus-4-5"),
                    max_tokens=ai_config.get("max_tokens", 1024),
                )
                goals_summary = "\n".join(
                    f"- {g['title']}: {g['progress']} / {g['target']} ({g['rate']*100:.1f}%)"
                    for g in goals
                )
                ai_insights = ai.analyze_goals(goals_summary)
            except Exception:
                ai_insights = None

        return {
            "database_id": database_id,
            "total_goals": total_goals,
            "completed": completed,
            "in_progress": in_progress,
            "achievement_rate": achievement_rate,
            "goals": goals,
            "ai_insights": ai_insights,
        }


PLUGIN_CLASS = GoalTrackerPlugin
