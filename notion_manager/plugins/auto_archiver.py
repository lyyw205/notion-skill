from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class AutoArchiverPlugin:
    name = "auto_archiver"
    description = "N일 이상 미편집 페이지 자동 아카이빙"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        days: int = kwargs.get("days", 90)
        dry_run: bool = kwargs.get("dry_run", True)

        cutoff = datetime.now(tz=UTC) - timedelta(days=days)

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": f"failed to fetch pages: {exc}"}

        candidates: list[dict[str, Any]] = []

        for page in pages:
            pid = page.get("id", "")
            title = _get_title(page)
            last_edited_raw: str = page.get("last_edited_time", "")

            if not last_edited_raw:
                continue

            try:
                last_edited_dt = datetime.fromisoformat(
                    last_edited_raw.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            if last_edited_dt < cutoff:
                candidates.append(
                    {
                        "id": pid,
                        "title": title,
                        "last_edited": last_edited_raw,
                    }
                )

        archived: list[dict[str, Any]] = []

        if not dry_run:
            for item in candidates:
                try:
                    client._client.pages.update(
                        page_id=item["id"], archived=True
                    )
                    archived.append(item)
                except Exception as exc:
                    archived.append({**item, "error": str(exc)})

        result: dict[str, Any] = {
            "candidates": candidates,
            "dry_run": dry_run,
            "count": len(candidates),
        }

        if not dry_run:
            result["archived"] = archived

        return result


