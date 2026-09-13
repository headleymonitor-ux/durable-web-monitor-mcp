"""Stable text normalization before hashing."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_HORIZONTAL = re.compile(r"[ \t\f\v]+")
_BLANKS = re.compile(r"\n{3,}")


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "template"}:
            self._hidden_depth += 1
        elif not self._hidden_depth and tag.lower() in {
            "p", "div", "br", "li", "section", "article", "header", "footer",
            "main", "nav", "h1", "h2", "h3", "h4", "h5", "h6", "tr"
        }:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "template"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif not self._hidden_depth and tag.lower() in {
            "p", "div", "li", "section", "article", "header", "footer",
            "main", "nav", "h1", "h2", "h3", "h4", "h5", "h6", "tr"
        }:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def normalize_text(text: str) -> str:
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _HORIZONTAL.sub(" ", raw).strip()
        lines.append(line)
    normalized = "\n".join(lines)
    normalized = _BLANKS.sub("\n\n", normalized)
    return normalized.strip()


def html_to_text(document: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(document)
    parser.close()
    return normalize_text(html.unescape(parser.text()))
