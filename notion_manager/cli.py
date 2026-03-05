from __future__ import annotations

import json
import os
import sys
from typing import Any

import click

from notion_manager.config import load_config
from notion_manager.client import NotionClient
from notion_manager.plugin_registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_client(cfg: dict[str, Any]) -> NotionClient:
    """Instantiate NotionClient from config dict; exit with helpful message on missing token."""
    token: str = cfg.get("notion_token", "")
    if not token:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + "NOTION_TOKEN is not set. "
            "Export it as an environment variable or add it to your config YAML.",
            err=True,
        )
        sys.exit(1)
    rl = cfg.get("rate_limit", {})
    return NotionClient(
        token=token,
        requests_per_second=rl.get("requests_per_second", 3),
        max_retries=rl.get("max_retries", 5),
        backoff_factor=rl.get("backoff_factor", 2.0),
    )


def _ensure_api_key(cfg: dict[str, Any]) -> None:
    """Exit with a helpful message when the Anthropic API key is missing."""
    ai_cfg = cfg.get("ai", {})
    key: str = cfg.get("anthropic_api_key", "") or ai_cfg.get("api_key", "")
    if not key:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + "ANTHROPIC_API_KEY is not set. "
            "Export it as an environment variable or add it to your config YAML.",
            err=True,
        )
        sys.exit(1)
    # Inject into ai sub-dict so plugins can find it
    cfg.setdefault("ai", {})["api_key"] = key


def _get_plugin(name: str) -> Any:
    registry = PluginRegistry()
    registry._autodiscover()
    cls = registry.get(name)
    if cls is None:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + f"Plugin '{name}' not found.",
            err=True,
        )
        sys.exit(1)
    return cls()


def _print_error(result: dict[str, Any]) -> None:
    click.echo(click.style("Error: ", fg="red", bold=True) + result["error"], err=True)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--config",
    "config_path",
    default="config/default.yaml",
    show_default=True,
    help="Path to YAML config file.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    """notion-manager — automate your Notion workspace with AI."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("page_id")
@click.option("--insert", is_flag=True, default=False, help="Insert summary as a callout block on the page.")
@click.option("--database-id", default=None, help="Summarize all pages in a database instead.")
@click.pass_context
def summarize(ctx: click.Context, page_id: str, insert: bool, database_id: str | None) -> None:
    """Summarize a Notion page (or all pages in a database) using AI."""
    cfg = load_config(ctx.obj["config_path"])
    _ensure_api_key(cfg)
    client = _build_client(cfg)
    plugin = _get_plugin("summarizer")

    kwargs: dict[str, Any] = {"insert": insert}
    if database_id:
        kwargs["database_id"] = database_id
    else:
        kwargs["page_id"] = page_id

    result = plugin.execute(client, cfg, **kwargs)

    if isinstance(result, list):
        ok = [r for r in result if "error" not in r and not r.get("skipped")]
        skipped = [r for r in result if r.get("skipped")]
        errors = [r for r in result if "error" in r]
        click.echo(click.style(f"Summarized {len(ok)} page(s).", fg="green", bold=True))
        for r in ok:
            click.echo(f"\n  {click.style(r['page_id'], fg='cyan')}")
            click.echo(f"  {r['summary']}")
            if r.get("inserted"):
                click.echo(click.style("  [inserted as callout]", fg="yellow"))
        if skipped:
            click.echo(click.style(f"\nSkipped {len(skipped)} page(s) (text too short).", fg="yellow"))
        if errors:
            click.echo(click.style(f"\n{len(errors)} error(s):", fg="red"))
            for r in errors:
                click.echo(f"  {r['page_id']}: {r['error']}")
        return

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    if result.get("skipped"):
        click.echo(click.style("Skipped: ", fg="yellow") + result.get("reason", "text too short"))
        return

    click.echo(click.style("Summary", fg="green", bold=True) + f" ({result['page_id']}):")
    click.echo(result["summary"])
    if result.get("inserted"):
        click.echo(click.style("\n[Inserted as a callout block on the page]", fg="yellow"))


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("page_id")
@click.option(
    "--tags",
    default=None,
    help="Comma-separated list of allowed tags (AI picks from these). Omit to auto-generate.",
)
@click.option("--property", "tag_property", default="Tags", show_default=True, help="Notion property name to update.")
@click.pass_context
def tag(ctx: click.Context, page_id: str, tags: str | None, tag_property: str) -> None:
    """Auto-tag a Notion page using AI."""
    cfg = load_config(ctx.obj["config_path"])
    _ensure_api_key(cfg)
    client = _build_client(cfg)
    plugin = _get_plugin("tagger")

    available_tags = [t.strip() for t in tags.split(",")] if tags else None

    result = plugin.execute(
        client, cfg,
        page_id=page_id,
        available_tags=available_tags,
        tag_property=tag_property,
    )

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    tag_list = ", ".join(result.get("tags", []))
    click.echo(click.style("Tags applied: ", fg="green", bold=True) + click.style(tag_list, fg="cyan"))
    if result.get("updated"):
        click.echo(click.style(f"[Property '{tag_property}' updated on page {page_id}]", fg="yellow"))
    if result.get("update_error"):
        click.echo(click.style("Update error: ", fg="red") + result["update_error"])


# ---------------------------------------------------------------------------
# search sub-group
# ---------------------------------------------------------------------------

@cli.group()
def search() -> None:
    """Index and query Notion content with natural language."""


@search.command("index")
@click.pass_context
def search_index(ctx: click.Context) -> None:
    """Index all Notion pages into the vector store."""
    cfg = load_config(ctx.obj["config_path"])
    client = _build_client(cfg)
    plugin = _get_plugin("search")

    click.echo("Indexing Notion pages...")
    result = plugin.execute(client, cfg, action="index")

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    click.echo(
        click.style("Done. ", fg="green", bold=True)
        + f"Indexed {click.style(str(result['indexed_pages']), fg='cyan')} page(s) "
        f"into {click.style(str(result['total_chunks']), fg='cyan')} chunk(s)."
    )


@search.command("query")
@click.argument("question")
@click.pass_context
def search_query(ctx: click.Context, question: str) -> None:
    """Ask a question answered from your indexed Notion pages."""
    cfg = load_config(ctx.obj["config_path"])
    _ensure_api_key(cfg)
    client = _build_client(cfg)
    plugin = _get_plugin("search")

    result = plugin.execute(client, cfg, action="query", question=question)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    click.echo(click.style("Answer:", fg="green", bold=True))
    click.echo(result.get("answer", ""))

    sources = result.get("sources", [])
    if sources:
        click.echo(click.style("\nSources:", fg="blue", bold=True))
        for src in sources:
            relevance = src.get("relevance", 0)
            title = src.get("title") or src.get("page_id", "")
            click.echo(
                f"  {click.style(title, fg='cyan')}"
                f"  {click.style(f'(relevance: {relevance:.2f})', fg='yellow')}"
            )


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--pages",
    default=None,
    help="Comma-separated page IDs to back up. Omit to back up all accessible pages.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default=None,
    help="Output format (overrides config). Default: json.",
)
@click.pass_context
def backup(ctx: click.Context, pages: str | None, fmt: str | None) -> None:
    """Back up Notion pages to local files."""
    cfg = load_config(ctx.obj["config_path"])
    client = _build_client(cfg)

    # Allow --format to override config
    if fmt:
        cfg.setdefault("backup", {})["format"] = fmt

    plugin = _get_plugin("backup")
    page_ids = [p.strip() for p in pages.split(",")] if pages else None

    click.echo("Starting backup...")
    result = plugin.execute(client, cfg, page_ids=page_ids)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    click.echo(
        click.style("Backup complete. ", fg="green", bold=True)
        + f"{result['page_count']} page(s) saved as "
        + click.style(result["format"].upper(), fg="cyan")
        + " to "
        + click.style(result["backup_dir"], fg="cyan")
    )


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("database_id")
@click.option("--status-property", default="Status", show_default=True, help="Name of the status property.")
@click.option("--date-property", default="Date", show_default=True, help="Name of the date/due-date property.")
@click.pass_context
def analyze(ctx: click.Context, database_id: str, status_property: str, date_property: str) -> None:
    """Analyze a task database for completion rates and productivity insights."""
    cfg = load_config(ctx.obj["config_path"])
    _ensure_api_key(cfg)
    client = _build_client(cfg)
    plugin = _get_plugin("task_analyzer")

    click.echo("Analyzing database...")
    result = plugin.execute(
        client, cfg,
        database_id=database_id,
        status_property=status_property,
        date_property=date_property,
    )

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    # Metrics table
    click.echo(click.style("\nTask Metrics", fg="green", bold=True))
    click.echo(f"  Total tasks   : {click.style(str(result['total_tasks']), fg='cyan')}")
    click.echo(f"  Completed     : {click.style(str(result['completed']), fg='green')}")
    click.echo(f"  In progress   : {click.style(str(result['in_progress']), fg='yellow')}")
    click.echo(f"  Not started   : {click.style(str(result['not_started']), fg='white')}")
    click.echo(f"  Overdue       : {click.style(str(result['overdue']), fg='red')}")
    click.echo(f"  Completion %  : {click.style(str(result['completion_rate']) + '%', fg='cyan', bold=True)}")

    # Status breakdown
    by_status: dict[str, int] = result.get("tasks_by_status", {})
    if by_status:
        click.echo(click.style("\nStatus Breakdown", fg="blue", bold=True))
        for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
            click.echo(f"  {status:<25} {count}")

    # Overdue list
    overdue_tasks: list[str] = result.get("overdue_tasks", [])
    if overdue_tasks:
        click.echo(click.style("\nOverdue Tasks", fg="red", bold=True))
        for t in overdue_tasks[:10]:
            click.echo(f"  - {t}")
        if len(overdue_tasks) > 10:
            click.echo(f"  ... and {len(overdue_tasks) - 10} more")

    # Weekly trend
    weekly: dict[str, int] = result.get("weekly_trend", {})
    if weekly:
        click.echo(click.style("\nWeekly Completions (last 4 weeks)", fg="blue", bold=True))
        for week, count in sorted(weekly.items()):
            bar = click.style("#" * count, fg="green")
            click.echo(f"  {week}: {bar} ({count})")

    # AI insights
    ai_insights: dict[str, Any] = result.get("ai_insights", {})
    if ai_insights and "error" not in ai_insights:
        click.echo(click.style("\nAI Insights", fg="magenta", bold=True))

        summary = ai_insights.get("summary")
        if summary:
            click.echo(f"  Summary   : {summary}")

        priorities: list[str] = ai_insights.get("priorities", [])
        if priorities:
            click.echo(click.style("  Priorities:", fg="yellow"))
            for p in priorities:
                click.echo(f"    - {p}")

        blockers: list[str] = ai_insights.get("blockers", [])
        if blockers:
            click.echo(click.style("  Blockers:", fg="red"))
            for b in blockers:
                click.echo(f"    - {b}")

        next_actions: list[str] = ai_insights.get("next_actions", [])
        if next_actions:
            click.echo(click.style("  Next actions:", fg="cyan"))
            for a in next_actions:
                click.echo(f"    - {a}")
    elif ai_insights.get("error"):
        click.echo(click.style("\nAI insights unavailable: ", fg="yellow") + ai_insights["error"])


# ---------------------------------------------------------------------------
# plugins list
# ---------------------------------------------------------------------------

@cli.group("plugins")
def plugins_group() -> None:
    """Manage and inspect available plugins."""


@plugins_group.command("list")
@click.option("--category", default=None, help="Filter by category name.")
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json"]), help="Output format.")
@click.pass_context
def plugins_list(ctx: click.Context, category: str | None, fmt: str) -> None:
    """List all discovered plugins grouped by category."""
    from notion_manager.plugin_state import load_effective_plugins

    cfg = load_config(ctx.obj["config_path"])
    registry = PluginRegistry()
    registry._autodiscover()
    effective = set(load_effective_plugins(cfg))
    categories = registry.get_categories()

    if fmt == "json":
        data: list[dict[str, Any]] = []
        for name in registry.list_plugins():
            meta = registry.get_meta(name)
            if category and (not meta or meta.category != category):
                continue
            data.append({
                "name": name,
                "description": meta.description if meta else "",
                "category": meta.category if meta else "uncategorized",
                "enabled": name in effective,
            })
        click.echo(json.dumps(data, indent=2))
        return

    # Text output grouped by category
    cat_order = list(categories.keys())
    plugins_by_cat: dict[str, list[str]] = {}
    for name in registry.list_plugins():
        meta = registry.get_meta(name)
        cat = meta.category if meta else "uncategorized"
        if category and cat != category:
            continue
        plugins_by_cat.setdefault(cat, []).append(name)

    if not plugins_by_cat:
        click.echo(click.style("No plugins found.", fg="yellow"))
        return

    total = sum(len(v) for v in plugins_by_cat.values())
    click.echo(click.style(f"Found {total} plugin(s):\n", fg="green", bold=True))

    for cat_key in cat_order:
        if cat_key not in plugins_by_cat:
            continue
        cat_data = categories.get(cat_key, {})
        label = cat_data.get("label", cat_key)
        click.echo(click.style(f"  [{label}]", fg="magenta", bold=True))
        for name in sorted(plugins_by_cat[cat_key]):
            meta = registry.get_meta(name)
            status = click.style("[ON]", fg="green") if name in effective else click.style("[OFF]", fg="red")
            desc = meta.description if meta else ""
            click.echo(f"    {status} {click.style(name, fg='cyan', bold=True)}" + (f"  — {desc}" if desc else ""))
        click.echo()

    # uncategorized
    if "uncategorized" in plugins_by_cat:
        click.echo(click.style("  [Uncategorized]", fg="magenta", bold=True))
        for name in sorted(plugins_by_cat["uncategorized"]):
            meta = registry.get_meta(name)
            status = click.style("[ON]", fg="green") if name in effective else click.style("[OFF]", fg="red")
            desc = meta.description if meta else ""
            click.echo(f"    {status} {click.style(name, fg='cyan', bold=True)}" + (f"  — {desc}" if desc else ""))


@plugins_group.command("enable")
@click.argument("name")
def plugins_enable(name: str) -> None:
    """Enable a plugin (persisted to data/plugin_state.json)."""
    from notion_manager.plugin_state import toggle_plugin
    toggle_plugin(name, True)
    click.echo(click.style(f"Plugin '{name}' enabled.", fg="green"))


@plugins_group.command("disable")
@click.argument("name")
def plugins_disable(name: str) -> None:
    """Disable a plugin (persisted to data/plugin_state.json)."""
    from notion_manager.plugin_state import toggle_plugin
    toggle_plugin(name, False)
    click.echo(click.style(f"Plugin '{name}' disabled.", fg="yellow"))


@plugins_group.command("info")
@click.argument("name")
def plugins_info(name: str) -> None:
    """Show detailed info for a plugin."""
    from notion_manager.execution_tracker import ExecutionTracker

    registry = PluginRegistry()
    registry._autodiscover()
    meta = registry.get_meta(name)
    if not meta:
        click.echo(click.style(f"Plugin '{name}' not found.", fg="red"), err=True)
        return

    click.echo(click.style(f"Plugin: {meta.name}", fg="cyan", bold=True))
    click.echo(f"  Description : {meta.description}")
    click.echo(f"  Category    : {meta.category}")
    click.echo(f"  Requires AI : {meta.requires_ai}")
    click.echo(f"  Risk Level  : {meta.risk_level}")
    click.echo(f"  Version     : {meta.version}")

    try:
        tracker = ExecutionTracker()
        history = tracker.get_history(name, limit=5)
        tracker.close()
        if history:
            click.echo(click.style("\n  Recent executions:", bold=True))
            for h in history:
                status_color = "green" if h["status"] == "success" else "red"
                click.echo(
                    f"    {h['started_at'][:19]}  "
                    f"{click.style(h['status'], fg=status_color)}  "
                    f"{h.get('duration_ms', 0)}ms"
                )
    except Exception:
        pass


@plugins_group.command("run")
@click.argument("name")
@click.option("--param", multiple=True, help="key=value parameters.")
@click.pass_context
def plugins_run(ctx: click.Context, name: str, param: tuple[str, ...]) -> None:
    """Execute a plugin directly."""
    from notion_manager.execution_tracker import ExecutionTracker

    cfg = load_config(ctx.obj["config_path"])
    registry = PluginRegistry()
    registry._autodiscover()
    cls = registry.get(name)
    if not cls:
        click.echo(click.style(f"Plugin '{name}' not found.", fg="red"), err=True)
        return

    kwargs: dict[str, str] = {}
    for p in param:
        if "=" not in p:
            click.echo(click.style(f"Invalid param format: {p} (expected key=value)", fg="red"), err=True)
            return
        k, v = p.split("=", 1)
        kwargs[k] = v

    client = _build_client(cfg)
    plugin = cls()
    tracker = ExecutionTracker()

    with tracker.track(name, kwargs) as track_ctx:
        result = plugin.execute(client, cfg, **kwargs)
        track_ctx["result"] = result

    tracker.close()
    click.echo(click.style(f"Plugin '{name}' executed successfully.", fg="green"))
    click.echo(json.dumps(result, indent=2, default=str))


@plugins_group.command("history")
@click.option("--name", default=None, help="Filter by plugin name.")
@click.option("--limit", default=20, help="Number of records to show.")
def plugins_history(name: str | None, limit: int) -> None:
    """Show plugin execution history."""
    from notion_manager.execution_tracker import ExecutionTracker

    tracker = ExecutionTracker()
    history = tracker.get_history(plugin_name=name, limit=limit)
    tracker.close()

    if not history:
        click.echo(click.style("No execution history found.", fg="yellow"))
        return

    click.echo(click.style(f"{'Plugin':<30} {'Status':<10} {'Duration':<12} {'Started At'}", bold=True))
    click.echo("-" * 80)
    for h in history:
        status_color = "green" if h["status"] == "success" else ("red" if h["status"] == "error" else "yellow")
        dur = f"{h.get('duration_ms', 0)}ms" if h.get("duration_ms") is not None else "—"
        click.echo(
            f"  {h['plugin_name']:<28} "
            f"{click.style(h['status'], fg=status_color):<10} "
            f"{dur:<12} "
            f"{h['started_at'][:19]}"
        )


# ---------------------------------------------------------------------------
# _setup helper
# ---------------------------------------------------------------------------

def _setup(ctx: click.Context) -> tuple[dict[str, Any], NotionClient]:
    """Load config and build client; exit on missing token."""
    cfg = load_config(ctx.obj["config_path"])
    client = _build_client(cfg)
    return cfg, client


# ---------------------------------------------------------------------------
# detect sub-group
# ---------------------------------------------------------------------------

@cli.group()
def detect() -> None:
    """워크스페이스 문제 탐지 (중복, 빈 페이지, 고아 페이지)"""


@detect.command("duplicates")
@click.option("--threshold", default=0.8, type=float, show_default=True, help="유사도 기준 (0.0-1.0)")
@click.pass_context
def detect_duplicates(ctx: click.Context, threshold: float) -> None:
    """중복 페이지를 탐지합니다."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("duplicate_detector")

    click.echo("Scanning for duplicate pages...")
    result = plugin.execute(client, cfg, threshold=threshold)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    duplicates: list[dict[str, Any]] = result.get("duplicates", [])
    total_checked: int = result.get("total_checked", 0)
    click.echo(
        click.style(f"Checked {total_checked} page(s). ", fg="green", bold=True)
        + click.style(f"Found {len(duplicates)} duplicate pair(s).", fg="cyan")
    )
    for dup in duplicates:
        titles = dup.get("titles", ["", ""])
        pages = dup.get("pages", ["", ""])
        sim = dup.get("similarity", 0.0)
        click.echo(
            f"\n  {click.style(titles[0], fg='yellow')} ({pages[0]})"
            f"\n  {click.style(titles[1], fg='yellow')} ({pages[1]})"
            f"\n  {click.style(f'similarity: {sim:.2%}', fg='cyan')}"
        )


@detect.command("empty")
@click.option("--min-chars", default=100, type=int, show_default=True, help="미완성 기준 글자수")
@click.pass_context
def detect_empty(ctx: click.Context, min_chars: int) -> None:
    """빈 페이지 및 미완성 페이지를 탐지합니다."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("empty_detector")

    click.echo("Scanning for empty/incomplete pages...")
    result = plugin.execute(client, cfg, min_chars=min_chars)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    empty: list[dict[str, Any]] = result.get("empty_pages", [])
    incomplete: list[dict[str, Any]] = result.get("incomplete_pages", [])
    total: int = result.get("total_checked", 0)

    click.echo(
        click.style(f"Checked {total} page(s). ", fg="green", bold=True)
        + click.style(f"{len(empty)} empty, {len(incomplete)} incomplete.", fg="cyan")
    )

    if empty:
        click.echo(click.style("\nEmpty pages:", fg="red", bold=True))
        for p in empty:
            click.echo(f"  {click.style(p['title'], fg='yellow')} ({p['id']})")

    if incomplete:
        click.echo(click.style(f"\nIncomplete pages (< {min_chars} chars):", fg="yellow", bold=True))
        for p in incomplete:
            count = p.get("char_count", 0)
            click.echo(f"  {click.style(p['title'], fg='yellow')} ({p['id']})  {count} chars")


@detect.command("orphans")
@click.pass_context
def detect_orphans(ctx: click.Context) -> None:
    """고아 페이지를 탐지합니다 (링크되지 않은 페이지)."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("orphan_detector")

    click.echo("Scanning for orphan pages...")
    result = plugin.execute(client, cfg)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    orphans: list[dict[str, Any]] = result.get("orphan_pages", [])
    total: int = result.get("total_pages", 0)

    click.echo(
        click.style(f"Checked {total} page(s). ", fg="green", bold=True)
        + click.style(f"Found {len(orphans)} orphan page(s).", fg="cyan")
    )
    for p in orphans:
        last_edited = p.get("last_edited", "")
        click.echo(
            f"  {click.style(p['title'], fg='yellow')} ({p['id']})"
            + (f"  last edited: {last_edited}" if last_edited else "")
        )


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--days", default=90, type=int, show_default=True, help="미편집 기간 (일)")
@click.option("--execute", "do_execute", is_flag=True, default=False, help="실제 아카이빙 실행 (기본: dry-run)")
@click.pass_context
def archive(ctx: click.Context, days: int, do_execute: bool) -> None:
    """오래된 페이지를 자동 아카이빙합니다."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("auto_archiver")

    dry_run = not do_execute
    if not dry_run:
        click.echo(click.style("Warning: ", fg="yellow", bold=True) + f"Archiving pages not edited in {days} days.")

    click.echo(f"{'[dry-run] ' if dry_run else ''}Scanning for pages older than {days} days...")
    result = plugin.execute(client, cfg, days=days, dry_run=dry_run)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    candidates: list[dict[str, Any]] = result.get("candidates", [])
    click.echo(
        click.style(f"Found {len(candidates)} candidate(s)", fg="cyan", bold=True)
        + (" — dry-run, no changes made." if dry_run else ".")
    )
    for item in candidates:
        click.echo(
            f"  {click.style(item['title'], fg='yellow')} ({item['id']})"
            f"  last edited: {item.get('last_edited', '')}"
        )

    if not dry_run:
        archived: list[dict[str, Any]] = result.get("archived", [])
        ok = [a for a in archived if "error" not in a]
        errs = [a for a in archived if "error" in a]
        click.echo(click.style(f"\nArchived {len(ok)} page(s).", fg="green", bold=True))
        if errs:
            click.echo(click.style(f"{len(errs)} error(s):", fg="red"))
            for e in errs:
                click.echo(f"  {e['id']}: {e['error']}")


# ---------------------------------------------------------------------------
# optimize-hierarchy
# ---------------------------------------------------------------------------

@cli.command("optimize-hierarchy")
@click.option("--max-depth", default=5, type=int, show_default=True, help="최대 허용 깊이")
@click.pass_context
def optimize_hierarchy(ctx: click.Context, max_depth: int) -> None:
    """계층 구조를 분석하고 정리 제안을 출력합니다."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("hierarchy_optimizer")

    click.echo("Analyzing hierarchy...")
    result = plugin.execute(client, cfg, max_depth=max_depth)

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    stats: dict[str, Any] = result.get("stats", {})
    click.echo(click.style("\nHierarchy Stats", fg="green", bold=True))
    click.echo(f"  Total pages   : {click.style(str(stats.get('total_pages', 0)), fg='cyan')}")
    click.echo(f"  Max depth     : {click.style(str(stats.get('max_depth', 0)), fg='cyan')}")
    click.echo(f"  Avg depth     : {click.style(str(stats.get('avg_depth', 0.0)), fg='cyan')}")
    click.echo(f"  Flat roots    : {click.style(str(stats.get('too_flat_roots', 0)), fg='yellow')}")

    too_deep: list[dict[str, Any]] = stats.get("too_deep", [])
    if too_deep:
        click.echo(click.style(f"\nPages exceeding max depth ({max_depth}):", fg="red", bold=True))
        for p in too_deep:
            click.echo(f"  depth={p['depth']}  {click.style(p['title'], fg='yellow')} ({p['id']})")

    suggestions: str = result.get("suggestions", "")
    if suggestions:
        click.echo(click.style("\nAI Suggestions:", fg="magenta", bold=True))
        click.echo(suggestions)


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------

@cli.command("sort")
@click.argument("database_id")
@click.option("--property", "sort_property", default="Date", show_default=True, help="정렬 기준 속성")
@click.option(
    "--direction",
    default="descending",
    show_default=True,
    type=click.Choice(["ascending", "descending"]),
    help="정렬 방향",
)
@click.pass_context
def sort_db(ctx: click.Context, database_id: str, sort_property: str, direction: str) -> None:
    """데이터베이스를 속성 기준으로 정렬합니다."""
    cfg, client = _setup(ctx)
    plugin = _get_plugin("auto_sorter")

    click.echo(f"Sorting database {database_id} by '{sort_property}' ({direction})...")
    result = plugin.execute(
        client, cfg,
        database_id=database_id,
        sort_property=sort_property,
        direction=direction,
    )

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    click.echo(
        click.style("Done. ", fg="green", bold=True)
        + f"Sorted {click.style(str(result['sorted_count']), fg='cyan')} page(s) "
        f"by {click.style(result['sort_property'], fg='cyan')} ({result['direction']})."
    )


# ---------------------------------------------------------------------------
# bulk-update
# ---------------------------------------------------------------------------

@cli.command("bulk-update")
@click.argument("database_id")
@click.option("--filter", "filter_json", required=True, help="필터 조건 (JSON)")
@click.option("--updates", "updates_json", required=True, help="업데이트 내용 (JSON)")
@click.pass_context
def bulk_update(ctx: click.Context, database_id: str, filter_json: str, updates_json: str) -> None:
    """데이터베이스 속성을 일괄 업데이트합니다."""
    cfg, client = _setup(ctx)

    try:
        filter_conditions: dict[str, Any] = json.loads(filter_json)
    except json.JSONDecodeError as exc:
        click.echo(click.style("Error: ", fg="red", bold=True) + f"Invalid --filter JSON: {exc}", err=True)
        sys.exit(1)

    try:
        updates: dict[str, Any] = json.loads(updates_json)
    except json.JSONDecodeError as exc:
        click.echo(click.style("Error: ", fg="red", bold=True) + f"Invalid --updates JSON: {exc}", err=True)
        sys.exit(1)

    plugin = _get_plugin("bulk_updater")

    click.echo(f"Bulk-updating database {database_id}...")
    result = plugin.execute(
        client, cfg,
        database_id=database_id,
        filter_conditions=filter_conditions,
        updates=updates,
    )

    if "error" in result:
        _print_error(result)
        sys.exit(1)

    click.echo(
        click.style("Done. ", fg="green", bold=True)
        + f"Updated {click.style(str(result['updated_count']), fg='cyan')} page(s)."
    )
    errors: list[dict[str, Any]] = result.get("errors", [])
    if errors:
        click.echo(click.style(f"{len(errors)} error(s):", fg="red"))
        for e in errors:
            click.echo(f"  {e['page_id']}: {e['error']}")


# ---------------------------------------------------------------------------
# meeting-summary
# ---------------------------------------------------------------------------

@cli.command("meeting-summary")
@click.argument("page_id")
@click.pass_context
def meeting_summary(ctx, page_id):
    """회의록에서 결정사항/액션아이템 추출"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.meeting_summarizer import MeetingSummarizerPlugin
    result = MeetingSummarizerPlugin().execute(client, cfg, page_id=page_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Meeting Summary", fg="cyan", bold=True))
    click.echo(f"\nSummary: {result.get('summary', '')}")
    click.echo(click.style("\nDecisions:", fg="yellow"))
    for d in result.get("decisions", []):
        click.echo(f"  • {d}")
    click.echo(click.style("\nAction Items:", fg="yellow"))
    for a in result.get("action_items", []):
        click.echo(f"  • {a}")
    click.echo(click.style("\nAttendees:", fg="yellow"))
    for att in result.get("attendees", []):
        click.echo(f"  • {att}")


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------

@cli.command("digest")
@click.option("--period", default="weekly", type=click.Choice(["weekly", "monthly"]))
@click.option("--create-page", is_flag=True, help="다이제스트를 새 페이지로 생성")
@click.pass_context
def digest(ctx, period, create_page):
    """주간/월간 변경사항 다이제스트 생성"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.digest_generator import DigestGeneratorPlugin
    result = DigestGeneratorPlugin().execute(client, cfg, period=period, create_page=create_page)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style(f"{period.title()} Digest", fg="cyan", bold=True))
    dr = result.get("date_range", {})
    click.echo(f"Period: {dr.get('start','')} ~ {dr.get('end','')}")
    click.echo(f"Pages changed: {result.get('pages_changed', 0)}")
    click.echo(f"\n{result.get('digest', '')}")
    if result.get("created_page_id"):
        click.echo(click.style(f"\nCreated page: {result['created_page_id']}", fg="green"))


# ---------------------------------------------------------------------------
# db-stats
# ---------------------------------------------------------------------------

@cli.command("db-stats")
@click.argument("database_id")
@click.pass_context
def db_stats(ctx, database_id):
    """데이터베이스 통계 요약"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.db_stats import DBStatsPlugin
    result = DBStatsPlugin().execute(client, cfg, database_id=database_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Database Stats", fg="cyan", bold=True))
    click.echo(f"Total items: {result.get('total_items', 0)}")
    for prop_name, stats in result.get("properties_summary", {}).items():
        click.echo(click.style(f"\n  {prop_name} ({stats.get('type','')}):", fg="yellow"))
        for k, v in stats.items():
            if k != "type":
                click.echo(f"    {k}: {v}")


# ---------------------------------------------------------------------------
# project-summary
# ---------------------------------------------------------------------------

@cli.command("project-summary")
@click.argument("database_id")
@click.pass_context
def project_summary(ctx, database_id):
    """프로젝트 DB 진행 요약"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.project_summarizer import ProjectSummarizerPlugin
    result = ProjectSummarizerPlugin().execute(client, cfg, database_id=database_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Project Summary", fg="cyan", bold=True))
    click.echo(f"Total: {result.get('total_projects', 0)} | Progress: {result.get('progress_rate', 0):.0%}")
    for status, count in result.get("by_status", {}).items():
        click.echo(f"  {status}: {count}")
    if result.get("ai_summary"):
        click.echo(f"\n{result['ai_summary']}")


# ---------------------------------------------------------------------------
# reading-notes
# ---------------------------------------------------------------------------

@cli.command("reading-notes")
@click.argument("page_id")
@click.pass_context
def reading_notes(ctx, page_id):
    """독서 노트 핵심 인사이트 추출"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.reading_notes import ReadingNotesPlugin
    result = ReadingNotesPlugin().execute(client, cfg, page_id=page_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style(f"Reading Notes: {result.get('title','')}", fg="cyan", bold=True))
    click.echo(click.style("\nKey Insights:", fg="yellow"))
    for i in result.get("key_insights", []):
        click.echo(f"  • {i}")
    click.echo(click.style("\nMain Concepts:", fg="yellow"))
    for c in result.get("main_concepts", []):
        click.echo(f"  • {c}")
    click.echo(click.style("\nQuotes:", fg="yellow"))
    for q in result.get("quotes", []):
        click.echo(f"  \"{q}\"")


# ---------------------------------------------------------------------------
# convert-bullets
# ---------------------------------------------------------------------------

@cli.command("convert-bullets")
@click.argument("page_id")
@click.option("--replace", is_flag=True, help="원본 블록을 bullet point로 교체")
@click.pass_context
def convert_bullets(ctx, page_id, replace):
    """장문 텍스트를 bullet point로 변환"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.bullet_converter import BulletConverterPlugin
    result = BulletConverterPlugin().execute(client, cfg, page_id=page_id, replace=replace)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Bullet Conversion", fg="cyan", bold=True))
    click.echo(f"Original: {result.get('original_chars', 0)} chars")
    for bp in result.get("bullet_points", []):
        click.echo(f"  • {bp}")
    if result.get("replaced"):
        click.echo(click.style("Page blocks replaced.", fg="green"))


# ---------------------------------------------------------------------------
# expand
# ---------------------------------------------------------------------------

@cli.command("expand")
@click.argument("page_id")
@click.option("--style", default="formal", type=click.Choice(["formal", "casual"]))
@click.pass_context
def expand(ctx, page_id, style):
    """짧은 메모를 구조화된 문서로 확장"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.content_expander import ContentExpanderPlugin
    result = ContentExpanderPlugin().execute(client, cfg, page_id=page_id, style=style)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Content Expansion", fg="cyan", bold=True))
    click.echo(f"Original: {result.get('original_chars', 0)} → Expanded: {result.get('expanded_chars', 0)} chars")
    if result.get("inserted"):
        click.echo(click.style("Expanded content appended to page.", fg="green"))


# ---------------------------------------------------------------------------
# translate
# ---------------------------------------------------------------------------

@cli.command("translate")
@click.argument("page_id")
@click.option("--lang", "target_lang", default="en", help="대상 언어 코드 (en, ko, ja, etc.)")
@click.option("--create-page", is_flag=True, help="번역 결과를 새 페이지로 생성")
@click.pass_context
def translate_page(ctx, page_id, target_lang, create_page):
    """페이지 콘텐츠 번역"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.translator import TranslatorPlugin
    result = TranslatorPlugin().execute(client, cfg, page_id=page_id, target_lang=target_lang, create_page=create_page)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style(f"Translation → {target_lang}", fg="cyan", bold=True))
    click.echo(f"\n{result.get('translated_content', '')[:500]}")
    if result.get("new_page_id"):
        click.echo(click.style(f"\nNew page created: {result['new_page_id']}", fg="green"))


# ---------------------------------------------------------------------------
# sentiment
# ---------------------------------------------------------------------------

@cli.command("sentiment")
@click.argument("page_id", required=False)
@click.option("--database-id", default=None, help="DB 전체 감정 분석")
@click.pass_context
def sentiment(ctx, page_id, database_id):
    """콘텐츠 감정 분석"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True)
        sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.sentiment_analyzer import SentimentAnalyzerPlugin
    kwargs = {}
    if database_id:
        kwargs["database_id"] = database_id
    elif page_id:
        kwargs["page_id"] = page_id
    else:
        click.echo(click.style("Error: page_id or --database-id required", fg="red"), err=True)
        sys.exit(1)
    result = SentimentAnalyzerPlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Sentiment Analysis", fg="cyan", bold=True))
    if "sentiment" in result:
        click.echo(f"Sentiment: {result['sentiment']} (score: {result.get('score', 0):.2f})")
        click.echo(f"Keywords: {', '.join(result.get('keywords', []))}")
    if "sentiment_distribution" in result:
        click.echo(f"Total analyzed: {result.get('total_analyzed', 0)}")
        click.echo(f"Average score: {result.get('average_score', 0):.2f}")
        for s, c in result.get("sentiment_distribution", {}).items():
            click.echo(f"  {s}: {c}")


# ---------------------------------------------------------------------------
# usage-analysis
# ---------------------------------------------------------------------------

@cli.command("usage-analysis")
@click.pass_context
def usage_analysis(ctx):
    """워크스페이스 사용 패턴 분석"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.usage_analyzer import UsageAnalyzerPlugin
    result = UsageAnalyzerPlugin().execute(client, cfg)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Usage Analysis", fg="cyan", bold=True))
    click.echo(f"Total pages: {result.get('total_pages', 0)}")
    click.echo(click.style(f"  Active (≤7d): {result.get('active', 0)}", fg="green"))
    click.echo(click.style(f"  Stale (≤30d): {result.get('stale', 0)}", fg="yellow"))
    click.echo(click.style(f"  Abandoned (>30d): {result.get('abandoned', 0)}", fg="red"))
    if result.get("most_active"):
        click.echo(click.style("\nMost Active:", fg="yellow"))
        for p in result["most_active"][:5]:
            click.echo(f"  • {p.get('title', '')} ({p.get('last_edited', '')})")


# ---------------------------------------------------------------------------
# keywords
# ---------------------------------------------------------------------------

@cli.command("keywords")
@click.option("--database-id", default=None, help="특정 DB 분석")
@click.option("--top-k", default=20, type=int, help="상위 키워드 수")
@click.pass_context
def keywords(ctx, database_id, top_k):
    """키워드 빈도 분석"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.keyword_analyzer import KeywordAnalyzerPlugin
    kwargs = {"top_k": top_k}
    if database_id:
        kwargs["database_id"] = database_id
    result = KeywordAnalyzerPlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Keyword Analysis", fg="cyan", bold=True))
    click.echo(f"Pages: {result.get('pages_analyzed', 0)} | Words: {result.get('total_words', 0)} | Unique: {result.get('unique_words', 0)}")
    click.echo(click.style("\nTop Keywords:", fg="yellow"))
    for kw in result.get("top_keywords", []):
        click.echo(f"  {kw['word']}: {kw['count']}")


# ---------------------------------------------------------------------------
# content-graph
# ---------------------------------------------------------------------------

@cli.command("content-graph")
@click.pass_context
def content_graph(ctx):
    """콘텐츠 연결 그래프 분석"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.content_graph import ContentGraphPlugin
    result = ContentGraphPlugin().execute(client, cfg)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Content Graph", fg="cyan", bold=True))
    click.echo(f"Nodes: {result.get('total_nodes', 0)} | Edges: {result.get('total_edges', 0)}")
    if result.get("most_connected"):
        click.echo(click.style("\nMost Connected:", fg="yellow"))
        for n in result["most_connected"][:5]:
            click.echo(f"  • {n.get('title', '')} ({n.get('connections', 0)} connections)")
    if result.get("isolated"):
        click.echo(click.style(f"\nIsolated pages: {len(result['isolated'])}", fg="red"))


# ---------------------------------------------------------------------------
# writing-habits
# ---------------------------------------------------------------------------

@cli.command("writing-habits")
@click.pass_context
def writing_habits(ctx):
    """작성 습관 분석"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.writing_habit_analyzer import WritingHabitAnalyzerPlugin
    result = WritingHabitAnalyzerPlugin().execute(client, cfg)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style("Writing Habits", fg="cyan", bold=True))
    click.echo(f"Total pages: {result.get('total_pages', 0)}")
    click.echo(f"Most productive hour: {result.get('most_productive_hour', 'N/A')}:00")
    click.echo(f"Most productive day: {result.get('most_productive_day', 'N/A')}")
    click.echo(click.style("\nBy Weekday:", fg="yellow"))
    for day, count in result.get("by_weekday", {}).items():
        click.echo(f"  {day}: {'█' * count} ({count})")


# ---------------------------------------------------------------------------
# db-health
# ---------------------------------------------------------------------------

@cli.command("db-health")
@click.argument("database_id")
@click.pass_context
def db_health(ctx, database_id):
    """데이터베이스 헬스체크"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.db_health_checker import DBHealthCheckerPlugin
    result = DBHealthCheckerPlugin().execute(client, cfg, database_id=database_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    score = result.get("health_score", 0)
    color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
    click.echo(click.style(f"DB Health Score: {score:.0%}", fg=color, bold=True))
    click.echo(f"Total items: {result.get('total_items', 0)}")
    issues = result.get("issues", {})
    if issues.get("unused_properties"):
        click.echo(click.style(f"\nUnused properties: {len(issues['unused_properties'])}", fg="yellow"))
        for p in issues["unused_properties"]:
            click.echo(f"  • {p}")
    if issues.get("empty_properties"):
        click.echo(click.style(f"\nEmpty property entries: {len(issues['empty_properties'])}", fg="yellow"))
    if issues.get("inconsistent_values"):
        click.echo(click.style(f"\nInconsistent values: {len(issues['inconsistent_values'])}", fg="red"))
        for iv in issues["inconsistent_values"][:5]:
            click.echo(f"  • {iv}")


# ---------------------------------------------------------------------------
# goals
# ---------------------------------------------------------------------------

@cli.command("goals")
@click.argument("database_id")
@click.option("--progress-property", default="Progress", help="진행률 속성명")
@click.option("--target-property", default="Target", help="목표 속성명")
@click.pass_context
def goals(ctx, database_id, progress_property, target_property):
    """목표 달성도 추적"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.goal_tracker import GoalTrackerPlugin
    result = GoalTrackerPlugin().execute(
        client, cfg, database_id=database_id,
        progress_property=progress_property, target_property=target_property
    )
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True)
        sys.exit(1)
    rate = result.get("achievement_rate", 0)
    color = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
    click.echo(click.style(f"Goal Achievement: {rate:.0%}", fg=color, bold=True))
    click.echo(f"Total: {result.get('total_goals', 0)} | Completed: {result.get('completed', 0)} | In Progress: {result.get('in_progress', 0)}")
    for g in result.get("goals", []):
        click.echo(f"  • {g.get('title', '')}: {g.get('rate', 0):.0%}")
    if result.get("ai_insights"):
        click.echo(click.style(f"\nInsights:\n{result['ai_insights']}", fg="cyan"))


@cli.command("generate-template")
@click.option("--database-id", default=None)
@click.option("--page-ids", default=None, help="Comma-separated page IDs")
@click.pass_context
def generate_template(ctx, database_id, page_ids):
    """페이지 패턴 분석 기반 템플릿 생성"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.template_generator import TemplateGeneratorPlugin
    kwargs = {}
    if database_id: kwargs["database_id"] = database_id
    if page_ids: kwargs["page_ids"] = [p.strip() for p in page_ids.split(",")]
    result = TemplateGeneratorPlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style("Template Analysis", fg="cyan", bold=True))
    click.echo(f"Pages analyzed: {result.get('analyzed_pages', 0)}")
    click.echo(click.style("\nCommon Structure:", fg="yellow"))
    for s in result.get("common_structure", []):
        click.echo(f"  • {s.get('block_type','')}: {s.get('frequency',0)}")
    if result.get("template_suggestion"):
        click.echo(click.style("\nSuggested Template:", fg="green"))
        click.echo(result["template_suggestion"])


@cli.command("journal")
@click.argument("parent_page_id")
@click.pass_context
def journal(ctx, parent_page_id):
    """일간 저널 페이지 생성"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.daily_journal import DailyJournalPlugin
    result = DailyJournalPlugin().execute(client, cfg, parent_page_id=parent_page_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style(f"Journal created: {result.get('date','')}", fg="green"))
    click.echo(f"Page ID: {result.get('created_page_id','')}")


@cli.command("meeting-template")
@click.argument("parent_page_id")
@click.option("--title", required=True, help="회의 제목")
@click.option("--attendees", default=None, help="참석자 (comma-separated)")
@click.option("--agenda", default=None, help="안건 (comma-separated)")
@click.pass_context
def meeting_template_cmd(ctx, parent_page_id, title, attendees, agenda):
    """회의록 템플릿 생성"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.meeting_template import MeetingTemplatePlugin
    kwargs = {"parent_page_id": parent_page_id, "title": title}
    if attendees: kwargs["attendees"] = [a.strip() for a in attendees.split(",")]
    if agenda: kwargs["agenda"] = [a.strip() for a in agenda.split(",")]
    result = MeetingTemplatePlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style(f"Meeting template created: {result.get('title','')}", fg="green"))
    click.echo(f"Page ID: {result.get('created_page_id','')}")


@cli.command("weekly-review")
@click.option("--parent-page-id", default=None)
@click.option("--create-page", is_flag=True)
@click.pass_context
def weekly_review_cmd(ctx, parent_page_id, create_page):
    """주간 리뷰 초안 작성"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.weekly_review import WeeklyReviewPlugin
    result = WeeklyReviewPlugin().execute(client, cfg, parent_page_id=parent_page_id, create_page=create_page)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style(f"Weekly Review: {result.get('week','')}", fg="cyan", bold=True))
    click.echo(f"Pages edited: {result.get('pages_edited', 0)}")
    click.echo(f"\n{result.get('review_content', '')}")
    if result.get("created_page_id"):
        click.echo(click.style(f"\nPage: {result['created_page_id']}", fg="green"))


@cli.command("generate-faq")
@click.argument("page_id", required=False)
@click.option("--database-id", default=None)
@click.option("--create-page", is_flag=True)
@click.option("--parent-page-id", default=None)
@click.pass_context
def generate_faq(ctx, page_id, database_id, create_page, parent_page_id):
    """문서 기반 FAQ 자동 생성"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True); sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.faq_generator import FAQGeneratorPlugin
    kwargs = {"create_page": create_page}
    if page_id: kwargs["page_id"] = page_id
    if database_id: kwargs["database_id"] = database_id
    if parent_page_id: kwargs["parent_page_id"] = parent_page_id
    result = FAQGeneratorPlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style("Generated FAQ", fg="cyan", bold=True))
    for faq in result.get("faqs", []):
        click.echo(click.style(f"\nQ: {faq['question']}", fg="yellow"))
        click.echo(f"A: {faq['answer']}")


@cli.command("release-notes")
@click.argument("database_id")
@click.option("--version", default=None)
@click.option("--create-page", is_flag=True)
@click.option("--parent-page-id", default=None)
@click.pass_context
def release_notes_cmd(ctx, database_id, version, create_page, parent_page_id):
    """변경 로그 기반 릴리즈 노트 생성"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.release_notes import ReleaseNotesPlugin
    result = ReleaseNotesPlugin().execute(client, cfg, database_id=database_id, version=version, create_page=create_page, parent_page_id=parent_page_id)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style(f"Release Notes {result.get('version','')}", fg="cyan", bold=True))
    click.echo(f"Changes: {result.get('changes', 0)}")
    click.echo(f"\n{result.get('release_notes', '')}")


@cli.command("semantic-search")
@click.argument("query")
@click.option("--top-k", default=5, type=int)
@click.pass_context
def semantic_search_cmd(ctx, query, top_k):
    """임베딩 기반 시맨틱 검색"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.semantic_search import SemanticSearchPlugin
    result = SemanticSearchPlugin().execute(client, cfg, query=query, top_k=top_k)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style(f"Semantic Search: \"{query}\"", fg="cyan", bold=True))
    for r in result.get("results", []):
        click.echo(f"\n  [{r.get('relevance',0):.2f}] {r.get('title','')}")
        click.echo(f"    {r.get('snippet','')[:100]}")


@cli.command("cross-qa")
@click.argument("question")
@click.option("--pages", default=None, help="Comma-separated page IDs")
@click.pass_context
def cross_qa(ctx, question, pages):
    """멀티소스 Q&A"""
    cfg, client = _setup(ctx)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        click.echo(click.style("Error: ANTHROPIC_API_KEY not set", fg="red"), err=True); sys.exit(1)
    cfg.setdefault("ai", {})["api_key"] = api_key
    from notion_manager.plugins.cross_page_qa import CrossPageQAPlugin
    kwargs = {"question": question}
    if pages: kwargs["page_ids"] = [p.strip() for p in pages.split(",")]
    result = CrossPageQAPlugin().execute(client, cfg, **kwargs)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style("Answer", fg="cyan", bold=True))
    click.echo(f"\n{result.get('answer', '')}")
    click.echo(click.style(f"\nConfidence: {result.get('confidence',0):.0%}", fg="yellow"))
    click.echo(click.style("\nSources:", fg="yellow"))
    for s in result.get("sources", []):
        click.echo(f"  • {s.get('title','')} ({s.get('relevance',0):.2f})")


@cli.command("recommend")
@click.argument("page_id")
@click.option("--top-k", default=5, type=int)
@click.pass_context
def recommend(ctx, page_id, top_k):
    """관련 페이지 추천"""
    cfg, client = _setup(ctx)
    from notion_manager.plugins.page_recommender import PageRecommenderPlugin
    result = PageRecommenderPlugin().execute(client, cfg, page_id=page_id, top_k=top_k)
    if "error" in result:
        click.echo(click.style(f"Error: {result['error']}", fg="red"), err=True); sys.exit(1)
    click.echo(click.style("Recommendations", fg="cyan", bold=True))
    for r in result.get("recommendations", []):
        click.echo(f"  [{r.get('relevance',0):.2f}] {r.get('title','')}")
