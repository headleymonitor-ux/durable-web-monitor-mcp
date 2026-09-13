import tempfile
import unittest
from pathlib import Path

from durable_web_monitor.store import Store


class StoreTests(unittest.TestCase):
    def test_notification_cursor_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            seq = store.add_notification(
                monitor_name="docs",
                url="https://example.com/docs",
                old_hash="a",
                new_hash="b",
                excerpt="changed",
                matching_terms=[],
            )

            unread = store.list_notifications(status="new")
            self.assertEqual([item["seq"] for item in unread["items"]], [seq])
            self.assertEqual(unread["reviewed_through_seq"], 0)

            state = store.mark_reviewed(seq)
            self.assertEqual(state["reviewed_through_seq"], seq)
            self.assertEqual(store.list_notifications(status="new")["items"], [])

    def test_monitor_upsert_preserves_initialized_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            store.save_monitor(
                name="docs",
                url="https://example.com",
                adapter="direct",
                target="body",
                watch_terms=[],
                digest="one",
                excerpt="one",
            )
            first = store.get_monitor("docs")
            store.save_monitor(
                name="docs",
                url="https://example.com",
                adapter="direct",
                target="body",
                watch_terms=[],
                digest="two",
                excerpt="two",
                initialized_at=first["initialized_at"],
            )
            second = store.get_monitor("docs")
            self.assertEqual(first["initialized_at"], second["initialized_at"])
            self.assertEqual(second["last_hash"], "two")


if __name__ == "__main__":
    unittest.main()
