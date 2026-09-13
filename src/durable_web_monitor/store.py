"""SQLite-backed durable baseline and notification storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Notification:
    seq: int
    monitor_name: str
    url: str
    created_at: str
    old_hash: str
    new_hash: str
    excerpt: str
    matching_terms: list[str]


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _init(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS monitor_state (
                    name TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    adapter TEXT NOT NULL,
                    target TEXT NOT NULL,
                    watch_terms_json TEXT NOT NULL,
                    last_hash TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    initialized_at TEXT NOT NULL,
                    last_checked_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    monitor_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    old_hash TEXT NOT NULL,
                    new_hash TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    matching_terms_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            con.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES ('reviewed_through_seq', '0')"
            )
            con.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES ('last_reviewed_at', '')"
            )

    def get_monitor(self, name: str) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM monitor_state WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def save_monitor(
        self,
        *,
        name: str,
        url: str,
        adapter: str,
        target: str,
        watch_terms: list[str],
        digest: str,
        excerpt: str,
        initialized_at: str | None = None,
    ) -> None:
        now = utc_now()
        with self._connect() as con:
            existing = con.execute(
                "SELECT initialized_at FROM monitor_state WHERE name=?", (name,)
            ).fetchone()
            init = initialized_at or (existing["initialized_at"] if existing else now)
            con.execute(
                """
                INSERT INTO monitor_state(
                    name,url,adapter,target,watch_terms_json,last_hash,excerpt,
                    initialized_at,last_checked_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                    url=excluded.url,
                    adapter=excluded.adapter,
                    target=excluded.target,
                    watch_terms_json=excluded.watch_terms_json,
                    last_hash=excluded.last_hash,
                    excerpt=excluded.excerpt,
                    last_checked_at=excluded.last_checked_at
                """,
                (
                    name,
                    url,
                    adapter,
                    target,
                    json.dumps(watch_terms),
                    digest,
                    excerpt,
                    init,
                    now,
                ),
            )

    def add_notification(
        self,
        *,
        monitor_name: str,
        url: str,
        old_hash: str,
        new_hash: str,
        excerpt: str,
        matching_terms: list[str],
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO notifications(
                    monitor_name,url,created_at,old_hash,new_hash,excerpt,matching_terms_json
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    monitor_name,
                    url,
                    utc_now(),
                    old_hash,
                    new_hash,
                    excerpt,
                    json.dumps(matching_terms),
                ),
            )
            return int(cur.lastrowid)

    def review_state(self) -> dict:
        with self._connect() as con:
            rows = dict(con.execute("SELECT key,value FROM metadata").fetchall())
            high = con.execute("SELECT COALESCE(MAX(seq),0) FROM notifications").fetchone()[0]
        return {
            "reviewed_through_seq": int(rows.get("reviewed_through_seq", "0")),
            "last_reviewed_at": rows.get("last_reviewed_at", ""),
            "high_water_seq": int(high),
        }

    def list_notifications(self, *, status: str = "new", limit: int = 50) -> dict:
        state = self.review_state()
        limit = max(1, min(int(limit), 100))
        with self._connect() as con:
            if status == "new":
                rows = con.execute(
                    "SELECT * FROM notifications WHERE seq>? ORDER BY seq ASC LIMIT ?",
                    (state["reviewed_through_seq"], limit),
                ).fetchall()
            elif status == "all":
                rows = con.execute(
                    "SELECT * FROM notifications ORDER BY seq DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                raise ValueError("status must be 'new' or 'all'")

        items = []
        for row in rows:
            items.append(
                asdict(
                    Notification(
                        seq=row["seq"],
                        monitor_name=row["monitor_name"],
                        url=row["url"],
                        created_at=row["created_at"],
                        old_hash=row["old_hash"],
                        new_hash=row["new_hash"],
                        excerpt=row["excerpt"],
                        matching_terms=json.loads(row["matching_terms_json"]),
                    )
                )
            )
        return {**state, "items": items}

    def mark_reviewed(self, through_seq: int) -> dict:
        state = self.review_state()
        through_seq = int(through_seq)
        if through_seq < 0:
            raise ValueError("through_seq must be >= 0")
        if through_seq > state["high_water_seq"]:
            raise ValueError("through_seq cannot exceed high_water_seq")
        if through_seq < state["reviewed_through_seq"]:
            raise ValueError("through_seq cannot move the review cursor backwards")

        now = utc_now()
        with self._connect() as con:
            con.execute(
                "UPDATE metadata SET value=? WHERE key='reviewed_through_seq'",
                (str(through_seq),),
            )
            con.execute(
                "UPDATE metadata SET value=? WHERE key='last_reviewed_at'",
                (now,),
            )
        return self.review_state()
