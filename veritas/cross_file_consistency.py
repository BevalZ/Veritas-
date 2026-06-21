"""Cross-file consistency analysis and report rendering helpers."""

import collections
import re
from pathlib import Path

from .evidence_rendering import _clean_mineru_table_block
from .html_utils import _html_escape
from .text_utils import _brief_text

__all__ = [
    "_cross_file_source_label",
    "_cross_file_source_rank",
    "_cross_file_segment_text",
    "_cross_file_terms",
    "_cross_file_is_noisy",
    "_extract_cross_file_sample_records",
    "_cross_file_shared_terms",
    "_cross_file_context_match",
    "_cross_file_finding",
    "_cross_file_sample_findings",
    "_normalize_group_label",
    "_extract_cross_file_group_labels",
    "_cross_file_group_findings",
    "_extract_supplementary_refs",
    "_cross_file_figure_table_findings",
    "build_cross_file_consistency_audit",
    "_cross_file_severity_label",
    "format_cross_file_consistency_markdown",
    "format_cross_file_consistency_html",
]


def _md_escape_cell(text):
    """Markdown table cell escaping for cross-file report rows."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("|", "\\|")


def _cross_file_source_label(category):
    return {
        "main_text": "正文",
        "supplement": "补充材料",
        "data_file": "数据文件",
        "other": "其他材料",
    }.get(category or "", category or "未知来源")


def _cross_file_source_rank(category):
    return {
        "main_text": 0,
        "supplement": 1,
        "data_file": 2,
        "other": 3,
    }.get(category or "", 9)


def _cross_file_segment_text(text):
    raw = _clean_mineru_table_block(str(text or ""))
    raw = re.sub(r"\[\[/?(?:BLOCK|FIGURE)[^\]]*\]\]", " ", raw, flags=re.I)
    segments = []
    for line in raw.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[。.!?])\s+|\s{2,}", line):
            part = part.strip()
            if 12 <= len(part) <= 800:
                segments.append(part)
    return segments[:1200]


_CROSS_FILE_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "were", "was", "are",
    "into", "have", "has", "had", "not", "all", "table", "figure", "supplement",
    "supplementary", "group", "groups", "cohort", "sample", "samples", "patients",
    "subjects", "mice", "cells", "results", "method", "methods", "study", "data",
}


def _cross_file_terms(text):
    lowered = str(text or "").lower()
    terms = set()
    for token in re.findall(r"[a-z][a-z0-9_-]{2,}|[A-Za-z]*\d+[A-Za-z]*", lowered):
        token = token.strip("_-")
        if token and token not in _CROSS_FILE_STOPWORDS:
            terms.add(token)
    return terms


def _cross_file_is_noisy(text):
    raw = str(text or "")
    if "[文件解析失败" in raw or "[文本过长已截断]" in raw:
        return True
    pipe_count = raw.count("|")
    return pipe_count >= 8 and pipe_count > max(2, len(raw) // 80)


def _extract_cross_file_sample_records(entry):
    records = []
    patterns = [
        re.compile(r"\b[nN]\s*[=:：]\s*(\d{1,5})\b"),
        re.compile(r"\b(\d{1,5})\s+(?:patients?|subjects?|participants?|samples?|mice|cells|cases)\b", re.I),
    ]
    for segment in _cross_file_segment_text(entry.get("text", "")):
        if not re.search(r"\b(?:n\s*[=:：]|\d+\s+(?:patients?|subjects?|participants?|samples?|mice|cells|cases))", segment, re.I):
            continue
        for pattern in patterns:
            for match in pattern.finditer(segment):
                try:
                    value = int(match.group(1))
                except Exception:
                    continue
                if value <= 0:
                    continue
                records.append({
                    "value": value,
                    "terms": _cross_file_terms(segment),
                    "excerpt": segment,
                    "file": entry.get("file", ""),
                    "path": entry.get("path", ""),
                    "category": entry.get("category", ""),
                    "noisy": _cross_file_is_noisy(segment),
                })
    return records


def _cross_file_shared_terms(a, b):
    return sorted((a.get("terms") or set()) & (b.get("terms") or set()))


def _cross_file_context_match(a, b):
    shared = _cross_file_shared_terms(a, b)
    if shared:
        return shared
    a_text = str(a.get("excerpt") or "").lower()
    b_text = str(b.get("excerpt") or "").lower()
    figure_tokens_a = set(re.findall(r"\b(?:fig(?:ure)?|table)\s*s?\d+[a-z]?\b", a_text, flags=re.I))
    figure_tokens_b = set(re.findall(r"\b(?:fig(?:ure)?|table)\s*s?\d+[a-z]?\b", b_text, flags=re.I))
    return sorted(figure_tokens_a & figure_tokens_b)


def _cross_file_finding(conflict_type, severity, claim, counter, reason, manual_check):
    return {
        "conflict_type": conflict_type,
        "severity": severity,
        "claim": claim.get("text", ""),
        "claim_source": claim.get("category", ""),
        "claim_source_label": _cross_file_source_label(claim.get("category", "")),
        "claim_file": claim.get("file", ""),
        "claim_excerpt": _brief_text(claim.get("excerpt", ""), 420),
        "counter_evidence": counter.get("text", ""),
        "counter_source": counter.get("category", ""),
        "counter_source_label": _cross_file_source_label(counter.get("category", "")),
        "counter_file": counter.get("file", ""),
        "counter_excerpt": _brief_text(counter.get("excerpt", ""), 420),
        "reason": reason,
        "manual_check": manual_check,
    }


def _cross_file_sample_findings(entries):
    records = []
    for entry in entries:
        records.extend(_extract_cross_file_sample_records(entry))
    findings = []
    seen = set()
    for idx, a in enumerate(records):
        for b in records[idx + 1:]:
            if a.get("value") == b.get("value"):
                continue
            if a.get("category") == b.get("category") and a.get("file") == b.get("file"):
                continue
            shared = _cross_file_context_match(a, b)
            if not shared:
                continue
            severity = "weak" if a.get("noisy") or b.get("noisy") else "strong"
            key = (
                "sample_size_mismatch",
                tuple(sorted([a.get("file", ""), b.get("file", "")])),
                tuple(sorted([a.get("value"), b.get("value")])),
                tuple(shared[:4]),
            )
            if key in seen:
                continue
            seen.add(key)
            first, second = sorted([a, b], key=lambda item: _cross_file_source_rank(item.get("category")))
            findings.append(_cross_file_finding(
                "sample_size_mismatch",
                severity,
                {
                    **first,
                    "text": f"{_cross_file_source_label(first.get('category'))}报告样本量 n={first.get('value')}",
                },
                {
                    **second,
                    "text": f"{_cross_file_source_label(second.get('category'))}报告样本量 n={second.get('value')}",
                },
                f"相近上下文共享关键词 {', '.join(shared[:6])}，但样本量分别为 {first.get('value')} 和 {second.get('value')}。",
                "核对同一实验/队列/分组的最终纳入样本数、排除标准和表格版本是否一致。",
            ))
    return findings


def _normalize_group_label(label):
    label = re.sub(r"\s+", " ", str(label or "").strip().lower())
    aliases = {
        "wt": "wildtype",
        "wild-type": "wildtype",
        "ko": "knockout",
    }
    return aliases.get(label, label)


def _extract_cross_file_group_labels(entry):
    labels = {}
    patterns = [
        re.compile(r"\b(control|vehicle|placebo|treatment|treated|case|experimental|sham|wildtype|wild-type|wt|knockout|ko|disease)\s+(?:group|arm|cohort)\b", re.I),
        re.compile(r"\b(?:group|arm|cohort)\s+(?:of\s+)?(control|vehicle|placebo|treatment|treated|case|experimental|sham|wildtype|wild-type|wt|knockout|ko|disease)\b", re.I),
    ]
    for segment in _cross_file_segment_text(entry.get("text", "")):
        for pattern in patterns:
            for match in pattern.finditer(segment):
                label = _normalize_group_label(match.group(1))
                labels.setdefault(label, {
                    "label": label,
                    "excerpt": segment,
                    "file": entry.get("file", ""),
                    "path": entry.get("path", ""),
                    "category": entry.get("category", ""),
                })
    return labels


def _cross_file_group_findings(entries):
    by_category = collections.defaultdict(dict)
    for entry in entries:
        labels = _extract_cross_file_group_labels(entry)
        by_category[entry.get("category", "")].update(labels)
    main_labels = by_category.get("main_text") or {}
    other_labels = {}
    for category, labels in by_category.items():
        if category != "main_text":
            other_labels.update(labels)
    findings = []
    if "control" in main_labels and "vehicle" in other_labels and "vehicle" not in main_labels:
        findings.append(_cross_file_finding(
            "group_label_mismatch",
            "medium",
            {**main_labels["control"], "text": "正文使用 Control group"},
            {**other_labels["vehicle"], "text": "补充/数据材料使用 Vehicle group"},
            "正文与补充/数据材料使用了不同的对照组标签；两者可能是同义设计，也可能代表分组命名不一致。",
            "核对方法学定义、图表标签和原始分组编码，确认 Control 与 Vehicle 是否为同一组。",
        ))
    return findings


def _extract_supplementary_refs(text):
    refs = []
    pattern = re.compile(r"\b(?:Supplementary|Supplemental|附表|补充图|补充表)\s*(?:Fig(?:ure)?|Table)?\s*S?(\d+[A-Za-z]?)\b|\b(?:Fig(?:ure)?|Table)\s*S(\d+[A-Za-z]?)\b", re.I)
    for segment in _cross_file_segment_text(text):
        for match in pattern.finditer(segment):
            number = (match.group(1) or match.group(2) or "").lower()
            if number:
                refs.append((f"s{number}" if not number.startswith("s") else number, segment))
    return refs


def _cross_file_figure_table_findings(entries):
    main_text = "\n".join(entry.get("text", "") for entry in entries if entry.get("category") == "main_text")
    supplemental_text = "\n".join(entry.get("text", "") for entry in entries if entry.get("category") in {"supplement", "data_file"})
    if not main_text or not supplemental_text:
        return []
    supplement_lower = supplemental_text.lower()
    findings = []
    seen = set()
    for ref_id, excerpt in _extract_supplementary_refs(main_text):
        if ref_id in seen:
            continue
        seen.add(ref_id)
        compact = ref_id.replace("s", "")
        if ref_id in supplement_lower or f"table {compact}" in supplement_lower or f"figure {compact}" in supplement_lower:
            continue
        findings.append(_cross_file_finding(
            "supplement_reference_gap",
            "weak",
            {
                "category": "main_text",
                "file": "main_text",
                "excerpt": excerpt,
                "text": f"正文引用补充材料 {ref_id.upper()}",
            },
            {
                "category": "supplement",
                "file": "supplement/data files",
                "excerpt": f"未在已提取补充/数据文本中找到 {ref_id.upper()} 的直接标记。",
                "text": "补充材料标记覆盖不足",
            },
            "正文出现补充图表引用，但已提取补充材料中未找到对应编号标记。",
            "核对补充材料文件是否完整、编号是否被OCR/表格提取改写，或是否缺失对应补充图表。",
        ))
        if len(findings) >= 8:
            break
    return findings


def build_cross_file_consistency_audit(file_entries, root_path=None):
    entries = []
    for entry in file_entries or []:
        text = str(entry.get("text") or "")
        category = entry.get("category") or "other"
        if not text.strip() or category == "reference":
            continue
        entries.append({
            "file": entry.get("file") or Path(entry.get("path", "")).name,
            "path": entry.get("path") or entry.get("file") or "",
            "category": category,
            "text": text,
        })
    cross_categories = {entry.get("category") for entry in entries if entry.get("category") != "main_text"}
    if len(entries) < 2 or not cross_categories:
        return {
            "status": "skipped",
            "checked_files": len(entries),
            "finding_count": 0,
            "strong_count": 0,
            "medium_count": 0,
            "weak_count": 0,
            "findings": [],
            "note": "缺少可比较的跨文件材料；跨文件一致性审查已跳过。",
        }
    findings = []
    findings.extend(_cross_file_sample_findings(entries))
    findings.extend(_cross_file_group_findings(entries))
    findings.extend(_cross_file_figure_table_findings(entries))
    severity_rank = {"strong": 0, "medium": 1, "weak": 2}
    findings = sorted(findings, key=lambda item: (severity_rank.get(item.get("severity"), 9), item.get("conflict_type", ""), item.get("claim_file", "")))[:40]
    return {
        "status": "ok",
        "checked_files": len(entries),
        "finding_count": len(findings),
        "strong_count": sum(1 for item in findings if item.get("severity") == "strong"),
        "medium_count": sum(1 for item in findings if item.get("severity") == "medium"),
        "weak_count": sum(1 for item in findings if item.get("severity") == "weak"),
        "findings": findings,
        "note": "基于已提取文本的跨文件一致性审查；不等同于最终科研不端判断。",
    }


def _cross_file_severity_label(severity):
    return {
        "strong": "强证据冲突",
        "medium": "中等疑点",
        "weak": "弱信号/需人工核对",
    }.get(severity or "", severity or "未知")


def format_cross_file_consistency_markdown(audit):
    if audit is None:
        return []
    lines = [
        '<a id="cross-file-consistency"></a>',
        "## 🧩 跨文件一致性审查",
        "",
        f"**状态**: {audit.get('status', 'N/A')}",
        f"**检查文件数**: {audit.get('checked_files', 0)}",
        f"**发现数**: {audit.get('finding_count', 0)}（强 {audit.get('strong_count', 0)} / 中 {audit.get('medium_count', 0)} / 弱 {audit.get('weak_count', 0)}）",
        f"> {audit.get('note', '')}",
        "",
    ]
    findings = audit.get("findings") or []
    if findings:
        lines.append("| # | 级别 | 类型 | 证据A | 证据B | 复核建议 |")
        lines.append("|---|------|------|-------|-------|----------|")
        for idx, finding in enumerate(findings[:30], 1):
            claim = f"{finding.get('claim_source_label') or finding.get('claim_source')} / {finding.get('claim_file')}: {finding.get('claim_excerpt')}"
            counter = f"{finding.get('counter_source_label') or finding.get('counter_source')} / {finding.get('counter_file')}: {finding.get('counter_excerpt')}"
            lines.append(
                f"| {idx} | {_md_escape_cell(_cross_file_severity_label(finding.get('severity')))} | "
                f"{_md_escape_cell(finding.get('conflict_type', ''))} | {_md_escape_cell(_brief_text(claim, 260))} | "
                f"{_md_escape_cell(_brief_text(counter, 260))} | {_md_escape_cell(finding.get('manual_check', ''))} |"
            )
    else:
        lines.append("> 未发现明确跨文件不一致；仍建议人工抽查关键表格、补充材料和正文结论。")
    lines.append("")
    return lines


def format_cross_file_consistency_html(audit):
    if not audit:
        return ""
    findings = audit.get("findings") or []
    if findings:
        cards = ""
        for idx, finding in enumerate(findings[:40], 1):
            cards += f"""
        <details class="cross-file-card" id="cross-file-finding-{idx}">
          <summary class="cross-file-summary">
            <span class="cross-file-rank">#{idx}</span>
            <span class="cross-file-severity cross-file-{_html_escape(finding.get('severity', ''))}">{_html_escape(_cross_file_severity_label(finding.get('severity')))}</span>
            <span class="cross-file-title">{_html_escape(finding.get('conflict_type', ''))}</span>
            <span class="cross-file-reason">{_html_escape(_brief_text(finding.get('reason', ''), 140))}</span>
          </summary>
          <div class="cross-file-body">
            <div><strong>{_html_escape(finding.get('claim_source_label') or finding.get('claim_source'))} / {_html_escape(finding.get('claim_file', ''))}</strong><p>{_html_escape(finding.get('claim_excerpt', ''))}</p></div>
            <div><strong>{_html_escape(finding.get('counter_source_label') or finding.get('counter_source'))} / {_html_escape(finding.get('counter_file', ''))}</strong><p>{_html_escape(finding.get('counter_excerpt', ''))}</p></div>
            <p><strong>复核建议</strong>: {_html_escape(finding.get('manual_check', ''))}</p>
          </div>
        </details>"""
    else:
        cards = '<div class="muted">未发现明确跨文件不一致；仍建议人工抽查关键表格、补充材料和正文结论。</div>'
    return f"""
  <div class="section cross-file-section" id="cross-file-consistency">
    <h2>跨文件一致性审查</h2>
    <p><strong>状态</strong>: {_html_escape(audit.get('status', 'N/A'))} | <strong>文件</strong>: {audit.get('checked_files', 0)} | <strong>发现</strong>: {audit.get('finding_count', 0)}（强 {audit.get('strong_count', 0)} / 中 {audit.get('medium_count', 0)} / 弱 {audit.get('weak_count', 0)}）</p>
    <p class="section-hint">{_html_escape(audit.get('note', ''))}</p>
    <div class="cross-file-list">{cards}</div>
  </div>"""
