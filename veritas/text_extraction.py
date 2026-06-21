"""Local text extraction helpers."""

import re
import zlib

__all__ = ["extract_pdf_text"]


def extract_pdf_text(filepath, max_chars=8000):
    """Extract text from a PDF with a minimal standard-library stream fallback."""
    with open(filepath, "rb") as f:
        raw = f.read()
    parts = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL):
        try:
            decompressed = zlib.decompress(stream)
            for value in re.findall(rb"\((.*?)\)\s*Tj", decompressed):
                decoded = value.decode("latin-1", errors="ignore")
                if len(decoded.strip()) > 1:
                    parts.append(decoded)
            for text_block in re.findall(rb"BT(.*?)ET", decompressed, re.DOTALL):
                for value in re.findall(rb"\((.*?)\)", text_block):
                    decoded = value.decode("latin-1", errors="ignore")
                    if len(decoded.strip()) > 1:
                        parts.append(decoded)
        except Exception:
            pass
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    meta = {
        "size_mb": round(len(raw) / 1024 / 1024, 2),
        "total_chars": len(text),
        "extraction_method": "raw_pdf_stream",
    }
    return text[:max_chars], meta, raw
