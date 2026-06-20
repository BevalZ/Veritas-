"""Shared helper rules for risk scoring and report rendering."""


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


__all__ = [
    "_check_text_for_scoring",
    "_is_extraction_limited_check",
    "_should_downgrade_extraction_red_flag",
    "_soften_extraction_red_flag_language",
    "_soften_nonfinal_red_flag_language",
    "_downgrade_extraction_red_flags",
]
