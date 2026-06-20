"""MinerU structured content-list text formatting helpers."""

import html
import json
import re
from pathlib import Path

from .evidence_rendering import _parse_html_table_rows

__all__ = [
    "_extract_mineru_structured_text",
    "_format_mineru_content_list",
    "_flatten_mineru_items",
    "_mineru_block_type",
    "_mineru_block_text",
    "_mineru_content_text",
    "_format_mineru_table_block",
    "_normalize_mineru_table_text",
    "_table_rows_to_markdown",
    "_normalize_markdown_table",
]


def _extract_mineru_structured_text(zf):
    """Build audit-oriented text from MinerU content_list JSON when available."""
    names = zf.namelist()
    candidates = sorted(
        [n for n in names if n.endswith("_content_list_v2.json")],
        key=lambda n: zf.getinfo(n).file_size,
        reverse=True,
    )
    candidates.extend(sorted(
        [n for n in names if n.endswith("_content_list.json")],
        key=lambda n: zf.getinfo(n).file_size,
        reverse=True,
    ))
    for name in candidates:
        try:
            data = json.loads(zf.read(name).decode("utf-8", errors="replace"))
            text = _format_mineru_content_list(data)
            if text and len(text.strip()) > 200:
                print(f"  🧱 使用MinerU结构化内容: {Path(name).name}")
                return text
        except Exception as e:
            print(f"  ⚠️ MinerU结构化内容解析失败 {name}: {e}")
    return None


def _format_mineru_content_list(data):
    """Convert MinerU content_list entries to stable text blocks for audit."""
    if isinstance(data, dict):
        for key in ("content", "content_list", "list", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return None

    parts = [
        "[[EXTRACTION_NOTE]] MinerU structured extraction is used. Table layout/OCR artifacts are extraction noise; do not treat formatting defects alone as academic misconduct. [[/EXTRACTION_NOTE]]"
    ]
    table_idx = 0
    figure_idx = 0
    for item in _flatten_mineru_items(data):
        if not isinstance(item, dict):
            continue
        block_type = _mineru_block_type(item)
        page = item.get("page_idx", item.get("page", item.get("page_no", "?")))
        text = _mineru_block_text(item).strip()
        if not text:
            continue
        if block_type == "table":
            table_idx += 1
            parts.append(_format_mineru_table_block(text, page, table_idx))
        elif block_type in {"image", "figure"}:
            figure_idx += 1
            parts.append(f"[[FIGURE page={page} id={figure_idx}]]\n{text}\n[[/FIGURE]]")
        else:
            parts.append(f"[[BLOCK type={block_type} page={page}]]\n{text}\n[[/BLOCK]]")
    return "\n\n".join(parts)


def _flatten_mineru_items(data):
    """Yield MinerU layout items from flat or page-nested content lists."""
    if isinstance(data, dict):
        yield data
        return
    if isinstance(data, list):
        for item in data:
            yield from _flatten_mineru_items(item)


def _mineru_block_type(item):
    raw = str(item.get("type") or item.get("category") or item.get("block_type") or "").lower()
    content = item.get("content")
    if "table" in raw:
        return "table"
    if raw in {"image", "figure", "chart"} or "image" in raw or "figure" in raw or "chart" in raw:
        return "figure"
    if "title" in raw:
        return "title"
    if "equation" in raw or "formula" in raw:
        return "formula"
    if raw == "list" and isinstance(content, dict) and content.get("list_type") == "reference_list":
        return "reference_list"
    return raw or "text"


def _mineru_block_text(item):
    for key in ("text", "md", "content", "html", "table_body", "latex", "caption"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            extracted = _mineru_content_text(value)
            if extracted:
                return extracted
    texts = []
    for key in ("table_caption", "table_footnote", "image_caption", "img_caption", "chart_caption", "chart_footnote"):
        value = item.get(key)
        if isinstance(value, list):
            texts.extend(_mineru_content_text(v) for v in value if _mineru_content_text(v))
        elif isinstance(value, str) and value.strip():
            texts.append(value)
    return "\n".join(texts)


def _mineru_content_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [_mineru_content_text(v) for v in value]
        return " ".join(p for p in parts if p).strip()
    if not isinstance(value, dict):
        return ""

    direct = value.get("content")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    html_value = value.get("html")
    parts = []
    for key in (
        "title_content", "paragraph_content", "page_header_content", "page_footer_content",
        "page_number_content", "math_content", "table_caption", "table_footnote",
        "image_caption", "image_footnote", "chart_caption", "chart_footnote", "item_content",
    ):
        item = value.get(key)
        text = _mineru_content_text(item)
        if text:
            parts.append(text)
    list_items = value.get("list_items")
    if isinstance(list_items, list):
        for idx, item in enumerate(list_items, 1):
            text = _mineru_content_text(item)
            if text:
                parts.append(f"{idx}. {text}")
    if isinstance(html_value, str) and html_value.strip():
        parts.append(html_value.strip())
    return "\n".join(parts).strip()


def _format_mineru_table_block(text, page, table_idx):
    text = _normalize_mineru_table_text(text)
    return (
        f"[[TABLE_START page={page} id={table_idx}]]\n"
        "[[EXTRACTION_NOTE]] This table was extracted by MinerU/OCR. Broken alignment, merged cells, or missing separators are extraction artifacts unless numeric contradictions are explicit. [[/EXTRACTION_NOTE]]\n"
        f"{text}\n"
        "[[TABLE_END]]"
    )


def _normalize_mineru_table_text(text):
    raw = str(text or "")
    rows = _parse_html_table_rows(text)
    if rows:
        prefix = re.split(r"<table\b", raw, maxsplit=1, flags=re.I)[0]
        prefix = re.sub(r"<[^>]+>", " ", html.unescape(prefix))
        prefix = re.sub(r"\s+", " ", prefix).strip()
        table_text = _table_rows_to_markdown(rows)
        return "\n".join(part for part in (prefix, table_text) if part)
    return _normalize_markdown_table(text)


def _table_rows_to_markdown(rows):
    rows = [[re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row] for row in rows if row]
    if not rows:
        return ""
    max_cols = max(len(row) for row in rows)
    rows = [row + [""] * (max_cols - len(row)) for row in rows]

    def cell(value):
        return str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(cell(c) for c in rows[0]) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(cell(c) for c in row) + " |")
    return "\n".join(lines)


def _normalize_markdown_table(text):
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "\n".join(lines)
