import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from durable_web_monitor.fetchers import FetchResult
from durable_web_monitor.monitor import check_url
from durable_web_monitor.store import Store


class MonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_check_is_quiet_then_change_notifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            first = FetchResult("https://example.com/", "one", "direct")
            second = FetchResult("https://example.com/", "two", "direct")

            with patch("durable_web_monitor.monitor.fetch_direct", return_value=first):
                result = await check_url(
                    store=store,
                    name="example",
                    url="https://example.com/",
                )
            self.assertEqual(result["status"], "baseline_created")
            self.assertEqual(store.list_notifications(status="new")["items"], [])

            with patch("durable_web_monitor.monitor.fetch_direct", return_value=second):
                result = await check_url(
                    store=store,
                    name="example",
                    url="https://example.com/",
                )
            self.assertEqual(result["status"], "changed")
            self.assertEqual(len(store.list_notifications(status="new")["items"]), 1)

    async def test_watch_terms_can_filter_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            with patch(
                "durable_web_monitor.monitor.fetch_direct",
                return_value=FetchResult("https://example.com/", "healthy", "direct"),
            ):
                await check_url(
                    store=store,
                    name="status",
                    url="https://example.com/",
                    watch_terms=["incident"],
                )

            with patch(
                "durable_web_monitor.monitor.fetch_direct",
                return_value=FetchResult("https://example.com/", "still healthy", "direct"),
            ):
                result = await check_url(
                    store=store,
                    name="status",
                    url="https://example.com/",
                    watch_terms=["incident"],
                )
            self.assertEqual(result["status"], "changed_filtered")
            self.assertEqual(store.list_notifications(status="new")["items"], [])


if __name__ == "__main__":
    unittest.main()
