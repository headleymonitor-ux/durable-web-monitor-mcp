import unittest

from durable_web_monitor.normalize import html_to_text, normalize_text


class NormalizeTests(unittest.TestCase):
    def test_whitespace_is_stable(self):
        self.assertEqual(normalize_text(" a   b \n\n\n c "), "a b\n\nc")

    def test_html_ignores_script_and_style(self):
        doc = """
        <html><head><style>hidden css</style><script>hidden js</script></head>
        <body><h1>Hello</h1><p>World &amp; friends</p></body></html>
        """
        text = html_to_text(doc)
        self.assertIn("Hello", text)
        self.assertIn("World & friends", text)
        self.assertNotIn("hidden css", text)
        self.assertNotIn("hidden js", text)


if __name__ == "__main__":
    unittest.main()
