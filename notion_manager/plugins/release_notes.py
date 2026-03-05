from __future__ import annotations

from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


def _get_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class ReleaseNotesPlugin:
    name = "release_notes"
    description = "변경 로그 기반 릴리즈 노트 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        database_id: str | None = kwargs.get("database_id")
        version: str = kwargs.get("version") or ""
        create_page: bool = kwargs.get("create_page", False)
        parent_page_id: str | None = kwargs.get("parent_page_id")

        if not database_id:
            return {"error": "database_id required"}

        try:
            pages = client.query_database(database_id)
        except Exception as exc:
            return {"error": str(exc)}

        changes: list[str] = []
        for page in pages:
            title = _get_title(page)
            try:
                blocks = client.get_page_blocks(page.get("id", ""))
                text = NotionClient.blocks_to_text(blocks)
                entry = f"### {title}\n{text}" if text.strip() else f"### {title}"
                changes.append(entry)
            except Exception:
                changes.append(f"### {title}")

        changes_text = "\n\n".join(changes)

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            release_notes = ai.generate_release_notes(changes_text, version=version)
        except Exception as exc:
            return {"error": str(exc)}

        created_page_id: str | None = None

        if create_page and parent_page_id:
            page_title = f"릴리즈 노트 {version}" if version else "릴리즈 노트"
            try:
                page = client.create_page(
                    parent={"page_id": parent_page_id},
                    properties={
                        "title": {
                            "title": [{"type": "text", "text": {"content": page_title}}]
                        }
                    },
                    children=[
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": release_notes}}]
                            },
                        }
                    ],
                )
                created_page_id = page.get("id", "")
            except Exception as exc:
                return {
                    "version": version,
                    "changes": changes,
                    "release_notes": release_notes,
                    "created_page_id": None,
                    "create_error": str(exc),
                }

        return {
            "version": version,
            "changes": changes,
            "release_notes": release_notes,
            "created_page_id": created_page_id,
        }


