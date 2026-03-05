from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient
from notion_manager.plugin_registry import PluginRegistry


class WorkspaceHealthDashboardPlugin:
    name = "workspace_health_dashboard"
    description = "기존 분석 플러그인 통합 종합 건강 점수 (0-100)"

    HEALTH_PLUGINS = {
        "duplicate_detector": {"weight": 20, "score_fn": "_score_duplicates"},
        "empty_detector": {"weight": 15, "score_fn": "_score_empties"},
        "orphan_detector": {"weight": 15, "score_fn": "_score_orphans"},
        "db_health_checker": {"weight": 20, "score_fn": "_score_db_health"},
        "usage_analyzer": {"weight": 15, "score_fn": "_score_usage"},
        "db_stats": {"weight": 15, "score_fn": "_score_db_stats"},
    }

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")

        registry = PluginRegistry()
        registry.discover()

        scores: dict[str, dict[str, Any]] = {}
        total_weight = 0
        weighted_sum = 0.0
        errors: list[str] = []

        for plugin_name, meta in self.HEALTH_PLUGINS.items():
            plugin_cls = registry.get(plugin_name)
            if plugin_cls is None:
                errors.append(f"{plugin_name}: not found")
                continue

            plugin = plugin_cls()
            plugin_kwargs: dict[str, Any] = {}
            if database_id:
                plugin_kwargs["database_id"] = database_id

            try:
                result = plugin.execute(client, config, **plugin_kwargs)
            except Exception as exc:
                errors.append(f"{plugin_name}: {exc}")
                continue

            if "error" in result:
                errors.append(f"{plugin_name}: {result['error']}")
                continue

            score_fn = getattr(self, meta["score_fn"], None)
            if score_fn:
                score = score_fn(result)
                weight = meta["weight"]
                scores[plugin_name] = {"score": score, "weight": weight}
                weighted_sum += score * weight
                total_weight += weight

        overall = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

        grade = "A"
        if overall < 60:
            grade = "F"
        elif overall < 70:
            grade = "D"
        elif overall < 80:
            grade = "C"
        elif overall < 90:
            grade = "B"

        return {
            "overall_score": overall,
            "grade": grade,
            "scores": scores,
            "errors": errors,
            "plugins_evaluated": len(scores),
            "plugins_failed": len(errors),
        }

    @staticmethod
    def _score_duplicates(result: dict) -> float:
        dupes = len(result.get("duplicates", []))
        total = result.get("total_checked", 1)
        ratio = dupes / max(total, 1)
        return max(0.0, 100.0 * (1.0 - ratio * 10))

    @staticmethod
    def _score_empties(result: dict) -> float:
        empties = len(result.get("empty_pages", []))
        total = result.get("total_checked", 1)
        ratio = empties / max(total, 1)
        return max(0.0, 100.0 * (1.0 - ratio * 5))

    @staticmethod
    def _score_orphans(result: dict) -> float:
        orphans = len(result.get("orphan_pages", []))
        total = result.get("total_checked", 1)
        ratio = orphans / max(total, 1)
        return max(0.0, 100.0 * (1.0 - ratio * 5))

    @staticmethod
    def _score_db_health(result: dict) -> float:
        issues = len(result.get("issues", []))
        return max(0.0, 100.0 - issues * 10)

    @staticmethod
    def _score_usage(result: dict) -> float:
        stats = result.get("stats", {})
        active = stats.get("active_pages", 0)
        total = stats.get("total_pages", 1)
        if total == 0:
            return 50.0
        return min(100.0, (active / total) * 100)

    @staticmethod
    def _score_db_stats(result: dict) -> float:
        total = result.get("total_pages", 0)
        if total == 0:
            return 50.0
        return min(100.0, 70.0 + min(total, 30))


