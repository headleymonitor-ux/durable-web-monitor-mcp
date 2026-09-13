"""Direct HTTPS and isolated Playwright MCP fetch adapters."""

from __future__ import annotations

from dataclasses import dataclass
import contextlib
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .normalize import html_to_text, normalize_browser_snapshot, normalize_text
from .security import validate_public_https_url

Adapter = Literal["direct", "browser"]

_MAX_BYTES = 2_000_000
_MAX_REDIRECTS = 5
_USER_AGENT = "durable-web-monitor-mcp/0.1 (+https://github.com/headleymonitor-ux/durable-web-monitor-mcp)"
_PLAYWRIGHT_MCP_PACKAGE = "@playwright/mcp@0.0.80"
_PLAYWRIGHT_BROWSER = "chromium"
_PLAYWRIGHT_BROWSER_INSTALL = "npx -y playwright@1.63.0-alpha-2026-08-31 install chromium"


@dataclass(frozen=True)
class FetchResult:
    url: str
    text: str
    adapter: Adapter


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_direct(url: str, *, timeout: float = 20.0) -> FetchResult:
    """Fetch a public HTTPS page, revalidating every redirect."""
    current = url
    opener = build_opener(_NoRedirect)

    for _ in range(_MAX_REDIRECTS + 1):
        validate_public_https_url(current)
        request = Request(
            current,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
            },
        )
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise RuntimeError(f"redirect {exc.code} had no Location header") from exc
                current = urljoin(current, location)
                continue
            raise RuntimeError(f"HTTP {exc.code} fetching {current}") from exc
        except URLError as exc:
            raise RuntimeError(f"network error fetching {current}: {exc.reason}") from exc

        with response:
            final_url = response.geturl()
            validate_public_https_url(final_url)
            content_type = (response.headers.get_content_type() or "").lower()
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                raise RuntimeError(f"response exceeded {_MAX_BYTES} bytes")
            text = raw.decode(charset, errors="replace")

        if content_type in {"text/html", "application/xhtml+xml"}:
            text = html_to_text(text)
        else:
            text = normalize_text(text)
        return FetchResult(url=final_url, text=text, adapter="direct")

    raise RuntimeError(f"too many redirects (>{_MAX_REDIRECTS})")


async def fetch_browser(url: str, *, target: str = "body", depth: int = 10) -> FetchResult:
    """Fetch a page through a fresh isolated Playwright MCP subprocess."""
    validate_public_https_url(url)

    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            _PLAYWRIGHT_MCP_PACKAGE,
            "--headless",
            "--isolated",
            "--browser",
            _PLAYWRIGHT_BROWSER,
            "--image-responses=omit",
        ],
    )

    # The high-level v2 Client owns the subprocess lifecycle. Exiting this
    # context terminates the Playwright MCP process tree.
    async with Client(params) as client:
        nav = await client.call_tool("browser_navigate", {"url": url})
        if nav.is_error:
            raise RuntimeError(
                "Playwright MCP browser_navigate failed. Ensure Chromium is installed for "
                f"the pinned Playwright build, for example: {_PLAYWRIGHT_BROWSER_INSTALL}"
            )
        try:
            snap = await client.call_tool(
                "browser_snapshot",
                {"target": target, "depth": max(1, min(int(depth), 20)), "boxes": False},
            )
            if snap.is_error:
                raise RuntimeError("Playwright MCP browser_snapshot failed")
            chunks = []
            for block in snap.content:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    chunks.append(text)
            snapshot = normalize_browser_snapshot("\n".join(chunks))
            if not snapshot:
                raise RuntimeError("Playwright MCP returned an empty text snapshot")
            return FetchResult(url=url, text=snapshot, adapter="browser")
        finally:
            with contextlib.suppress(Exception):
                await client.call_tool("browser_close", {})
