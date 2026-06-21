"""Shared text normalization and summarization helpers."""

import hashlib
import html
import re


def _brief_text(text, limit=180):
    """Compress long text for report and diagnostic readability."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _text_fingerprint(text: str, extra: str = ""):
    """Stable short fingerprint used by report evidence IDs and LLM caches."""
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8", errors="ignore"))
    h.update(str(extra).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:16]


def _normalize_title(value):
    value = html.unescape(str(value or "")).lower()
    value = re.sub(r"\bdoi\s*[:：]\s*10\.\S+", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _title_tokens(value):
    normalized = _normalize_title(value)
    stop = {
        "the", "and", "for", "with", "from", "into", "onto", "that", "this", "using",
        "study", "analysis", "research", "journal", "vol", "volume", "issue", "pages",
    }
    return {token for token in normalized.split() if len(token) >= 3 and token not in stop}


def _token_similarity(a, b):
    left = _title_tokens(a)
    right = _title_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


__all__ = [
    "_brief_text",
    "_text_fingerprint",
    "_normalize_title",
    "_title_tokens",
    "_token_similarity",
]
