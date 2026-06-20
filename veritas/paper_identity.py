"""Best-effort article identity extraction helpers."""

import re
from pathlib import Path
from typing import Any, Dict

from .evidence_rendering import _clean_mineru_table_block

__all__ = ["extract_paper_identity"]


def extract_paper_identity(full_text: str, input_path: Path = None) -> Dict[str, Any]:
    """Best-effort paper identity extraction for follow-up drafts."""
    raw_text = _clean_mineru_table_block(full_text or "")
    lines = []
    for line in raw_text.splitlines():
        cleaned = re.sub(r"\s+", " ", str(line or "")).strip()
        if cleaned:
            lines.append(cleaned)
    top_lines = lines[:40]

    def score_title(line: str) -> float:
        lowered = line.lower()
        if len(line) < 12 or len(line) > 220:
            return -100.0
        if any(term in lowered for term in ("abstract", "keyword", "keywords", "introduction", "references", "reference")):
            return -100.0
        score = 0.0
        score += min(len(line) / 24.0, 8.0)
        if re.search(r"[A-Za-z]", line):
            score += 2.0
        if re.search(r"[.!?]$", line):
            score -= 1.5
        if "@" in line or re.search(r"\b(?:department|university|institute|hospital)\b", lowered):
            score -= 2.0
        if re.search(r"\b(?:doi|vol\.?|volume|issue|pages?|pp\.?|journal|nature|science|cell|bmc|plos|springer|elsevier|wiley|frontiers)\b", lowered):
            score -= 1.0
        if re.search(r"\b[A-Z]\.\s*[A-Z]\.", line):
            score -= 2.5
        if line.count(",") >= 3:
            score -= 1.5
        return score

    def looks_like_author_line(line: str) -> bool:
        lowered = line.lower()
        if len(line) > 180:
            return False
        if any(term in lowered for term in ("abstract", "keyword", "keywords", "introduction", "references")):
            return False
        return bool(
            re.search(r"\b[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)+\b", line)
            or re.search(r"\bet al\.?\b", lowered)
            or line.count(",") >= 2
            or " and " in lowered
        )

    def looks_like_journal(line: str) -> bool:
        lowered = line.lower()
        return bool(re.search(r"\b(?:journal|nature|science|cell|lancet|bmc|plos|springer|elsevier|wiley|frontiers|ieee|acm|proceedings)\b", lowered))

    title = max(top_lines, key=score_title, default="")
    if title and score_title(title) < 0:
        title = ""
    authors = []
    journal = ""
    for line in top_lines:
        if not journal and looks_like_journal(line):
            journal = line
        if not authors and looks_like_author_line(line) and line != title:
            authors = [part.strip() for part in re.split(r",|;| and ", line) if part.strip()]
        if title and authors and journal:
            break
    if not title and input_path is not None:
        try:
            title = Path(input_path).stem.replace("_", " ").replace("-", " ").strip()
        except Exception:
            title = ""
    if authors:
        authors = authors[:6]
    return {
        "title": title,
        "journal": journal,
        "authors": authors,
    }
