from __future__ import annotations

import datetime
from typing import Any

from notion_manager.ai_provider import AIProvider
from notion_manager.client import NotionClient


class WeeklyReviewPlugin:
    name = "weekly_review"
    description = "주간 리뷰 초안 작성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        parent_page_id: str | None = kwargs.get("parent_page_id")
        create_page: bool = kwargs.get("create_page", True)

        today = datetime.date.today()
        week_str = today.strftime("%Y-W%W")
        seven_days_ago = today - datetime.timedelta(days=7)

        try:
            pages = client.search("", filter_type="page")
        except Exception as exc:
            return {"error": str(exc)}

        edited_pages: list[str] = []
        for page in pages:
            last_edited = page.get("last_edited_time", "")
            if last_edited:
                try:
                    edited_date = datetime.date.fromisoformat(last_edited[:10])
                    if edited_date >= seven_days_ago:
                        props = page.get("properties", {})
                        title = ""
                        for prop in props.values():
                            if prop.get("type") == "title":
                                rich_texts = prop.get("title", [])
                                title = "".join(rt.get("plain_text", "") for rt in rich_texts)
                                break
                        edited_pages.append(title or page.get("id", ""))
                except (ValueError, TypeError):
                    continue

        activity_text = (
            f"주간 리뷰 기간: {seven_days_ago.isoformat()} ~ {today.isoformat()}\n"
            f"편집된 페이지 수: {len(edited_pages)}\n"
            f"페이지 목록:\n" + "\n".join(f"- {p}" for p in edited_pages[:50])
        )

        ai_config = config.get("ai", {})
        ai = AIProvider(
            api_key=ai_config.get("api_key", ""),
            model=ai_config.get("model", "claude-opus-4-5"),
            max_tokens=ai_config.get("max_tokens", 1024),
        )

        try:
            review_content = ai.generate_weekly_review(activity_text)
        except Exception as exc:
            review_content = f"AI error: {exc}"

        created_page_id: str | None = None

        if create_page and parent_page_id:
            try:
                page = client._client.pages.create(
                    parent={"page_id": parent_page_id},
                    properties={
                        "title": {
                            "title": [{"type": "text", "text": {"content": f"주간 리뷰 {week_str}"}}]
                        }
                    },
                    children=[
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": review_content}}]
                            },
                        }
                    ],
                )
                created_page_id = page.get("id", "")
            except Exception as exc:
                return {
                    "week": week_str,
                    "pages_edited": len(edited_pages),
                    "review_content": review_content,
                    "created_page_id": None,
                    "create_error": str(exc),
                }

        return {
            "week": week_str,
            "pages_edited": len(edited_pages),
            "review_content": review_content,
            "created_page_id": created_page_id,
        }


PLUGIN_CLASS = WeeklyReviewPlugin
