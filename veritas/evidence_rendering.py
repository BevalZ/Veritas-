"""Evidence excerpt and table rendering helpers."""

import html
import re

from .html_utils import _html_escape
from .text_utils import _brief_text

__all__ = [
    "_split_markdown_table_row",
    "_is_markdown_table_separator",
    "_looks_like_markdown_table",
    "_clean_mineru_table_block",
    "_plain_table_summary_text",
    "_render_data_table_html",
    "_markdown_table_to_html",
    "_parse_html_table_rows",
    "_escaped_html_table_fragment_to_html",
    "_render_unmarked_evidence_html",
    "render_evidence_html",
    "_evidence_contains_table",
    "render_evidence_summary_html",
]


def _split_markdown_table_row(line):
    line = str(line or "").strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.replace("\\|", "|").strip() for cell in line.split("|")]


def _is_markdown_table_separator(line):
    cells = _split_markdown_table_row(line)
    if len(cells) < 2:
        return False
    return all(cell and "-" in cell and re.fullmatch(r"[:\-\s]+", cell) for cell in cells)


def _looks_like_markdown_table(lines, idx):
    if idx + 1 >= len(lines):
        return False
    if "|" not in lines[idx]:
        return False
    return _is_markdown_table_separator(lines[idx + 1])


def _clean_mineru_table_block(text):
    text = re.sub(r"\[\[TABLE_START[^\]]*\]\]", "", str(text or ""))
    text = re.sub(r"\[\[TABLE_END\]\]", "", text)
    text = re.sub(r"\[\[TABLE_CONTINUATION[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[EXTRACTION_NOTE\]\].*?\[\[/EXTRACTION_NOTE\]\]", "", text, flags=re.S)
    return text.strip()


def _plain_table_summary_text(text):
    text = _clean_mineru_table_block(text)
    text = html.unescape(text)
    text = re.sub(r"</t[dh]>\s*<t[dh]\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"</tr>\s*<tr\b[^>]*>", " / ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _render_data_table_html(rows, header=True, collapse_threshold_rows=12, collapse_threshold_cols=8):
    rows = [[str(cell or "").strip() for cell in row] for row in rows if row]
    if not rows:
        return ""
    max_cols = max(len(row) for row in rows)
    normalized = [row + [""] * (max_cols - len(row)) for row in rows]

    body_rows = []
    for r_idx, row in enumerate(normalized):
        tag = "th" if header and r_idx == 0 else "td"
        cells = "".join(f"<{tag}>{_html_escape(cell)}</{tag}>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")

    table_html = (
        '<div class="data-table-wrap">'
        '<table class="data-table">'
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )
    is_large = len(normalized) > collapse_threshold_rows or max_cols > collapse_threshold_cols
    if is_large:
        return (
            '<details class="data-table-details">'
            f"<summary>查看完整表格（{len(normalized)}行 x {max_cols}列）</summary>"
            f"{table_html}"
            "</details>"
        )
    return table_html


def _markdown_table_to_html(lines):
    if isinstance(lines, str):
        lines = [line for line in lines.splitlines() if line.strip()]
    if len(lines) < 2 or not _is_markdown_table_separator(lines[1]):
        return ""
    rows = [_split_markdown_table_row(lines[0])]
    rows.extend(_split_markdown_table_row(line) for line in lines[2:] if "|" in line)
    return _render_data_table_html(rows, header=True)


def _parse_html_table_rows(text):
    decoded = html.unescape(str(text or ""))
    row_matches = re.findall(r"<tr\b[^>]*>(.*?)</tr>", decoded, flags=re.I | re.S)
    if not row_matches and re.search(r"<t[dh]\b", decoded, flags=re.I):
        row_matches = [decoded]

    rows = []
    for row_html in row_matches:
        cells = []
        for _tag, value in re.findall(r"<(td|th)\b[^>]*>(.*?)</\1>", row_html, flags=re.I | re.S):
            value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
            value = re.sub(r"<[^>]+>", " ", value)
            cells.append(html.unescape(re.sub(r"\s+", " ", value).strip()))
        if cells:
            rows.append(cells)
    return rows


def _escaped_html_table_fragment_to_html(text):
    rows = _parse_html_table_rows(text)
    if not rows:
        return ""
    first_row_is_header = bool(re.search(r"<th\b", html.unescape(str(text or "")), flags=re.I))
    return _render_data_table_html(rows, header=first_row_is_header)


def _render_unmarked_evidence_html(text):
    text = _clean_mineru_table_block(text)
    if not text:
        return ""

    html_table = _escaped_html_table_fragment_to_html(text)
    if html_table:
        return html_table

    lines = text.splitlines()
    parts = []
    paragraph = []
    i = 0
    while i < len(lines):
        if _looks_like_markdown_table(lines, i):
            if paragraph:
                paragraph_text = "\n".join(paragraph).strip()
                parts.append(f"<blockquote>{_html_escape(paragraph_text)}</blockquote>")
                paragraph = []
            table_lines = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            parts.append(_markdown_table_to_html(table_lines))
            continue
        paragraph.append(lines[i])
        i += 1

    if paragraph:
        plain = "\n".join(paragraph).strip()
        if plain:
            parts.append(f"<blockquote>{_html_escape(plain)}</blockquote>")
    return "".join(part for part in parts if part)


def render_evidence_html(text, compact=False):
    """Render evidence excerpts, converting table fragments to readable HTML."""
    text = str(text or "").strip()
    if not text:
        return "<blockquote>LLM未提供明确原文摘录，请人工回查对应段落。</blockquote>"

    parts = []
    pos = 0
    start_pattern = re.compile(r"\[\[TABLE_START[^\]]*\]\]", re.S)
    for match in start_pattern.finditer(text):
        if match.start() < pos:
            continue
        before = text[pos:match.start()].strip()
        if before:
            parts.append(_render_unmarked_evidence_html(before))
        end_match = re.search(r"\[\[TABLE_END\]\]", text[match.end():], flags=re.S)
        block_end = match.end() + end_match.end() if end_match else len(text)
        table_block = _clean_mineru_table_block(text[match.start():block_end])
        rendered_table = _render_unmarked_evidence_html(table_block)
        if rendered_table:
            parts.append(rendered_table)
        pos = block_end
    rest = text[pos:].strip()
    if rest:
        parts.append(_render_unmarked_evidence_html(rest))

    rendered = "".join(part for part in parts if part)
    return rendered or f"<blockquote>{_html_escape(_clean_mineru_table_block(text))}</blockquote>"


def _evidence_contains_table(text):
    raw = str(text or "")
    if "[[TABLE_START" in raw:
        return True
    decoded = html.unescape(raw)
    if re.search(r"<(?:table|tr|td|th)\b", decoded, flags=re.I):
        return True
    lines = raw.splitlines()
    return any(_looks_like_markdown_table(lines, i) for i in range(len(lines)))


def render_evidence_summary_html(text, limit=160):
    """Render compact evidence summaries without embedding large tables."""
    text = str(text or "").strip()
    if not text:
        return "-"
    if _evidence_contains_table(text):
        cleaned = _plain_table_summary_text(text)
        excerpt = _brief_text(cleaned, 80)
        hint = '<span class="table-hint">含表格，见下方逐条详细分析</span>'
        return f"{hint}<span class=\"summary-excerpt\">{_html_escape(excerpt)}</span>" if excerpt else hint
    return _html_escape(_brief_text(text, limit))
