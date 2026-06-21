"""HTML report section builders."""

from .evidence_rendering import render_evidence_html, render_evidence_summary_html
from .html_utils import _html_escape
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_tags,
    _check_source_text,
    _check_suspicion_score,
    _check_verdict_class,
    _is_suspicious_check,
    _merged_group_html,
)
from .text_utils import _brief_text

__all__ = ["format_html_check_sections_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _format_html_parse_error_section(report, html_escape):
    return f"""
        <div class="section">
            <h2>LLM报告解析失败（原始输出）</h2>
            <pre class="error-block">{html_escape(report.get('raw_output', ''))}</pre>
        </div>"""


def _format_html_suspicious_card(
    index,
    check,
    html_escape,
    verdict_class_for,
    check_source_text,
    check_reason,
    check_suspicion_score,
    check_source_tags,
    merged_group_html,
    brief_text,
    evidence_html,
):
    verdict = check.get("verdict", "N/A")
    verdict_class = verdict_class_for(verdict)
    cat_item = f"{check.get('category', 'N/A')} / {check.get('item', 'N/A')}"
    source = check_source_text(check)
    reason = check_reason(check)
    brief = brief_text(reason or source or "未提供详细原因", 120)
    suspicion_score = check_suspicion_score(check)
    source_tags = " + ".join(check_source_tags(check))
    merged_html = merged_group_html(check)
    return f"""
            <details class="suspicion-card" id="suspicious-finding-{index}">
                <summary class="suspicion-summary">
                    <span class="suspicion-rank">#{index}</span>
                    <span class="{verdict_class} suspicion-verdict">{html_escape(verdict)}</span>
                    <span class="suspicion-title">{html_escape(cat_item)}</span>
                    <span class="suspicion-score">复核分 {suspicion_score}</span>
                    <span class="suspicion-brief"><strong>{html_escape(source_tags)}</strong> · {html_escape(brief)}</span>
                    <span class="summary-action">查看详情</span>
                </summary>
                <div class="suspicion-body">
                    {merged_html}
                    <div class="detail-evidence"><strong>原文/证据摘录</strong>{evidence_html(source or 'LLM未提供明确原文摘录，请人工回查对应段落。')}</div>
                    <div class="detail-text"><strong>可疑原因/详细说明</strong><p>{html_escape(reason or 'LLM未提供详细说明。')}</p></div>
                </div>
            </details>"""


def _format_html_check_table_row(
    index,
    check,
    html_escape,
    verdict_class_for,
    check_source_text,
    evidence_summary_html,
):
    verdict = check.get("verdict", "N/A")
    verdict_class = verdict_class_for(verdict)
    return f"""
            <tr>
                <td>{index}</td>
                <td>{html_escape(check.get('category', 'N/A'))}</td>
                <td>{html_escape(check.get('item', 'N/A'))}</td>
                <td><span class="{verdict_class}">{html_escape(verdict)}</span></td>
                <td class="evidence-cell">{evidence_summary_html(check_source_text(check), 120)}</td>
            </tr>"""


def format_html_check_sections_from_namespace(namespace, report):
    """Render LLM check summary/detail sections for the top-level HTML report."""
    html_escape = _namespace_value(namespace, "_html_escape", _html_escape)
    check_sort_key = _namespace_value(namespace, "_check_sort_key", _check_sort_key)
    is_suspicious = _namespace_value(namespace, "_is_suspicious_check", _is_suspicious_check)
    verdict_class_for = _namespace_value(namespace, "_check_verdict_class", _check_verdict_class)
    check_source_text = _namespace_value(namespace, "_check_source_text", _check_source_text)
    check_reason = _namespace_value(namespace, "_check_reason", _check_reason)
    check_suspicion_score = _namespace_value(namespace, "_check_suspicion_score", _check_suspicion_score)
    check_source_tags = _namespace_value(namespace, "_check_source_tags", _check_source_tags)
    merged_group_html = _namespace_value(namespace, "_merged_group_html", _merged_group_html)
    brief_text = _namespace_value(namespace, "_brief_text", _brief_text)
    evidence_html = _namespace_value(namespace, "render_evidence_html", render_evidence_html)
    evidence_summary_html = _namespace_value(namespace, "render_evidence_summary_html", render_evidence_summary_html)

    if report.get("parse_error"):
        checks_html = _format_html_parse_error_section(report, html_escape)
        return checks_html, ""

    checks = sorted(report.get("checks", []), key=check_sort_key)
    suspicious = [c for c in checks if is_suspicious(c)]

    suspicious_items = ""
    for i, c in enumerate(suspicious[:5], 1):
        suspicious_items += _format_html_suspicious_card(
            i,
            c,
            html_escape,
            verdict_class_for,
            check_source_text,
            check_reason,
            check_suspicion_score,
            check_source_tags,
            merged_group_html,
            brief_text,
            evidence_html,
        )
    if len(suspicious) > 5:
        suspicious_items += f'<div class="muted">仅显示 Top 5；完整 {len(suspicious)} 条见下方全部检查项。</div>'
    if not suspicious_items:
        suspicious_items = '<div class="muted">未发现红旗/疑点项；仍建议人工核验关键数据、图表和引用。</div>'

    checks_table_rows = ""
    for i, c in enumerate(checks, 1):
        checks_table_rows += _format_html_check_table_row(
            i,
            c,
            html_escape,
            verdict_class_for,
            check_source_text,
            evidence_summary_html,
        )

    detail_cards = ""
    for i, c in enumerate(checks, 1):
        verdict = c.get("verdict", "N/A")
        verdict_class = verdict_class_for(verdict)
        source = check_source_text(c)
        reason = check_reason(c)
        source_html = evidence_html(source or "LLM未提供明确原文摘录，请人工回查对应段落。")
        merged_html = merged_group_html(c)
        detail_cards += f"""
            <details class="detail-card" id="check-{i}">
                <summary class="detail-header detail-summary">
                    <span class="detail-num">#{i}</span>
                    <span class="detail-cat">{html_escape(c.get('category', 'N/A'))}</span>
                    <span class="detail-item">{html_escape(c.get('item', 'N/A'))}</span>
                    <span class="{verdict_class} detail-verdict">{html_escape(verdict)}</span>
                    <span class="detail-brief">{html_escape(brief_text(reason or source or '无摘要', 120))}</span>
                    <span class="summary-action">查看详情</span>
                </summary>
                <div class="detail-body">
                    {merged_html}
                    <div class="detail-evidence"><strong>原文/证据摘录</strong>{source_html}</div>
                    <div class="detail-text"><strong>可疑原因/详细说明</strong><p>{html_escape(reason or 'LLM未提供详细说明。')}</p></div>
                </div>
            </details>"""

    checks_html = f"""
        <div class="section evidence-summary" id="suspicious-findings">
            <h2>Top 可复核证据</h2>
            <p class="section-hint">按可复核性和证据强度排序；默认显示前5项，展开后查看原文证据、判断理由和相近疑点统合来源。</p>
            <div class="suspicion-list">{suspicious_items}</div>
        </div>
        <div class="section" id="all-checks">
            <h2>全部检查项概览</h2>
            <table class="checks-table">
                <thead><tr><th>#</th><th>分类</th><th>检查项</th><th>判定</th><th>证据摘要</th></tr></thead>
                <tbody>{checks_table_rows}</tbody>
            </table>
        </div>
        <div class="section" id="finding-details">
            <h2>逐条详细分析（含原文支撑）</h2>
            {detail_cards}
        </div>"""

    conclusion_html = ""
    if report.get("conclusion"):
        conclusion_html = f"""
            <div class="section conclusion-section">
                <h2>综合结论</h2>
                <p class="conclusion-text">{html_escape(report['conclusion'])}</p>
            </div>"""

    return checks_html, conclusion_html
