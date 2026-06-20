"""Local statistics and text chunking helpers."""

import collections
import math
import re


def benford_analysis(numbers):
    """Benford analysis for detecting anomalous first-digit distributions."""
    if len(numbers) < 100:
        return None, "样本不足(需≥100)"
    digits = [str(abs(int(n)))[0] for n in numbers if abs(int(n)) >= 1]
    if not digits:
        return None, "无有效数字"
    counts = collections.Counter(digits)
    total = len(digits)
    expected = {str(d): math.log10(1 + 1 / d) * total for d in range(1, 10)}
    deviations = {}
    for d in range(1, 10):
        d_str = str(d)
        actual = counts.get(d_str, 0)
        exp = expected[d_str]
        deviations[d_str] = abs(actual - exp) / exp
    avg_deviation = sum(deviations.values()) / 9
    return avg_deviation, "高偏差⚠️" if avg_deviation > 0.3 else "正常✅"


def extract_all_numbers(text):
    """Extract numeric observations while filtering common year/page noise."""
    exclude = {
        2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027,
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    }
    nums = []
    for match in re.finditer(r"\b(\d+\.?\d*)\b", text):
        try:
            n = float(match.group(1))
            if n not in exclude and n > 0:
                nums.append(n)
        except Exception:
            pass
    return nums


def local_stat_check(text):
    """Run local statistical checks without calling an LLM."""
    result = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "p_value_details": [],
        "sd_count": 0,
        "sd_abnormal": 0,
        "number_count": 0,
        "number_consistency": None,
    }
    nums = extract_all_numbers(text)
    result["number_count"] = len(nums)
    if nums:
        dev, status = benford_analysis(nums)
        result["benford_deviation"] = dev
        result["benford_status"] = status
    p_matches = re.findall(r"p\s*[=<]\s*(\d+\.?\d*)", text, re.IGNORECASE)
    result["p_value_count"] = len(p_matches)
    for p in p_matches:
        try:
            pv = float(p)
            if pv > 0.05:
                result["p_value_abnormal"] += 1
                result["p_value_details"].append(f"p={'<=' + p if pv <= 0.001 else '=' + p}")
        except Exception:
            pass
    sd_matches = re.findall(r"(?:std|sd|标准差|SE|SEM)\s*[=:≈]\s*(\d+\.?\d*)", text, re.IGNORECASE)
    result["sd_count"] = len(sd_matches)
    n_matches = re.findall(r"(?:n|N|sample|样本)\s*[=:]\s*(\d+)", text, re.IGNORECASE)
    if len(set(n_matches)) > 1:
        result["number_consistency"] = f"检测到不同样本量: {set(n_matches)}"
    return result


def smart_chunk_text(text, chunk_size=8000, overlap=1000):
    """Split text by structure while preserving table blocks."""
    if chunk_size <= 0:
        chunk_size = 8000
    overlap = max(0, min(overlap, chunk_size // 4))

    def hard_split(s, size):
        parts = []
        s = s or ""
        while len(s) > size:
            cut = size
            window_start = max(0, size - 800)
            candidates = [s.rfind(sep, window_start, size) for sep in ["\n", "。", ". ", "; ", "；", ", ", "，", " "]]
            best = max(candidates)
            if best > max(200, size // 2):
                cut = best + 1
            parts.append(s[:cut].strip())
            s = s[cut:].strip()
        if s.strip():
            parts.append(s.strip())
        return parts

    def split_structured_blocks(s):
        blocks = []
        pos = 0
        pattern = re.compile(r"\[\[TABLE_START[^\]]*\]\][\s\S]*?\[\[TABLE_END\]\]", re.IGNORECASE)
        for match in pattern.finditer(s or ""):
            prefix = s[pos:match.start()]
            blocks.extend(("text", p.strip()) for p in re.split(r"\n{2,}", prefix) if p.strip())
            blocks.append(("table", match.group().strip()))
            pos = match.end()
        suffix = s[pos:]
        blocks.extend(("text", p.strip()) for p in re.split(r"\n{2,}", suffix) if p.strip())
        return blocks

    def split_table_block(block, size):
        if len(block) <= size:
            return [block]
        start = re.search(r"\[\[TABLE_START[^\]]*\]\]", block)
        note = re.search(r"\[\[EXTRACTION_NOTE\]\][\s\S]*?\[\[/EXTRACTION_NOTE\]\]", block)
        header = start.group() if start else "[[TABLE_START split=true]]"
        if note:
            header += "\n" + note.group()
        body = re.sub(r"\[\[TABLE_START[^\]]*\]\]", "", block, count=1)
        body = re.sub(r"\[\[EXTRACTION_NOTE\]\][\s\S]*?\[\[/EXTRACTION_NOTE\]\]", "", body, count=1)
        body = body.replace("[[TABLE_END]]", "").strip()
        rows = [r for r in body.splitlines() if r.strip()]
        if not rows:
            return hard_split(block, size)
        table_header_rows = rows[:2] if len(rows) >= 2 and "|" in rows[0] else rows[:1]
        chunks = []
        current_rows = []
        part = 1
        for row in rows:
            prefix = f"{header}\n[[TABLE_CONTINUATION part={part}]]\n" + "\n".join(table_header_rows)
            candidate_rows = current_rows + [row]
            candidate = prefix + "\n" + "\n".join(candidate_rows) + "\n[[TABLE_END]]"
            if current_rows and len(candidate) > size:
                chunk = prefix + "\n" + "\n".join(current_rows) + "\n[[TABLE_END]]"
                chunks.extend(hard_split(chunk, size) if len(chunk) > size else [chunk])
                current_rows = [row]
                part += 1
            else:
                current_rows = candidate_rows
        if current_rows:
            prefix = f"{header}\n[[TABLE_CONTINUATION part={part}]]\n" + "\n".join(table_header_rows)
            chunk = prefix + "\n" + "\n".join(current_rows) + "\n[[TABLE_END]]"
            chunks.extend(hard_split(chunk, size) if len(chunk) > size else [chunk])
        return chunks

    if len(text) <= chunk_size:
        return [(text, 0, 1)]

    blocks = []
    for kind, block in split_structured_blocks(text):
        if kind == "table":
            blocks.extend(split_table_block(block, chunk_size))
        elif len(block) > chunk_size:
            blocks.extend(hard_split(block, chunk_size))
        else:
            blocks.append(block)

    chunks = []
    current = ""
    for part in blocks:
        candidate = (current + "\n\n" + part).strip() if current else part
        if current and len(candidate) > chunk_size:
            chunks.append(current[:chunk_size])
            prefix = current[-overlap:] + "\n\n" if overlap > 0 and len(current) > overlap else ""
            candidate = (prefix + part).strip()
            if len(candidate) > chunk_size:
                chunks.extend(split_table_block(part, chunk_size) if "[[TABLE_START" in part else hard_split(part, chunk_size))
                current = ""
            else:
                current = candidate
        else:
            current = candidate
    if current:
        chunks.append(current[:chunk_size])

    safe_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size:
            safe_chunks.extend(split_table_block(chunk, chunk_size) if "[[TABLE_START" in chunk else hard_split(chunk, chunk_size))
        elif chunk.strip():
            safe_chunks.append(chunk)

    total = len(safe_chunks)
    return [(chunk, index, total) for index, chunk in enumerate(safe_chunks)]


__all__ = [
    "benford_analysis",
    "extract_all_numbers",
    "local_stat_check",
    "smart_chunk_text",
]
