"""Text normalization helpers."""

from __future__ import annotations

import html
import re

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def decode_entities_and_strip_html(value: str) -> str:
    """Decode HTML entities and strip HTML tags into plain text."""
    if not value:
        return ""

    decoded = value
    for _ in range(2):
        next_value = html.unescape(decoded)
        if next_value == decoded:
            break
        decoded = next_value

    no_tags = _HTML_TAG_PATTERN.sub(" ", decoded)
    return _WHITESPACE_PATTERN.sub(" ", no_tags).strip()
