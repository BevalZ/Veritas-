"""Shared helper rules for risk scoring and report rendering."""

import re
from typing import Any, Dict

from .text_utils import _brief_text, _token_similarity


def _check_text_for_scoring(c):
    return " ".join(
        str(c.get(key, "") or "")
        for key in ("category", "item", "source_text", "quote", "evidence", "reason", "detail", "analysis", "explanation")
    )


def _is_extraction_limited_check(c):
    if c.get("_verdict_adjusted") == "extraction_red_flag_downgraded":
        return True
    text = _check_text_for_scoring(c)
    extraction_terms = (
        "OCR", "提取", "格式", "错位", "断裂", "表头缺失", "列名缺失", "行列",
        "表格结构", "原PDF", "人工核对原", "无法判定", "不可直接用于", "不构成造假",
    )
    evidence_terms = (
        "不一致", "矛盾", "冲突", "样本量", "下采样", "AUC", "p值异常",
        "重复", "复用", "拼接", "篡改", "置信区间", "均值", "标准差",
    )
    if not any(term in text for term in extraction_terms):
        return False
    if any(term in text for term in evidence_terms):
        return False
    category = str(c.get("category", ""))
    item = str(c.get("item", ""))
    return ("表" in item) or ("OCR" in item) or ("图" in category) or ("数据" in category)


def _should_downgrade_extraction_red_flag(c):
    verdict = str(c.get("verdict", ""))
    if "红旗" not in verdict:
        return False
    text = _check_text_for_scoring(c)
    extraction = any(term in text for term in ("OCR", "提取", "原PDF", "MinerU", "<tr>", "<td>"))
    uncertainty = any(term in text for term in ("可能", "疑似", "需人工核对", "确认", "错位", "格式"))
    table_based = any(term in text for term in ("表格", "行", "列", "数字序列", "<tr>", "<td>"))
    definitive_cross_evidence = any(term in text for term in ("正文明确矛盾", "跨正文/表格矛盾", "原文明确写明", "同一指标跨正文"))
    return extraction and uncertainty and table_based and not definitive_cross_evidence


def _soften_extraction_red_flag_language(text):
    """Remove assertive red-flag language after an OCR/table finding is downgraded."""
    softened = str(text or "")
    replacements = {
        "判定为红旗": "原分段审查曾判为红旗；现因证据依赖未核实的表格提取结果，仅作为疑点",
        "构成🚩红旗": "需要升级为严重问题",
        "构成红旗": "可能构成需复核疑点",
        "作为红旗": "作为严重问题",
        "标记为红旗": "标记为需复核疑点",
        "升级为红旗": "在原PDF确认后再决定是否升级",
        "建议退修或拒稿": "建议先核对原PDF/原始数据后再决定处理方式",
        "建议拒稿": "建议先核对原PDF/原始数据后再决定处理方式",
    }
    for old, new in replacements.items():
        softened = softened.replace(old, new)
    return softened


def _soften_nonfinal_red_flag_language(text):
    softened = str(text or "")
    replacements = {
        "判定为红旗": "判定为严重问题",
        "构成🚩红旗": "需要升级为严重问题",
        "构成红旗": "需要升级为严重问题",
        "作为红旗": "作为严重问题",
        "升级为红旗": "升级为严重问题",
    }
    for old, new in replacements.items():
        softened = softened.replace(old, new)
    return softened


def _downgrade_extraction_red_flags(checks):
    for check in checks:
        if not _should_downgrade_extraction_red_flag(check):
            if "红旗" not in str(check.get("verdict", "")):
                for key in ("detail", "reason", "analysis", "explanation"):
                    if check.get(key):
                        check[key] = _soften_nonfinal_red_flag_language(check.get(key))
            continue
        check["verdict"] = "⚠️疑点"
        check["_verdict_adjusted"] = "extraction_red_flag_downgraded"
        note = "自动降级：该项基于MinerU/OCR提取表格，且存在提取错位或需核对原PDF的不确定性；原PDF确认前不作为红旗。"
        detail = _soften_extraction_red_flag_language(check.get("detail") or check.get("reason") or "")
        check["detail"] = f"{note} {detail}".strip()
    return checks


_CHECK_STOPWORDS = {
    "数据", "结果", "方法", "论文", "文献", "引用", "参考", "检查", "问题", "疑点", "红旗",
    "可能", "存在", "出现", "显示", "发现", "需要", "核对", "一致", "不一致", "异常",
    "the", "and", "for", "with", "from", "that", "this", "into", "using", "used",
}


def _normalize_check_terms(value: str) -> set:
    text = str(value or "").lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text)
    return {token for token in tokens if len(token) >= 2 and token not in _CHECK_STOPWORDS}


def _check_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    a_terms = _normalize_check_terms(" ".join(str(a.get(key, "")) for key in ("category", "item", "source", "evidence", "reason")))
    b_terms = _normalize_check_terms(" ".join(str(b.get(key, "")) for key in ("category", "item", "source", "evidence", "reason")))
    if not a_terms or not b_terms:
        return 0.0
    overlap = len(a_terms & b_terms)
    return overlap / max(1, min(len(a_terms), len(b_terms)))


def _check_merge_key(check: Dict[str, Any]):
    return (
        re.sub(r"\s+", "", str(check.get("category", "")).lower()),
        re.sub(r"\s+", "", str(check.get("item", "")).lower()),
    )


def _check_severity(verdict: str) -> int:
    if "红旗" in str(verdict):
        return 3
    if "疑点" in str(verdict):
        return 2
    if "通过" in str(verdict):
        return 1
    return 0


def _same_or_similar_check(existing: Dict[str, Any], new: Dict[str, Any]) -> bool:
    if _check_merge_key(existing) == _check_merge_key(new):
        return True
    if _is_extraction_limited_check(existing) or _is_extraction_limited_check(new):
        return False
    category_a = str(existing.get("category") or "")
    category_b = str(new.get("category") or "")
    if category_a and category_b and category_a != category_b and _token_similarity(category_a, category_b) < 0.5:
        return False
    return _check_similarity(existing, new) >= 0.68


def _append_unique_evidence(existing: Dict[str, Any], new: Dict[str, Any], chunk_idx: int):
    evidence = str(new.get("evidence") or "").strip()
    if evidence and evidence not in str(existing.get("evidence") or ""):
        prefix = str(existing.get("evidence") or "").strip()
        suffix = f"[第{chunk_idx + 1}段补充: {evidence}]"
        existing["evidence"] = f"{prefix} {suffix}".strip()


def _check_member_summary(check: Dict[str, Any], similarity=None) -> Dict[str, Any]:
    member = {
        "chunk": check.get("_source_chunk"),
        "category": check.get("category"),
        "item": check.get("item"),
        "verdict": check.get("verdict"),
        "source": check.get("source"),
        "source_text": _brief_text(check.get("source_text") or "", 500),
        "evidence": _brief_text(check.get("evidence") or "", 500),
        "reason": _brief_text(check.get("reason") or check.get("detail") or "", 500),
        "recommendation": _brief_text(check.get("recommendation") or "", 300),
        "confidence": check.get("confidence"),
    }
    if check.get("_verdict_adjusted"):
        member["_verdict_adjusted"] = check.get("_verdict_adjusted")
    if similarity is not None:
        member["merge_similarity"] = similarity
    return {key: value for key, value in member.items() if value not in (None, "")}


def _merge_check_into(existing: Dict[str, Any], new: Dict[str, Any], chunk_idx: int):
    similarity = _check_similarity(existing, new)
    old_severity = _check_severity(existing.get("verdict", ""))
    new_severity = _check_severity(new.get("verdict", ""))
    if _check_merge_key(existing) != _check_merge_key(new) or similarity >= 0.68:
        group = existing.setdefault("merged_group", {
            "count": 1,
            "source_chunks": list(existing.get("_source_chunks") or [existing.get("_source_chunk")]),
            "items": [existing.get("item")],
            "merge_reason": "category_item_or_evidence_similarity",
            "members": [_check_member_summary(existing, similarity=1.0)],
        })
        group["members"].append(_check_member_summary(new, similarity=round(similarity, 3)))
        group["count"] = len(group["members"])
        if new.get("item") and new.get("item") not in group["items"]:
            group["items"].append(new.get("item"))
        source_chunk = new.get("_source_chunk", chunk_idx + 1)
        if source_chunk not in group["source_chunks"]:
            group["source_chunks"].append(source_chunk)
    if new_severity > old_severity:
        for key in ("verdict", "source", "source_text", "evidence", "reason", "recommendation", "detail", "confidence"):
            if new.get(key):
                existing[key] = new.get(key)
    else:
        _append_unique_evidence(existing, new, chunk_idx)
    sources = list(existing.get("_source_chunks") or [])
    source_chunk = new.get("_source_chunk", chunk_idx + 1)
    if source_chunk not in sources:
        sources.append(source_chunk)
    existing["_source_chunks"] = sources
    if _check_merge_key(existing) != _check_merge_key(new) or similarity >= 0.68:
        existing["_merged_similar_count"] = int(existing.get("_merged_similar_count", 1)) + 1
        items = list(existing.get("_merged_similar_items") or [existing.get("item")])
        if new.get("item") and new.get("item") not in items:
            items.append(new.get("item"))
        existing["_merged_similar_items"] = items[:8]


def _risk_index(level):
    return {"低": 0, "中": 1, "高": 2, "严重证据冲突": 3}.get(str(level), 0)


def _max_risk(*levels):
    return max((level for level in levels if level), key=_risk_index, default="低")


def _check_label_for_summary(check):
    category = str(check.get("category") or "未分类")
    item = str(check.get("item") or "未命名检查项")
    return f"{category}/{item}"


def _brief_check_list(checks, limit=4):
    labels = [_check_label_for_summary(check) for check in checks[:limit]]
    if len(checks) > limit:
        labels.append(f"等{len(checks)}项")
    return "、".join(labels) if labels else "无"


def _build_merged_summary(total_reports, risk_level, red_flags, evidence_warnings, extraction_warnings):
    parts = [
        f"[合并{total_reports}段审查] 复核优先级{risk_level}",
        f"红旗{red_flags}项",
        f"证据型疑点{evidence_warnings}项",
        f"提取质量疑点{extraction_warnings}项",
    ]
    if red_flags == 0 and extraction_warnings:
        parts.append("主要问题集中在需回查原PDF/原始表格的提取质量与数据自洽性线索")
    elif red_flags == 0:
        parts.append("未发现可直接保留为红旗的检查项")
    return "；".join(parts) + "。"


def _build_merged_conclusion(reports, all_checks, risk_level, red_flags, evidence_warnings, extraction_warnings, stat_adjustments):
    valid_reports = [report for report in reports if not report.get("parse_error")]
    warning_checks = [check for check in all_checks if "疑点" in str(check.get("verdict", ""))]
    downgraded = [check for check in all_checks if check.get("_verdict_adjusted") == "extraction_red_flag_downgraded"]
    evidence_checks = [check for check in warning_checks if not _is_extraction_limited_check(check)]
    red_flag_checks = [check for check in all_checks if "红旗" in str(check.get("verdict", ""))]

    parts = [
        f"综合结论：合并{len(valid_reports) or len(reports)}段审查后，当前复核优先级为{risk_level}；最终结论以合并后检查项为准，而不是逐段LLM原始措辞。",
    ]
    if red_flags:
        parts.append(f"保留红旗{red_flags}项，优先核对：{_brief_check_list(red_flag_checks)}。")
    else:
        parts.append("未发现可直接保留为红旗的检查项；未核实的MinerU/OCR表格异常不应直接表述为学术不端。")
    if evidence_warnings:
        parts.append(f"证据型疑点{evidence_warnings}项，优先复核：{_brief_check_list(evidence_checks)}。")
    if extraction_warnings:
        parts.append(f"提取质量疑点{extraction_warnings}项，主要来自表格/OCR/MinerU结构化提取不清晰；需对照原PDF、补充材料或原始数据表确认后再升级。")
    if downgraded:
        parts.append(f"其中{len(downgraded)}项逐段审查中的红旗表述已自动降级，因为证据依赖表格提取结果且存在错位、截断或需人工核对的不确定性。")
    if "benford_high_deviation" in (stat_adjustments or []):
        parts.append("Benford分布偏差较高，仅作为批量数值复核线索；在缺少表格语义和原始数据上下文时，不单独构成造假结论。")
    if "p_value_abnormal" in (stat_adjustments or []):
        parts.append("p值异常计数提示需核对统计报告，但仍应回到原文方法、样本量和多重比较设置判断。")
    parts.append("建议复核顺序：先展开可疑点详情核对原PDF表格/补充材料，再查看图像检测清单，最后检查参考文献真实性校检结果。")
    return "\n\n".join(parts)


__all__ = [
    "_check_text_for_scoring",
    "_is_extraction_limited_check",
    "_should_downgrade_extraction_red_flag",
    "_soften_extraction_red_flag_language",
    "_soften_nonfinal_red_flag_language",
    "_downgrade_extraction_red_flags",
    "_CHECK_STOPWORDS",
    "_normalize_check_terms",
    "_check_similarity",
    "_check_merge_key",
    "_check_severity",
    "_same_or_similar_check",
    "_append_unique_evidence",
    "_check_member_summary",
    "_merge_check_into",
    "_risk_index",
    "_max_risk",
    "_check_label_for_summary",
    "_brief_check_list",
    "_build_merged_summary",
    "_build_merged_conclusion",
]
