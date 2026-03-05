from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from notion_manager.client import NotionClient


def _get_page_title(page: dict[str, Any]) -> str:
    """Extract title from a Notion page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            rich_texts = prop.get("title", [])
            return "".join(rt.get("plain_text", "") for rt in rich_texts)
    return page.get("id", "untitled")


class BackupPlugin:
    name = "backup"
    description = "워크스페이스 백업 (JSON/Markdown)"

    def execute(self, client: NotionClient, config: dict, **kwargs: Any) -> dict:
        page_ids: list[str] | None = kwargs.get("page_ids")
        fmt: str = config.get("backup", {}).get("format", "json")
        backup_base: str = config.get("backup", {}).get("backup_dir", "backups")

        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = Path(backup_base) / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Determine pages to back up
        if page_ids:
            pages_to_backup: list[dict[str, Any]] = []
            for pid in page_ids:
                try:
                    page = client.get_page(pid)
                    pages_to_backup.append(page)
                except Exception:
                    continue
        else:
            try:
                pages_to_backup = client.search("", filter_type="page")
            except Exception as exc:
                return {"error": f"failed to fetch pages: {exc}"}

        manifest: list[dict[str, Any]] = []

        for page in pages_to_backup:
            page_id = page.get("id", "")
            title = _get_page_title(page)
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:80]
            filename_stem = f"{page_id[:8]}_{safe_title}".strip("_")

            try:
                blocks = client.get_page_blocks(page_id)
            except Exception as exc:
                manifest.append({"page_id": page_id, "title": title, "error": str(exc)})
                continue

            if fmt == "markdown":
                content = self._blocks_to_markdown(blocks)
                filename = f"{filename_stem}.md"
                file_path = backup_dir / filename
                file_path.write_text(f"# {title}\n\n{content}", encoding="utf-8")
            else:
                content_data = {"page": page, "blocks": blocks}
                filename = f"{filename_stem}.json"
                file_path = backup_dir / filename
                file_path.write_text(
                    json.dumps(content_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            manifest.append(
                {
                    "page_id": page_id,
                    "title": title,
                    "file": filename,
                }
            )

        index_data = {
            "timestamp": timestamp,
            "format": fmt,
            "page_count": len(manifest),
            "pages": manifest,
        }
        index_path = backup_dir / "index.json"
        index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "backup_dir": str(backup_dir),
            "page_count": len([m for m in manifest if "error" not in m]),
            "format": fmt,
        }

    def _blocks_to_markdown(self, blocks: list[dict[str, Any]]) -> str:
        """Convert Notion blocks to Markdown text."""
        lines: list[str] = []

        def _rich_text_to_str(rich_texts: list[dict[str, Any]]) -> str:
            return "".join(rt.get("plain_text", "") for rt in rich_texts)

        def _convert(block: dict[str, Any], depth: int = 0) -> None:
            btype = block.get("type", "")
            content = block.get(btype, {})
            rich_texts: list[dict[str, Any]] = content.get("rich_text", [])
            text = _rich_text_to_str(rich_texts)
            indent = "  " * depth

            if btype == "heading_1":
                lines.append(f"# {text}")
            elif btype == "heading_2":
                lines.append(f"## {text}")
            elif btype == "heading_3":
                lines.append(f"### {text}")
            elif btype in ("bulleted_list_item",):
                lines.append(f"{indent}- {text}")
            elif btype == "numbered_list_item":
                lines.append(f"{indent}1. {text}")
            elif btype == "to_do":
                checked = content.get("checked", False)
                checkbox = "[x]" if checked else "[ ]"
                lines.append(f"{indent}- {checkbox} {text}")
            elif btype == "code":
                language = content.get("language", "")
                lines.append(f"```{language}")
                lines.append(text)
                lines.append("```")
            elif btype == "quote":
                lines.append(f"> {text}")
            elif btype == "divider":
                lines.append("---")
            elif btype == "callout":
                lines.append(f"> **Note:** {text}")
            elif btype == "paragraph":
                if text:
                    lines.append(text)
                else:
                    lines.append("")
            elif text:
                lines.append(text)

            children: list[dict[str, Any]] = block.get("children", [])
            for child in children:
                _convert(child, depth + 1)

        for block in blocks:
            _convert(block)

        return "\n".join(lines)


PLUGIN_CLASS = BackupPlugin
