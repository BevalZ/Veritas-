"""HTML rendering utility helpers."""

import json


def _html_escape(text):
    """Escape text for HTML fragments while preserving legacy newline rendering."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br>")
    )


def _json_for_script_tag(value):
    """JSON that remains parseable inside a <script type="application/json"> block."""
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


__all__ = ["_html_escape", "_json_for_script_tag"]
