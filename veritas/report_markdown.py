"""Top-level Markdown report renderer."""

import time

from .cross_file_consistency import format_cross_file_consistency_markdown
from .evidence_chain import format_evidence_chain_audit_markdown
from .image_reporting import format_image_audit_markdown
from .markdown_utils import _md_escape_cell
from .project_files import normalize_run_meta
from .reference_reporting import format_reference_audit_markdown
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_tags,
    _check_source_text,
    _is_suspicious_check,
    _merged_group_summary_text,
)
from .resource_reporting import format_resource_audit_markdown
from .review_overview import format_audit_action_summary_markdown, format_review_overview_markdown
from .runtime_metadata import runtime_utc_year
from .text_utils import _brief_text
from .versions import ADAPTER_VERSION, PROMPT_VERSION, RISK_RULE_VERSION, SCHEMA_VERSION

__all__ = ["format_report_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _markdown_report_metadata_lines(
    report,
    pdf_path,
    meta,
    prompt_version,
    schema_version,
    adapter_version,
    risk_rule_version,
    current_year,
):
    """Build the top-level Markdown metadata header lines."""
    artifact_type = meta.get("artifact_type") or "complete"
    artifact_label = "范围受限审查 (limited)" if artifact_type == "limited" else "完整审查 (complete)"
    runtime = meta.get("runtime") or {}
    lines = [
        f"# 📄 学术论文审查报告 [耿同学标准]",
        f"",
        f"**文件**: `{pdf_path}`",
        f"**产物类型**: {artifact_label}",
        f"**版本**: prompt={meta.get('prompt_version', prompt_version)}；schema={meta.get('schema_version', schema_version)}；adapter={meta.get('adapter_version', adapter_version)}；rules={meta.get('risk_rule_version', report.get('rule_version', risk_rule_version))}",
        f"**文件大小**: {meta.get('size_mb', 'N/A')} MB",
        f"**提取字符数**: {meta.get('total_chars', meta.get('chars', 'N/A'))}",
        f"**提取方式**: {meta.get('extraction_method', meta.get('source', 'N/A'))}",
    ]
    if meta.get("limited_reasons"):
        lines.append(f"**范围限制**: {'；'.join(meta.get('limited_reasons') or [])}")
    if meta.get("chunk_count") and meta["chunk_count"] > 1:
        lines.append(f"**审查方式**: 分块审查 | {meta['chunk_count']}块 | 单块上限{meta['chunk_size']}字符 | 重叠{meta['overlap']}字符")
    if meta.get("llm_coverage"):
        failed_chunks = meta.get("llm_failed_chunks") or []
        if meta.get("llm_partial_report") or failed_chunks:
            lines.append(f"**LLM覆盖率**: ⚠️ 部分报告，仅成功审查 {meta.get('llm_coverage')} 个分块；失败块: {failed_chunks or '无'}")
            lines.append("> ⚠️ 本报告只基于成功返回的LLM分块合并，未覆盖失败分块全文；结论只能作为阶段性结果，建议稍后用 `--llm-cache-only` 或更稳定API补跑。")
        else:
            lines.append(f"**LLM覆盖率**: ✅ {meta.get('llm_coverage')} 个分块全部成功")
    lines.append(f"**审查时间**: {runtime.get('local_time') or time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**运行时UTC年份**: {runtime.get('utc_year', current_year())}（用于未来发表年份等非LLM日期判断）")
    return lines


def _markdown_local_statistics_lines(stat_result):
    """Build the deterministic local-statistics Markdown table."""
    lines = [
        f"",
        f'<a id="local-statistics"></a>',
        f"## 📊 本地统计检测结果",
        f"| 检测项 | 结果 | 状态 |",
        f"|--------|------|------|",
        f"| Benford分布偏差 | {round(stat_result['benford_deviation'],3) if stat_result['benford_deviation'] else '样本不足'} | {stat_result['benford_status'] or 'N/A'} |",
        f"| p值数量/异常 | {stat_result['p_value_count']} / {stat_result['p_value_abnormal']}个>0.05 | {'⚠️异常' if stat_result['p_value_abnormal'] else '✅正常'} |",
        f"| 标准差提及 | {stat_result['sd_count']}处 | N/A |",
        f"| 提取数字数 | {stat_result['number_count']} | - |",
    ]

    if stat_result.get("number_consistency"):
        lines.append(f"| 数字自洽性 | {stat_result['number_consistency']} | ⚠️矛盾 |")

    lines.append("")
    return lines


def _markdown_report_summary_lines(report, risk_icons):
    """Build summary, risk, and score-breakdown lines for a complete Markdown report."""
    lines = [
        f"## 总评: {report.get('summary', 'N/A')}",
    ]
    risk = report.get("risk_level", "未知")
    lines.append(f"**复核优先级**: {risk_icons.get(risk, '⚪')} {risk}")
    lines.append(f"**证据风险分**: {report.get('detection_score', 0)} / 100 (辅助排序指标，越高表示越需要优先复核)")
    breakdown = report.get("score_breakdown") or {}
    if breakdown:
        lines.append(
            "**计分拆解**: "
            f"红旗 {breakdown.get('red_flags', 0)}；"
            f"证据型疑点 {breakdown.get('evidence_warnings', 0)}；"
            f"提取质量疑点 {breakdown.get('extraction_warnings', 0)}；"
            f"统计调整 {', '.join(breakdown.get('stat_adjustments') or []) or '无'}"
        )
    lines.append("")
    return lines


def _markdown_suspicious_finding_row(
    index,
    check,
    md_escape,
    check_source_tags,
    check_source_text,
    check_reason,
    brief_text,
):
    cat_item = f"{check.get('category', 'N/A')} / {check.get('item', 'N/A')}"
    return (
        f"| {index} | {md_escape(check.get('verdict', 'N/A'))} | {md_escape(' + '.join(check_source_tags(check)))} | "
        f"{md_escape(cat_item)} | "
        f"{md_escape(brief_text(check_source_text(check), 220) or '未提供明确原文摘录')} | "
        f"{md_escape(brief_text(check_reason(check), 220) or '未提供详细原因')} |"
    )


def _markdown_check_overview_row(index, check, md_escape, check_source_text, brief_text):
    return (
        f"| {index} | {md_escape(check.get('category', 'N/A'))} | "
        f"{md_escape(check.get('item', 'N/A'))} | "
        f"{md_escape(check.get('verdict', 'N/A'))} | "
        f"{md_escape(brief_text(check_source_text(check), 120) or '-')} |"
    )


def _markdown_check_detail_lines(index, check, check_source_text, check_reason, merged_group_summary):
    lines = [
        f'<a id="check-{index}"></a>',
        f"### {index}. {check.get('category', 'N/A')} - {check.get('item', 'N/A')} — {check.get('verdict', 'N/A')}",
    ]
    source = check_source_text(check)
    reason = check_reason(check)
    if source:
        lines.append(f"> **原文/证据摘录**: {source}")
    else:
        lines.append("> **原文/证据摘录**: LLM未提供明确原文摘录，请人工回查对应段落。")
    if reason:
        lines.append(f"\n**可疑原因/详细说明**：{reason}")
    merged_summary = merged_group_summary(check)
    if merged_summary:
        lines.append(f"\n**相近疑点统合**：{merged_summary}。完整成员见 HTML 展开区或 JSON `merged_group.members`。")
    lines.append("")
    return lines


def _markdown_check_sections_lines(
    checks,
    is_suspicious,
    md_escape,
    check_source_tags,
    check_source_text,
    check_reason,
    merged_group_summary,
    brief_text,
):
    if not checks:
        return []

    lines = []
    suspicious = [check for check in checks if is_suspicious(check)]
    lines.append('<a id="suspicious-findings"></a>')
    lines.append("## 🚩 可疑点证据汇总表")
    lines.append("")
    if suspicious:
        lines.append("| # | 判定 | 来源类型 | 分类/检查项 | 原文证据摘录 | 可疑原因 |")
        lines.append("|---|------|----------|-------------|--------------|----------|")
        for i, check in enumerate(suspicious[:5], 1):
            lines.append(
                _markdown_suspicious_finding_row(
                    i,
                    check,
                    md_escape,
                    check_source_tags,
                    check_source_text,
                    check_reason,
                    brief_text,
                )
            )
        if len(suspicious) > 5:
            lines.append("")
            lines.append(f"> 仅显示 Top 5 可疑点；完整 {len(suspicious)} 条见下方全部检查项和 HTML/JSON。")
    else:
        lines.append("> 未发现红旗/疑点项；仍建议人工核验关键数据、图表和引用。")
    lines.append("")

    lines.append('<a id="all-checks"></a>')
    lines.append("## 🔍 全部检查项概览")
    lines.append("")
    lines.append("| # | 分类 | 检查项 | 判定 | 证据摘要 |")
    lines.append("|---|------|--------|------|----------|")
    for i, check in enumerate(checks, 1):
        lines.append(_markdown_check_overview_row(i, check, md_escape, check_source_text, brief_text))
    lines.append("")

    lines.append('<a id="finding-details"></a>')
    lines.append("## 📋 逐条详细分析（含原文支撑）")
    lines.append("")
    for i, check in enumerate(checks, 1):
        lines.extend(_markdown_check_detail_lines(i, check, check_source_text, check_reason, merged_group_summary))
    return lines


def format_report_from_namespace(namespace, report, pdf_path, meta, stat_result):
    """Format the audit result as a Markdown report."""
    normalize_meta = _namespace_value(namespace, "normalize_run_meta", normalize_run_meta)
    meta = normalize_meta(meta, pdf_path)
    prompt_version = _namespace_value(namespace, "PROMPT_VERSION", PROMPT_VERSION)
    schema_version = _namespace_value(namespace, "SCHEMA_VERSION", SCHEMA_VERSION)
    adapter_version = _namespace_value(namespace, "ADAPTER_VERSION", ADAPTER_VERSION)
    risk_rule_version = _namespace_value(namespace, "RISK_RULE_VERSION", RISK_RULE_VERSION)
    current_year = _namespace_value(namespace, "runtime_utc_year", runtime_utc_year)
    review_overview = _namespace_value(namespace, "format_review_overview_markdown", format_review_overview_markdown)
    action_summary = _namespace_value(namespace, "format_audit_action_summary_markdown", format_audit_action_summary_markdown)
    evidence_chain = _namespace_value(namespace, "format_evidence_chain_audit_markdown", format_evidence_chain_audit_markdown)
    image_audit = _namespace_value(namespace, "format_image_audit_markdown", format_image_audit_markdown)
    cross_file = _namespace_value(namespace, "format_cross_file_consistency_markdown", format_cross_file_consistency_markdown)
    resource_audit = _namespace_value(namespace, "format_resource_audit_markdown", format_resource_audit_markdown)
    reference_audit = _namespace_value(namespace, "format_reference_audit_markdown", format_reference_audit_markdown)
    check_sort_key = _namespace_value(namespace, "_check_sort_key", _check_sort_key)
    is_suspicious = _namespace_value(namespace, "_is_suspicious_check", _is_suspicious_check)
    check_source_tags = _namespace_value(namespace, "_check_source_tags", _check_source_tags)
    check_source_text = _namespace_value(namespace, "_check_source_text", _check_source_text)
    check_reason = _namespace_value(namespace, "_check_reason", _check_reason)
    merged_group_summary = _namespace_value(namespace, "_merged_group_summary_text", _merged_group_summary_text)
    md_escape = _namespace_value(namespace, "_md_escape_cell", _md_escape_cell)
    brief_text = _namespace_value(namespace, "_brief_text", _brief_text)

    risk_icons = {"高": "🔴", "中": "🟡", "低": "🟢", "严重证据冲突": "⚫️"}
    lines = _markdown_report_metadata_lines(
        report,
        pdf_path,
        meta,
        prompt_version,
        schema_version,
        adapter_version,
        risk_rule_version,
        current_year,
    )

    if not report.get("parse_error"):
        lines.extend([""])
        lines.extend(review_overview(report, meta, stat_result))

    lines.extend(_markdown_local_statistics_lines(stat_result))

    if report.get("parse_error"):
        lines.append("## ⚠️ LLM报告解析失败（原始输出）")
        lines.append(f"```\n{report['raw_output']}\n```")
        return "\n".join(lines)

    lines.extend(_markdown_report_summary_lines(report, risk_icons))
    lines.extend(action_summary(report, meta, stat_result))

    checks = sorted(report.get("checks", []), key=check_sort_key)
    lines.extend(
        _markdown_check_sections_lines(
            checks,
            is_suspicious,
            md_escape,
            check_source_tags,
            check_source_text,
            check_reason,
            merged_group_summary,
            brief_text,
        )
    )

    if report.get("conclusion"):
        lines.append("## 📝 综合结论")
        lines.append(f"\n{report['conclusion']}")
        lines.append("")

    lines.extend(evidence_chain(meta.get("evidence_chain_audit")))
    lines.extend(image_audit(meta.get("image_audit")))
    lines.extend(cross_file(meta.get("cross_file_consistency_audit")))
    lines.extend(resource_audit(meta.get("resource_audit")))
    lines.extend(reference_audit(meta.get("reference_audit")))

    return "\n".join(lines)
