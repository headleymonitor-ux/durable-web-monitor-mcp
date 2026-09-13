import unittest
from unittest.mock import patch

from durable_web_monitor.security import UnsafeTarget, validate_public_https_url


class SecurityTests(unittest.TestCase):
    def test_rejects_http(self):
        with self.assertRaises(UnsafeTarget):
            validate_public_https_url("http://example.com")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(UnsafeTarget):
            validate_public_https_url("https://user:pass@example.com/")

    def test_rejects_private_resolution(self):
        with patch("socket.getaddrinfo") as mocked:
            mocked.return_value = [(2, 1, 6, "", ("127.0.0.1", 443))]
            with self.assertRaises(UnsafeTarget):
                validate_public_https_url("https://example.com/")

    def test_accepts_public_resolution(self):
        with patch("socket.getaddrinfo") as mocked:
            mocked.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
            self.assertEqual(
                validate_public_https_url("https://example.com/path"),
                "example.com",
            )


if __name__ == "__main__":
    unittest.main()
