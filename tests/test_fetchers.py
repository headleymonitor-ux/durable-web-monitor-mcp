import os
import unittest
from unittest.mock import patch

from durable_web_monitor.fetchers import _playwright_mcp_args


class PlaywrightArgsTests(unittest.TestCase):
    def test_default_args_use_pinned_isolated_sandboxed_chromium(self):
        with patch.dict(os.environ, {}, clear=True):
            args = _playwright_mcp_args()
        self.assertEqual(args[0:2], ["-y", "@playwright/mcp@0.0.80"])
        self.assertIn("--headless", args)
        self.assertIn("--sandbox", args)
        self.assertIn("--isolated", args)
        self.assertEqual(args[args.index("--browser") + 1], "chromium")
        self.assertEqual(args[args.index("--image-responses") + 1], "omit")
        self.assertEqual(args[args.index("--codegen") + 1], "none")
        self.assertNotIn("--executable-path", args)

    def test_environment_can_supply_system_chromium_path(self):
        with patch.dict(os.environ, {"DWM_BROWSER_EXECUTABLE_PATH": "/usr/bin/chromium"}, clear=True):
            args = _playwright_mcp_args()
        self.assertEqual(args[args.index("--executable-path") + 1], "/usr/bin/chromium")

    def test_explicit_path_overrides_environment(self):
        with patch.dict(os.environ, {"DWM_BROWSER_EXECUTABLE_PATH": "/env/chromium"}, clear=True):
            args = _playwright_mcp_args("/explicit/chromium")
        self.assertEqual(args[args.index("--executable-path") + 1], "/explicit/chromium")


if __name__ == "__main__":
    unittest.main()
