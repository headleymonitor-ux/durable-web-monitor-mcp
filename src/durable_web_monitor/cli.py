"""Small CLI for schedulers and manual checks."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .monitor import check_url
from .store import Store


def _store(path: str | None) -> Store:
    resolved = path or os.environ.get(
        "DWM_STATE_PATH",
        str(Path("~/.local/share/durable-web-monitor-mcp/state.sqlite3").expanduser()),
    )
    return Store(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(prog="dwm")
    parser.add_argument("--state-path")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--name", required=True)
    check.add_argument("--url", required=True)
    check.add_argument("--adapter", choices=("direct", "browser"), default="direct")
    check.add_argument("--target", default="body")
    check.add_argument("--watch-term", action="append", default=[])

    inbox = sub.add_parser("inbox")
    inbox.add_argument("--status", choices=("new", "all"), default="new")
    inbox.add_argument("--limit", type=int, default=50)

    ack = sub.add_parser("ack")
    ack.add_argument("--through-seq", type=int, required=True)

    args = parser.parse_args()
    store = _store(args.state_path)

    if args.command == "check":
        result = asyncio.run(
            check_url(
                store=store,
                name=args.name,
                url=args.url,
                adapter=args.adapter,
                target=args.target,
                watch_terms=args.watch_term,
            )
        )
    elif args.command == "inbox":
        result = store.list_notifications(status=args.status, limit=args.limit)
    else:
        result = store.mark_reviewed(args.through_seq)

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
