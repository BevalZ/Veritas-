"""Deterministic report check scoring and display helpers."""

import html
import json
import re
from typing import Any, Dict, List

from .evidence_rendering import _clean_mineru_table_block
from .html_utils import _html_escape
from .report_schema import _json_string_unescape
from .risk_rule_helpers import _check_text_blob, _is_extraction_limited_check
from .text_utils import _brief_text

__all__ = [
    "_is_suspicious_check",
    "_check_suspicion_score",
    "_check_source_tags",
    "_merged_group_summary_text",
    "_merged_group_html",
    "_check_sort_key",
    "_check_verdict_class",
    "_check_source_text",
    "_sanitize_reason_text",
    "_check_reason",
]


def _is_suspicious_check(c):
    verdict = str(c.get("verdict", ""))
    return ("红旗" in verdict) or ("疑点" in verdict) or ("可疑" in verdict)


def _check_suspicion_score(c):
    """Higher score means the finding should be reviewed earlier."""
    verdict = str(c.get("verdict", ""))
    text = " ".join(
        str(c.get(k, "") or "")
        for k in ("category", "item", "source_text", "quote", "evidence", "reason", "detail", "analysis", "explanation")
    )

    if "红旗" in verdict:
        score = 300
    elif "疑点" in verdict or "可疑" in verdict:
        score = 200
    elif "通过" in verdict:
        score = 0
    else:
        score = 100

    high_terms = (
        "造假", "伪造", "篡改", "捏造", "复制粘贴", "严重", "重大", "直接矛盾",
        "明显矛盾", "无法复现", "不可靠", "否决", "致命", "必须公开", "数据真实性",
    )
    medium_terms = (
        "矛盾", "异常", "重复", "缺失", "不一致", "过拟合", "无验证", "样本量",
        "p值", "多重比较", "利益冲突", "方法论缺陷",
    )
    low_terms = (
        "OCR", "提取", "人工核对", "原PDF", "表格结构", "暂判", "无法判定",
        "不宜判定", "无理由认定", "可能", "需确认",
    )

    score += sum(18 for term in high_terms if term in text)
    score += sum(8 for term in medium_terms if term in text)
    score -= sum(10 for term in low_terms if term in text)

    return max(score, 0)


def _check_source_tags(c: Dict[str, Any]) -> List[str]:
    text = _check_text_blob(c).lower()
    tags = []
    if c.get("_runtime_year_check"):
        tags.append("本地规则")
    if any(term in text for term in ("crossref", "openalex", "pubmed", "doi", "在线", "元数据")):
        tags.append("在线核验")
    if any(term in text for term in ("imagedetector", "ai概率", "ai probability")):
        tags.append("imagedetector")
    if any(term in text for term in ("图像语义", "visible_text", "semantic", "多模态")):
        tags.append("图像语义")
    if any(term in text for term in ("benford", "p值", "p-value", "统计")):
        tags.append("统计线索")
    if _is_extraction_limited_check(c):
        tags.append("MinerU/OCR提取")
    if not tags:
        tags.append("LLM语义")
    return list(dict.fromkeys(tags))


def _merged_group_summary_text(c: Dict[str, Any]) -> str:
    group = c.get("merged_group") or {}
    if not group:
        return ""
    chunks = "/".join(str(item) for item in group.get("source_chunks") or [])
    items = "、".join(str(item) for item in (group.get("items") or [])[:5] if item)
    return f"已合并 {group.get('count', 0)} 条相近疑点；来源分块: {chunks or 'N/A'}；原始项: {items or 'N/A'}"


def _merged_group_html(c: Dict[str, Any]) -> str:
    group = c.get("merged_group") or {}
    if not group:
        return ""
    rows = ""
    for idx, member in enumerate(group.get("members") or [], 1):
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td>{_html_escape(member.get('chunk', '-'))}</td>
          <td>{_html_escape(member.get('item', '-'))}</td>
          <td>{_html_escape(member.get('verdict', '-'))}</td>
          <td>{_html_escape(_brief_text(member.get('evidence') or member.get('source_text') or '', 160))}</td>
        </tr>"""
    return f"""
    <details class="merged-group">
      <summary>{_html_escape(_merged_group_summary_text(c))}</summary>
      <table>
        <thead><tr><th>#</th><th>分块</th><th>原始项</th><th>原判定</th><th>证据摘要</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </details>"""


def _check_sort_key(c):
    return (-_check_suspicion_score(c), str(c.get("category", "")), str(c.get("item", "")))


def _check_verdict_class(verdict):
    verdict = str(verdict or "")
    if "红旗" in verdict:
        return "verdict-red"
    if "疑点" in verdict or "可疑" in verdict:
        return "verdict-yellow"
    return "verdict-green"


def _check_source_text(c):
    """Extract source evidence text from known LLM finding fields."""
    for k in ("source_text", "quote", "original_text", "原文", "原文摘录", "evidence"):
        v = c.get(k)
        if isinstance(v, (list, tuple)):
            v = "；".join(str(x) for x in v if x)
        if v:
            return str(v)
    return ""


def _sanitize_reason_text(text):
    """Reason/detail fields are prose only; strip nested JSON and table markup noise."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    extracted = []
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        for key in ("summary", "reason", "detail", "analysis", "explanation", "conclusion"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                extracted.append(value)
        for check in parsed.get("checks", []) if isinstance(parsed.get("checks"), list) else []:
            if not isinstance(check, dict):
                continue
            for key in ("reason", "detail", "analysis", "explanation"):
                value = check.get(key)
                if isinstance(value, str) and value.strip():
                    extracted.append(value)
    elif raw.lstrip().startswith("{") and ('"checks"' in raw or '"summary"' in raw):
        for key in ("summary", "reason", "detail", "analysis", "explanation", "conclusion"):
            for match in re.finditer(rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"', raw):
                extracted.append(_json_string_unescape(match.group(1)))

    text = " ".join(extracted) if extracted else raw
    had_table_noise = bool(re.search(r"\[\[TABLE_|<\s*/?\s*t[rdh]\b|&lt;\s*/?\s*t[rdh]\b", text, flags=re.I))
    text = html.unescape(text)
    text = _clean_mineru_table_block(text)
    text = re.sub(r"\[\[/?(?:BLOCK|FIGURE)[^\]]*\]\]", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\b(?:source_text|evidence|checks|summary|risk_level|detection_score|verdict)\b\s*[:：]?", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;，；。")

    if had_table_noise:
        prefix = "表格原文已在证据区渲染；此处仅保留文字判断。"
        if text:
            return prefix + " " + _brief_text(text, 520)
        return prefix + " 请人工核对原PDF表格。"
    return _brief_text(text, 700)


def _check_reason(c):
    """Extract suspicious reason/detail text from known LLM finding fields."""
    for k in ("detail", "reason", "analysis", "explanation", "说明"):
        v = c.get(k)
        if v:
            return _sanitize_reason_text(v)
    return ""
