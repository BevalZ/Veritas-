"""Evidence-chain analysis and evidence-cluster report rendering helpers."""

import collections
import re

from .cross_file_consistency import (
    _cross_file_context_match,
    _cross_file_segment_text,
    _cross_file_severity_label,
    _cross_file_terms,
    _extract_cross_file_group_labels,
    _extract_cross_file_sample_records,
)
from .html_utils import _html_escape
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_text,
    _check_suspicion_score,
    _is_suspicious_check,
)
from .text_utils import _brief_text, _text_fingerprint

__all__ = [
    "_evidence_section_name",
    "_extract_evidence_sections",
    "_extract_section_sample_records",
    "_extract_section_group_records",
    "_evidence_segment_has_strong_claim",
    "_evidence_claim_keywords",
    "_results_support_claim",
    "_build_claim_chain_findings",
    "_extract_evidence_refs",
    "_evidence_keys_from_text",
    "_evidence_item",
    "_evidence_items_from_chain_findings",
    "_evidence_items_from_cross_file",
    "_evidence_items_from_llm_report",
    "_evidence_items_from_stat",
    "_evidence_items_from_reference",
    "_evidence_items_from_resource",
    "_evidence_items_from_image",
    "_cluster_severity",
    "_build_evidence_clusters",
    "build_evidence_chain_audit",
    "format_evidence_chain_audit_markdown",
    "format_evidence_chain_audit_html",
]


_EVIDENCE_SECTION_ALIASES = {
    "abstract": "abstract",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "materials & methods": "methods",
    "results": "results",
    "result": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
}


_EVIDENCE_STRONG_CLAIM_TERMS = (
    "demonstrate", "demonstrated", "demonstrates", "prove", "proved", "proves",
    "confirm", "confirmed", "confirms", "establish", "established", "significant",
    "significantly", "markedly", "robustly", "definitive", "definitively",
    "证明", "证实", "确定", "显著", "明确", "强烈", "完全",
)


_EVIDENCE_SUPPORT_HINT_RE = re.compile(
    r"\b(?:p\s*[<=>]|n\s*[=:：]|\d+\s+(?:patients?|subjects?|participants?|samples?|mice|cells|cases)|fig(?:ure)?|table)\b|图\s*\d+|表\s*\d+",
    re.I,
)


def _md_escape_cell(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("|", "\\|")


def _evidence_section_name(raw):
    return _EVIDENCE_SECTION_ALIASES.get(re.sub(r"\s+", " ", str(raw or "").strip().lower()))


def _extract_evidence_sections(text):
    sections = collections.defaultdict(list)
    current = None
    heading_re = re.compile(
        r"^\s*(abstract|materials\s+(?:and|&)\s+methods|methods?|results?|discussion|conclusions?)\s*(?::\s*(.*)|$)",
        re.I,
    )
    for line in str(text or "").splitlines():
        stripped = line.strip()
        match = heading_re.match(stripped)
        if match and len((match.group(2) or "").strip()) <= 240:
            section_name = _evidence_section_name(match.group(1))
            trailing = (match.group(2) or "").strip()
            if section_name:
                current = section_name
                if trailing:
                    sections[current].append(trailing)
                continue
        if current:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _extract_section_sample_records(text, section):
    entry = {"text": text, "file": section, "path": section, "category": section}
    records = []
    for record in _extract_cross_file_sample_records(entry):
        record = dict(record)
        record["section"] = section
        records.append(record)
    return records


def _extract_section_group_records(text, section):
    entry = {"text": text, "file": section, "path": section, "category": section}
    records = []
    for label, record in _extract_cross_file_group_labels(entry).items():
        item = dict(record)
        item["label"] = label
        item["section"] = section
        records.append(item)
    return records


def _evidence_segment_has_strong_claim(segment):
    lowered = str(segment or "").lower()
    return any(term in lowered or term in segment for term in _EVIDENCE_STRONG_CLAIM_TERMS)


def _evidence_claim_keywords(text):
    terms = _cross_file_terms(text)
    generic = {
        "abstract", "conclusion", "conclusions", "paper", "article", "study",
        "studies", "result", "results", "finding", "findings", "show", "shows",
        "shown", "demonstrate", "demonstrated", "demonstrates", "significant",
        "significantly", "prove", "proved", "confirm", "confirmed",
    }
    return sorted(term for term in terms if term not in generic)[:12]


def _results_support_claim(result_text, claim_segment):
    result_lower = str(result_text or "").lower()
    keywords = _evidence_claim_keywords(claim_segment)
    shared = [term for term in keywords if term.lower() in result_lower]
    if len(shared) >= 2:
        return True
    if shared and _EVIDENCE_SUPPORT_HINT_RE.search(result_text or ""):
        return True
    return False


def _build_claim_chain_findings(full_text):
    sections = _extract_evidence_sections(full_text)
    methods_text = sections.get("methods", "")
    results_text = sections.get("results", "")
    findings = []

    if methods_text and results_text:
        method_samples = _extract_section_sample_records(methods_text, "methods")
        result_samples = _extract_section_sample_records(results_text, "results")
        seen = set()
        for method_record in method_samples:
            for result_record in result_samples:
                if method_record.get("value") == result_record.get("value"):
                    continue
                shared = _cross_file_context_match(method_record, result_record)
                if not shared:
                    continue
                key = ("sample_size_chain_mismatch", method_record.get("value"), result_record.get("value"), tuple(shared[:5]))
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "type": "methods_results_sample_size_mismatch",
                    "severity": "strong" if not method_record.get("noisy") and not result_record.get("noisy") else "medium",
                    "chain": "Methods -> Results",
                    "method_excerpt": _brief_text(method_record.get("excerpt", ""), 420),
                    "result_excerpt": _brief_text(result_record.get("excerpt", ""), 420),
                    "reason": f"Methods 与 Results 在相近上下文共享关键词 {', '.join(shared[:6])}，但样本量分别为 {method_record.get('value')} 和 {result_record.get('value')}。",
                    "manual_check": "核对同一实验/队列/分组的纳入样本量、排除标准和最终图表版本。",
                    "evidence_keys": sorted(set(shared) | {f"n={method_record.get('value')}", f"n={result_record.get('value')}"}),
                })
                if len(findings) >= 20:
                    break
            if len(findings) >= 20:
                break

        method_groups = {item.get("label"): item for item in _extract_section_group_records(methods_text, "methods")}
        result_groups = {item.get("label"): item for item in _extract_section_group_records(results_text, "results")}
        if "control" in method_groups and "vehicle" in result_groups and "vehicle" not in method_groups:
            findings.append({
                "type": "methods_results_group_label_mismatch",
                "severity": "medium",
                "chain": "Methods -> Results",
                "method_excerpt": _brief_text(method_groups["control"].get("excerpt", ""), 420),
                "result_excerpt": _brief_text(result_groups["vehicle"].get("excerpt", ""), 420),
                "reason": "Methods 使用 Control group，Results 使用 Vehicle group；两者可能是同义设计，也可能是分组命名不一致。",
                "manual_check": "核对方法学定义、图表标签和原始分组编码，确认 Control 与 Vehicle 是否为同一组。",
                "evidence_keys": ["control", "vehicle"],
            })

    conclusion_sources = []
    for section_name in ("abstract", "conclusion"):
        for segment in _cross_file_segment_text(sections.get(section_name, "")):
            if not _evidence_segment_has_strong_claim(segment):
                continue
            keywords = _evidence_claim_keywords(segment)
            if not keywords:
                continue
            if _results_support_claim(results_text, segment):
                continue
            conclusion_sources.append((section_name, segment, keywords))
    for section_name, segment, keywords in conclusion_sources[:12]:
        findings.append({
            "type": "strong_claim_without_result_support",
            "severity": "medium",
            "chain": f"{section_name.title()} -> Results",
            "claim_excerpt": _brief_text(segment, 420),
            "result_excerpt": _brief_text(results_text, 420) if results_text else "未识别到 Results 段落或结果证据不足。",
            "reason": "摘要/结论出现强结论措辞，但 Results 段落中未找到足够接近的结果、图表或统计支撑。",
            "manual_check": "回查 Results 中是否存在对应指标、图表编号、统计量和方向一致的结果描述。",
            "evidence_keys": keywords[:8],
        })

    severity_rank = {"strong": 0, "medium": 1, "weak": 2}
    return sorted(findings, key=lambda item: (severity_rank.get(item.get("severity"), 9), item.get("type", "")))[:40]


def _extract_evidence_refs(text):
    raw = str(text or "")
    refs = set()
    for prefix, number in re.findall(r"\b(fig(?:ure)?|table)\s*\.?\s*(s?\d+[a-z]?)\b", raw, flags=re.I):
        kind = "figure" if prefix.lower().startswith("fig") else "table"
        refs.add(f"{kind}:{number.lower()}")
    for prefix, number in re.findall(r"([图表])\s*\.?\s*(\d+[a-zA-Z]?)", raw):
        kind = "figure" if prefix == "图" else "table"
        refs.add(f"{kind}:{number.lower()}")
    return sorted(refs)


def _evidence_keys_from_text(text):
    keys = set(_extract_evidence_refs(text))
    for value in re.findall(r"\b[nN]\s*[=:：]\s*(\d{1,5})\b", str(text or "")):
        keys.add(f"n={value}")
    for term in _cross_file_terms(text):
        if term not in {"risk", "audit", "evidence", "reason", "manual"}:
            keys.add(term)
    return sorted(keys)[:24]


def _evidence_item(source_type, severity, title, detail="", excerpt="", keys=None, source_id=None):
    text = " ".join(str(part or "") for part in (title, detail, excerpt))
    return {
        "id": source_id or f"{source_type}-{_text_fingerprint(text)[:10]}",
        "source_type": source_type,
        "severity": severity if severity in {"strong", "medium", "weak"} else "weak",
        "title": _brief_text(title, 160),
        "detail": _brief_text(detail, 520),
        "excerpt": _brief_text(excerpt, 520),
        "keys": sorted(set(keys or []) | set(_evidence_keys_from_text(text)))[:32],
    }


def _evidence_items_from_chain_findings(findings):
    items = []
    for idx, finding in enumerate(findings or [], 1):
        excerpt = " || ".join(
            part for part in (
                finding.get("method_excerpt"),
                finding.get("result_excerpt"),
                finding.get("claim_excerpt"),
            )
            if part
        )
        items.append(_evidence_item(
            "claim_chain",
            finding.get("severity", "weak"),
            finding.get("type", "claim_chain_finding"),
            finding.get("reason") or finding.get("manual_check") or "",
            excerpt,
            keys=finding.get("evidence_keys") or [],
            source_id=f"chain-{idx}",
        ))
    return items


def _evidence_items_from_cross_file(meta):
    audit = (meta or {}).get("cross_file_consistency_audit") or {}
    items = []
    for idx, finding in enumerate((audit.get("findings") or [])[:30], 1):
        excerpt = (
            f"{finding.get('claim_source_label')} / {finding.get('claim_file')}: {finding.get('claim_excerpt')} "
            f"|| {finding.get('counter_source_label')} / {finding.get('counter_file')}: {finding.get('counter_excerpt')}"
        )
        items.append(_evidence_item(
            "cross_file_consistency",
            finding.get("severity", "weak"),
            finding.get("conflict_type", "cross_file_finding"),
            finding.get("reason") or finding.get("manual_check") or "",
            excerpt,
            source_id=f"cross-file-{idx}",
        ))
    return items


def _evidence_items_from_llm_report(report):
    checks = sorted(report.get("checks", []) if isinstance(report, dict) else [], key=_check_sort_key)
    items = []
    for idx, check in enumerate(checks[:80], 1):
        if not _is_suspicious_check(check):
            continue
        score = _check_suspicion_score(check)
        severity = "strong" if "红旗" in str(check.get("verdict", "")) or score >= 220 else "medium"
        items.append(_evidence_item(
            "llm_check",
            severity,
            f"{check.get('category', 'N/A')} / {check.get('item', 'N/A')}",
            _check_reason(check),
            _check_source_text(check),
            source_id=f"llm-{idx}",
        ))
    return items[:30]


def _evidence_items_from_stat(stat_result):
    stat_result = stat_result or {}
    items = []
    if stat_result.get("number_consistency"):
        items.append(_evidence_item(
            "local_stat",
            "medium",
            "数字自洽性需复核",
            stat_result.get("number_consistency"),
            source_id="stat-number-consistency",
        ))
    if stat_result.get("benford_status") and "高偏差" in str(stat_result.get("benford_status")):
        items.append(_evidence_item(
            "local_stat",
            "medium",
            "Benford分布偏差较高",
            f"偏差={round(stat_result.get('benford_deviation') or 0, 3)}；建议核对原始数值来源。",
            source_id="stat-benford",
        ))
    if (stat_result.get("p_value_abnormal") or 0) > 0:
        severity = "medium" if (stat_result.get("p_value_abnormal") or 0) >= 3 else "weak"
        items.append(_evidence_item(
            "local_stat",
            severity,
            "p值分布需复核",
            f"p值数量/异常: {stat_result.get('p_value_count', 0)} / {stat_result.get('p_value_abnormal', 0)}。",
            source_id="stat-p-values",
        ))
    return items


def _evidence_items_from_reference(meta):
    reference_audit = (meta or {}).get("reference_audit") or {}
    refs_by_index = {i + 1: ref for i, ref in enumerate(reference_audit.get("references") or [])}
    items = []
    for issue in (reference_audit.get("issues") or [])[:12]:
        ref = refs_by_index.get(issue.get("index"), {})
        online = ref.get("online") or {}
        status = online.get("online_status")
        if status and status not in {"not_found", "weak", "error"}:
            continue
        items.append(_evidence_item(
            "reference_audit",
            "medium" if status in {"not_found", "error"} else "weak",
            f"参考文献 #{issue.get('index')} 在线证据不足",
            "；".join(str(x) for x in issue.get("issues", []) if x) or status or "reference issue",
            issue.get("text", ""),
            source_id=f"reference-{issue.get('index')}",
        ))
    return items


def _evidence_items_from_resource(meta):
    resource_audit = (meta or {}).get("resource_audit") or {}
    items = []
    for idx, issue in enumerate((resource_audit.get("issues") or [])[:12], 1):
        status = issue.get("status")
        severity = "medium" if status in {"unavailable", "access_restricted", "malformed", "error"} else "weak"
        items.append(_evidence_item(
            "resource_audit",
            severity,
            f"论文资源需复核: {issue.get('type') or 'resource'}",
            issue.get("problem") or status or "",
            issue.get("url") or "",
            source_id=f"resource-{idx}",
        ))
    return items


def _evidence_items_from_image(meta):
    image_audit = (meta or {}).get("image_audit") or {}
    items = []
    for idx, img in enumerate((image_audit.get("images") or [])[:30], 1):
        sem = img.get("semantic") or {}
        detector = img.get("detector") or {}
        detector_score = detector.get("score")
        local_warning = img.get("risk") == "local_warning"
        semantic_warning = sem.get("reasonability") in {"需人工核对", "可疑"} or sem.get("status") == "error"
        detector_warning = detector.get("status") == "ok" and detector_score is not None and detector_score >= 50
        if not (local_warning or semantic_warning or detector_warning):
            continue
        severity = "medium" if sem.get("reasonability") == "可疑" or (detector_score or 0) >= 80 else "weak"
        details = []
        if local_warning:
            details.append("本地图像规则提示需复核")
        if semantic_warning:
            details.append(f"图像语义: {sem.get('reasonability') or sem.get('status')}")
        if detector_warning:
            details.append(f"imagedetector score={detector_score}")
        items.append(_evidence_item(
            "image_audit",
            severity,
            f"图像需复核: {img.get('file') or idx}",
            "；".join(details),
            " ".join(str(x or "") for x in (img.get("file"), sem.get("summary"), detector.get("message"))),
            source_id=f"image-{idx}",
        ))
    return items


def _cluster_severity(evidence):
    severities = [item.get("severity") for item in evidence]
    source_types = {item.get("source_type") for item in evidence}
    if "strong" in severities:
        return "strong"
    if len(source_types) >= 2 and "medium" in severities:
        return "strong"
    if "medium" in severities:
        return "medium"
    if len(source_types) >= 2:
        return "medium"
    return "weak"


def _build_evidence_clusters(items):
    clusters = []
    for item in items:
        keys = set(item.get("keys") or [])
        target = None
        if keys:
            for cluster in clusters:
                if keys & set(cluster.get("_keys") or []):
                    target = cluster
                    break
        if target is None:
            target = {"_keys": sorted(keys), "evidence": []}
            clusters.append(target)
        else:
            target["_keys"] = sorted(set(target.get("_keys") or []) | keys)[:48]
        target["evidence"].append(item)

    severity_rank = {"strong": 0, "medium": 1, "weak": 2}
    rendered = []
    for idx, cluster in enumerate(clusters, 1):
        evidence = cluster.get("evidence") or []
        severity = _cluster_severity(evidence)
        source_types = sorted({item.get("source_type") for item in evidence if item.get("source_type")})
        key_refs = [key for key in cluster.get("_keys") or [] if key.startswith(("figure:", "table:", "n="))]
        title = " / ".join(key_refs[:3]) if key_refs else (evidence[0].get("title") if evidence else "证据簇")
        rendered.append({
            "id": f"cluster-{idx}",
            "severity": severity,
            "title": _brief_text(title, 140),
            "source_types": source_types,
            "evidence_count": len(evidence),
            "keys": (cluster.get("_keys") or [])[:24],
            "summary": _brief_text("; ".join(item.get("title", "") for item in evidence[:4] if item.get("title")), 360),
            "evidence": evidence[:12],
        })
    rendered.sort(key=lambda item: (severity_rank.get(item.get("severity"), 9), -item.get("evidence_count", 0), item.get("title", "")))
    for idx, cluster in enumerate(rendered, 1):
        cluster["id"] = f"cluster-{idx}"
    return rendered[:40]


def build_evidence_chain_audit(full_text, file_entries, report, meta, stat_result):
    meta = meta or {}
    full_text = str(full_text or "")
    file_entries = file_entries or []
    claim_findings = _build_claim_chain_findings(full_text) if full_text.strip() else []
    items = []
    items.extend(_evidence_items_from_chain_findings(claim_findings))
    items.extend(_evidence_items_from_cross_file(meta))
    items.extend(_evidence_items_from_llm_report(report or {}))
    items.extend(_evidence_items_from_stat(stat_result or {}))
    items.extend(_evidence_items_from_reference(meta))
    items.extend(_evidence_items_from_resource(meta))
    items.extend(_evidence_items_from_image(meta))
    clusters = _build_evidence_clusters(items)
    note_scope = "单文件链条审查范围较窄；未发现可比较的跨文件材料。" if len(file_entries) <= 1 else "已结合全文、跨文件材料和现有审查信号进行证据簇聚合。"
    if not full_text.strip() and not items:
        status = "skipped"
        note = "缺少全文和可聚合审查信号；证据链审查已跳过。"
    else:
        status = "ok"
        note = f"{note_scope} 该结果用于人工复核排序，不等同于科研不端判断。"
    return {
        "status": status,
        "checked_files": len(file_entries or []),
        "cluster_count": len(clusters),
        "finding_count": len(claim_findings),
        "strong_count": sum(1 for item in clusters if item.get("severity") == "strong"),
        "medium_count": sum(1 for item in clusters if item.get("severity") == "medium"),
        "weak_count": sum(1 for item in clusters if item.get("severity") == "weak"),
        "clusters": clusters,
        "claim_chain_findings": claim_findings,
        "note": note,
    }


def format_evidence_chain_audit_markdown(audit):
    if audit is None:
        return []
    lines = [
        '<a id="evidence-chain"></a>',
        "## 🔗 证据链与证据簇审查",
        "",
        f"**状态**: {audit.get('status', 'N/A')}",
        f"**证据簇**: {audit.get('cluster_count', 0)}（强 {audit.get('strong_count', 0)} / 中 {audit.get('medium_count', 0)} / 弱 {audit.get('weak_count', 0)}）",
        f"**链条发现**: {audit.get('finding_count', 0)}",
        f"> {audit.get('note', '')}",
        "",
    ]
    findings = audit.get("claim_chain_findings") or []
    if findings:
        lines.append('<a id="evidence-chain-findings"></a>')
        lines.append("### Methods → Results → Abstract/Conclusion 链条发现")
        lines.append("")
        lines.append("| # | 级别 | 链条 | 类型 | 证据摘要 | 复核建议 |")
        lines.append("|---|------|------|------|----------|----------|")
        for idx, finding in enumerate(findings[:20], 1):
            evidence = " || ".join(
                part for part in (
                    finding.get("method_excerpt"),
                    finding.get("result_excerpt"),
                    finding.get("claim_excerpt"),
                )
                if part
            )
            lines.append(
                f"| {idx} | {_md_escape_cell(_cross_file_severity_label(finding.get('severity')))} | "
                f"{_md_escape_cell(finding.get('chain', ''))} | {_md_escape_cell(finding.get('type', ''))} | "
                f"{_md_escape_cell(_brief_text(evidence or finding.get('reason', ''), 360))} | "
                f"{_md_escape_cell(finding.get('manual_check', ''))} |"
            )
        lines.append("")
    clusters = audit.get("clusters") or []
    if clusters:
        lines.append('<a id="evidence-chain-clusters"></a>')
        lines.append("### 证据簇")
        lines.append("")
        lines.append("| # | 级别 | 主题 | 来源 | 证据数 | 摘要 |")
        lines.append("|---|------|------|------|--------|------|")
        for idx, cluster in enumerate(clusters[:30], 1):
            lines.append(
                f"| {idx} | {_md_escape_cell(_cross_file_severity_label(cluster.get('severity')))} | "
                f"{_md_escape_cell(cluster.get('title', ''))} | {_md_escape_cell(', '.join(cluster.get('source_types') or []))} | "
                f"{cluster.get('evidence_count', 0)} | {_md_escape_cell(_brief_text(cluster.get('summary', ''), 260))} |"
            )
    else:
        lines.append("> 未形成明确证据簇；仍建议人工核对关键结果链条。")
    lines.append("")
    return lines


def format_evidence_chain_audit_html(audit):
    if not audit:
        return ""
    findings = audit.get("claim_chain_findings") or []
    finding_cards = ""
    for idx, finding in enumerate(findings[:20], 1):
        evidence = " || ".join(
            part for part in (
                finding.get("method_excerpt"),
                finding.get("result_excerpt"),
                finding.get("claim_excerpt"),
            )
            if part
        )
        finding_cards += f"""
        <details class="cross-file-card evidence-chain-card" id="evidence-chain-finding-{idx}">
          <summary class="cross-file-summary">
            <span class="cross-file-rank">#{idx}</span>
            <span class="cross-file-severity cross-file-{_html_escape(finding.get('severity', ''))}">{_html_escape(_cross_file_severity_label(finding.get('severity')))}</span>
            <span class="cross-file-title">{_html_escape(finding.get('chain', ''))}</span>
            <span class="cross-file-reason">{_html_escape(_brief_text(finding.get('reason', ''), 150))}</span>
          </summary>
          <div class="cross-file-body">
            <p>{_html_escape(evidence)}</p>
            <p><strong>复核建议</strong>: {_html_escape(finding.get('manual_check', ''))}</p>
          </div>
        </details>"""
    cluster_cards = ""
    for idx, cluster in enumerate((audit.get("clusters") or [])[:30], 1):
        evidence_rows = ""
        for item in (cluster.get("evidence") or [])[:8]:
            evidence_rows += f"""
            <li><strong>{_html_escape(item.get('source_type', ''))}</strong> · {_html_escape(item.get('title', ''))}<br><small>{_html_escape(item.get('detail') or item.get('excerpt') or '')}</small></li>"""
        cluster_cards += f"""
        <details class="cross-file-card evidence-cluster-card" id="evidence-chain-cluster-{idx}">
          <summary class="cross-file-summary">
            <span class="cross-file-rank">#{idx}</span>
            <span class="cross-file-severity cross-file-{_html_escape(cluster.get('severity', ''))}">{_html_escape(_cross_file_severity_label(cluster.get('severity')))}</span>
            <span class="cross-file-title">{_html_escape(cluster.get('title', ''))}</span>
            <span class="cross-file-reason">{_html_escape(_brief_text(cluster.get('summary', ''), 150))}</span>
          </summary>
          <div class="cross-file-body">
            <p><strong>来源</strong>: {_html_escape(', '.join(cluster.get('source_types') or []))} · <strong>证据数</strong>: {cluster.get('evidence_count', 0)}</p>
            <ul>{evidence_rows}</ul>
          </div>
        </details>"""
    if not finding_cards:
        finding_cards = '<div class="muted">未发现明确 Methods/Results/Abstract/Conclusion 链条问题。</div>'
    if not cluster_cards:
        cluster_cards = '<div class="muted">未形成明确证据簇；仍建议人工核对关键结果链条。</div>'
    return f"""
  <div class="section cross-file-section evidence-chain-section" id="evidence-chain">
    <h2>证据链与证据簇审查</h2>
    <p class="section-hint">{_html_escape(audit.get('note', ''))}</p>
    <p><strong>状态</strong>: {_html_escape(audit.get('status', 'N/A'))} | <strong>证据簇</strong>: {audit.get('cluster_count', 0)}（强 {audit.get('strong_count', 0)} / 中 {audit.get('medium_count', 0)} / 弱 {audit.get('weak_count', 0)}） | <strong>链条发现</strong>: {audit.get('finding_count', 0)}</p>
    <h3 id="evidence-chain-findings">链条发现</h3>
    {finding_cards}
    <h3 id="evidence-chain-clusters">证据簇</h3>
    {cluster_cards}
  </div>"""
