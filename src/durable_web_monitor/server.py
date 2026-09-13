"""MCP server surface for durable web monitoring."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server import MCPServer

from durable_web_monitor.monitor import check_url as run_check
from durable_web_monitor.store import Store

mcp = MCPServer(
    "durable-web-monitor-mcp",
    instructions=(
        "Use check_url to establish or compare a monitor baseline. "
        "Read notifications before acknowledging them. "
        "Only call mark_notifications_reviewed after the notifications were successfully handled."
    ),
)


def _store() -> Store:
    path = os.environ.get(
        "DWM_STATE_PATH",
        str(Path("~/.local/share/durable-web-monitor-mcp/state.sqlite3").expanduser()),
    )
    return Store(path)


@mcp.tool()
async def check_url(
    name: str,
    url: str,
    adapter: str = "direct",
    target: str = "body",
    watch_terms: list[str] | None = None,
) -> dict:
    """Fetch one public HTTPS page and update its durable baseline."""
    return await run_check(
        store=_store(),
        name=name,
        url=url,
        adapter=adapter,  # validated by engine
        target=target,
        watch_terms=watch_terms,
    )


@mcp.tool()
def list_notifications(status: str = "new", limit: int = 50) -> dict:
    """List durable notifications without advancing the review cursor."""
    return _store().list_notifications(status=status, limit=limit)


@mcp.tool()
def mark_notifications_reviewed(through_seq: int) -> dict:
    """Advance the durable notification cursor after successful handling."""
    return _store().mark_reviewed(through_seq)


@mcp.tool()
def monitor_status() -> dict:
    """Return bounded durable inbox state and storage location."""
    store = _store()
    return {
        **store.review_state(),
        "database": str(store.path),
    }
