from __future__ import annotations

from unittest.mock import MagicMock, patch

from notion_manager.client import NotionClient


class TestBlocksToText:
    """Tests for the static NotionClient.blocks_to_text helper."""

    def test_blocks_to_text_empty(self):
        result = NotionClient.blocks_to_text([])
        assert result == ""

    def test_blocks_to_text_paragraph(self):
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Hello world"}]
                },
            }
        ]
        result = NotionClient.blocks_to_text(blocks)
        assert result == "Hello world"

    def test_blocks_to_text_multiple_blocks(self):
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"plain_text": "Title"}]
                },
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Body text"}]
                },
            },
        ]
        result = NotionClient.blocks_to_text(blocks)
        assert result == "Title\nBody text"

    def test_blocks_to_text_nested(self):
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "Parent"}]
                },
                "children": [
                    {
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"plain_text": "Child"}]
                        },
                    }
                ],
            }
        ]
        result = NotionClient.blocks_to_text(blocks)
        assert result == "Parent\nChild"

    def test_blocks_to_text_block_without_rich_text(self):
        blocks = [
            {
                "type": "divider",
                "divider": {},
            }
        ]
        result = NotionClient.blocks_to_text(blocks)
        assert result == ""

    def test_blocks_to_text_multiple_rich_text_parts(self):
        blocks = [
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"plain_text": "Hello"},
                        {"plain_text": " "},
                        {"plain_text": "world"},
                    ]
                },
            }
        ]
        result = NotionClient.blocks_to_text(blocks)
        assert result == "Hello world"


class TestNotionClientInit:
    """Test that NotionClient can be constructed with a mocked notion_client."""

    def test_init_with_mock(self):
        with patch("notion_manager.client.Client") as MockClient:
            MockClient.return_value = MagicMock()
            client = NotionClient(token="fake-token")
            assert client is not None
            MockClient.assert_called_once_with(auth="fake-token")

    def test_get_page_delegates(self):
        with patch("notion_manager.client.Client") as MockClient:
            mock_sdk = MagicMock()
            MockClient.return_value = mock_sdk
            mock_sdk.pages.retrieve.return_value = {"id": "page-1"}

            client = NotionClient(token="fake-token")
            result = client.get_page("page-1")
            assert result == {"id": "page-1"}

    def test_query_database_paginates(self):
        with patch("notion_manager.client.Client") as MockClient:
            mock_sdk = MagicMock()
            MockClient.return_value = mock_sdk
            # First call returns has_more=True, second returns has_more=False
            mock_sdk.databases.query.side_effect = [
                {"results": [{"id": "r1"}], "has_more": True, "next_cursor": "cur1"},
                {"results": [{"id": "r2"}], "has_more": False, "next_cursor": None},
            ]

            client = NotionClient(token="fake-token")
            results = client.query_database("db-1")
            assert len(results) == 2
            assert results[0]["id"] == "r1"
            assert results[1]["id"] == "r2"
