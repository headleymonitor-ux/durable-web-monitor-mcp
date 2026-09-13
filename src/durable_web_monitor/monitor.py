"""Monitoring engine: fetch, normalize/hash, baseline, notify."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from .fetchers import fetch_browser, fetch_direct
from .store import Store

Adapter = Literal["direct", "browser"]


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _excerpt(text: str, limit: int = 2000) -> str:
    return text[:limit]


async def check_url(
    *,
    store: Store,
    name: str,
    url: str,
    adapter: Adapter = "direct",
    target: str = "body",
    watch_terms: list[str] | None = None,
) -> dict:
    if not name.strip():
        raise ValueError("name must not be empty")
    terms = [term.strip() for term in (watch_terms or []) if term.strip()]

    if adapter == "direct":
        fetched = fetch_direct(url)
    elif adapter == "browser":
        fetched = await fetch_browser(url, target=target)
    else:
        raise ValueError("adapter must be 'direct' or 'browser'")

    digest = digest_text(fetched.text)
    excerpt = _excerpt(fetched.text)
    previous = store.get_monitor(name)

    if previous is None:
        store.save_monitor(
            name=name,
            url=fetched.url,
            adapter=adapter,
            target=target,
            watch_terms=terms,
            digest=digest,
            excerpt=excerpt,
        )
        return {
            "status": "baseline_created",
            "name": name,
            "url": fetched.url,
            "adapter": adapter,
            "hash": digest,
            "notification_seq": None,
        }

    if previous["last_hash"] == digest:
        store.save_monitor(
            name=name,
            url=fetched.url,
            adapter=adapter,
            target=target,
            watch_terms=terms,
            digest=digest,
            excerpt=excerpt,
            initialized_at=previous["initialized_at"],
        )
        return {
            "status": "unchanged",
            "name": name,
            "url": fetched.url,
            "adapter": adapter,
            "hash": digest,
            "notification_seq": None,
        }

    lowered = fetched.text.casefold()
    matching = [term for term in terms if term.casefold() in lowered]
    should_notify = not terms or bool(matching)
    seq = None
    if should_notify:
        seq = store.add_notification(
            monitor_name=name,
            url=fetched.url,
            old_hash=previous["last_hash"],
            new_hash=digest,
            excerpt=excerpt,
            matching_terms=matching,
        )

    store.save_monitor(
        name=name,
        url=fetched.url,
        adapter=adapter,
        target=target,
        watch_terms=terms,
        digest=digest,
        excerpt=excerpt,
        initialized_at=previous["initialized_at"],
    )
    return {
        "status": "changed" if should_notify else "changed_filtered",
        "name": name,
        "url": fetched.url,
        "adapter": adapter,
        "old_hash": previous["last_hash"],
        "hash": digest,
        "matching_terms": matching,
        "notification_seq": seq,
    }
