from __future__ import annotations

import datetime
from typing import Any

from notion_manager.client import NotionClient


class DailyJournalPlugin:
    name = "daily_journal"
    description = "일간 저널 페이지 자동 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        parent_page_id: str | None = kwargs.get("parent_page_id")
        if not parent_page_id:
            return {"error": "parent_page_id required"}

        today = datetime.date.today().isoformat()

        try:
            page = client.create_page(
                parent={"page_id": parent_page_id},
                properties={
                    "title": {
                        "title": [{"type": "text", "text": {"content": today}}]
                    }
                },
                children=[
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "오늘의 할 일"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [],
                            "checked": False,
                        },
                    },
                    {
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [],
                            "checked": False,
                        },
                    },
                    {
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [],
                            "checked": False,
                        },
                    },
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "감사일기"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": []
                        },
                    },
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": "메모"}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": []
                        },
                    },
                ],
            )
        except Exception as exc:
            return {"error": str(exc)}

        created_page_id = page.get("id", "")
        return {
            "created_page_id": created_page_id,
            "date": today,
            "template_used": "default",
        }


