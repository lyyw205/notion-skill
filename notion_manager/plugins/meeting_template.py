from __future__ import annotations

from typing import Any

from notion_manager.client import NotionClient


class MeetingTemplatePlugin:
    name = "meeting_template"
    description = "회의록 템플릿 자동 생성"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        parent_page_id: str | None = kwargs.get("parent_page_id")
        title: str | None = kwargs.get("title")
        attendees: list[str] = kwargs.get("attendees", [])
        agenda: list[str] = kwargs.get("agenda", [])

        if not parent_page_id:
            return {"error": "parent_page_id required"}
        if not title:
            return {"error": "title required"}

        children: list[dict] = []

        # 참석자 section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "참석자"}}]
            },
        })
        if attendees:
            for attendee in attendees:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": attendee}}]
                    },
                })
        else:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []},
            })

        # 안건 section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "안건"}}]
            },
        })
        if agenda:
            for item in agenda:
                children.append({
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": item}}]
                    },
                })
        else:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []},
            })

        # 논의사항 section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "논의사항"}}]
            },
        })
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": []},
        })

        # 결정사항 section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "결정사항"}}]
            },
        })
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": []},
        })

        # 액션아이템 section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "액션아이템"}}]
            },
        })
        children.append({
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [],
                "checked": False,
            },
        })

        try:
            page = client.create_page(
                parent={"page_id": parent_page_id},
                properties={
                    "title": {
                        "title": [{"type": "text", "text": {"content": title}}]
                    }
                },
                children=children,
            )
        except Exception as exc:
            return {"error": str(exc)}

        return {
            "created_page_id": page.get("id", ""),
            "title": title,
        }


