"""Review overview and action-priority report helpers."""

import re

from .html_utils import _html_escape
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_text,
    _check_suspicion_score,
    _is_suspicious_check,
)
from .text_utils import _brief_text

__all__ = [
    "build_audit_action_items",
    "format_audit_action_summary_markdown",
    "format_audit_action_summary_html",
    "build_review_overview",
    "format_review_overview_markdown",
    "format_review_overview_html",
]


def _md_escape_cell(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("|", "\\|")


def build_audit_action_items(report, meta, stat_result, limit=8):
    meta = meta or {}
    stat_result = stat_result or {}
    items = []
    evidence_chain_audit = meta.get("evidence_chain_audit") or {}
    strong_clusters = [cluster for cluster in (evidence_chain_audit.get("clusters") or []) if cluster.get("severity") == "strong"]
    if strong_clusters:
        top = strong_clusters[0]
        items.append({
            "score": 285,
            "source": "证据链与证据簇审查",
            "title": f"{len(strong_clusters)}个强证据簇需优先复核",
            "detail": _brief_text(
                f"{top.get('title')}: {top.get('summary')}。优先核对 Methods、Results、图表、补充材料和现有审查信号是否指向同一证据链。",
                220,
            ),
            "anchor": "evidence-chain-clusters",
        })
    elif evidence_chain_audit.get("cluster_count"):
        items.append({
            "score": 238,
            "source": "证据链与证据簇审查",
            "title": f"{evidence_chain_audit.get('cluster_count')}个证据簇需复核",
            "detail": "证据簇用于把孤立疑点合并为可人工核查的问题组；建议优先查看中等以上证据簇。",
            "anchor": "evidence-chain-clusters",
        })
    checks = sorted(report.get("checks", []) if isinstance(report, dict) else [], key=_check_sort_key)
    for check_idx, c in enumerate(checks, 1):
        if not _is_suspicious_check(c):
            continue
        items.append({
            "score": _check_suspicion_score(c),
            "source": "LLM语义审查",
            "title": f"{c.get('category', 'N/A')} / {c.get('item', 'N/A')}",
            "detail": _brief_text(_check_reason(c) or _check_source_text(c) or "需人工复核。", 180),
            "anchor": f"check-{check_idx}",
        })
    if stat_result.get("benford_status") and "高偏差" in str(stat_result.get("benford_status")):
        items.append({
            "score": 260,
            "source": "本地统计",
            "title": "Benford分布偏差较高",
            "detail": f"偏差={round(stat_result.get('benford_deviation') or 0, 3)}，建议核对原始数值来源和批量生成痕迹。",
            "anchor": "local-statistics",
        })
    reference_audit = meta.get("reference_audit") or {}
    if reference_audit.get("online_enabled"):
        bad_refs = []
        refs_by_index = {i + 1: ref for i, ref in enumerate(reference_audit.get("references", []))}
        for issue in reference_audit.get("issues", []):
            ref = refs_by_index.get(issue.get("index"), {})
            online = ref.get("online") or {}
            if online.get("online_status") in {"not_found", "weak", "error"}:
                bad_refs.append(issue.get("index"))
        if bad_refs:
            items.append({
                "score": 240,
                "source": "参考文献在线检索",
                "title": f"{len(bad_refs)}条参考文献在线证据不足",
                "detail": f"优先核对编号: {bad_refs[:10]}；检查DOI、题名、年份是否与数据库命中一致。",
                "anchor": "reference-audit",
            })
    resource_audit = meta.get("resource_audit") or {}
    if resource_audit.get("issues"):
        issues = resource_audit.get("issues") or []
        items.append({
            "score": 235,
            "source": "资源可用性校检",
            "title": f"{len(issues)}项代码仓库/在线资源需复核",
            "detail": "优先核对不可访问、格式错误或访问受限的代码仓库、Streamlit等论文声明资源。",
            "anchor": "resource-audit",
        })
    cross_file_audit = meta.get("cross_file_consistency_audit") or {}
    cross_findings = cross_file_audit.get("findings") or []
    if cross_findings:
        strong = cross_file_audit.get("strong_count", 0)
        medium = cross_file_audit.get("medium_count", 0)
        score = 255 if strong else 225
        items.append({
            "score": score,
            "source": "跨文件一致性审查",
            "title": f"{len(cross_findings)}项跨文件一致性疑点",
            "detail": f"强证据冲突 {strong} 项，中等疑点 {medium} 项；优先核对正文、补充材料和数据表中的样本量/分组/图表编号。",
            "anchor": "cross-file-consistency",
        })
    image_audit = meta.get("image_audit") or {}
    image_warnings = [img for img in image_audit.get("images", []) if img.get("risk") == "local_warning"]
    semantic_warnings = []
    detector_warnings = []
    for img in image_audit.get("images", []):
        sem = img.get("semantic") or {}
        if sem.get("reasonability") in {"需人工核对", "可疑"} or sem.get("status") == "error":
            semantic_warnings.append(img)
        detector = img.get("detector") or {}
        score = detector.get("score")
        if detector.get("status") == "ok" and score is not None and score >= 50:
            detector_warnings.append(img)
    if image_warnings or semantic_warnings or detector_warnings:
        items.append({
            "score": 230,
            "source": "图像检测",
            "title": f"{len(image_warnings)}张本地异常 / {len(semantic_warnings)}张需语义复核 / {len(detector_warnings)}张AI概率偏高",
            "detail": "查看 image_ai_review_manifest.html 中的自动imagedetector结果，并核对图像语义分析描述是否与论文图注一致。",
            "anchor": "image-audit",
        })
    items.sort(key=lambda item: (-item["score"], item["source"], item["title"]))
    selected = []
    used_sources = set()
    for item in items:
        if item["source"] in used_sources:
            continue
        selected.append(item)
        used_sources.add(item["source"])
        if len(selected) >= limit:
            return selected
    for item in items:
        if item in selected:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def format_audit_action_summary_markdown(report, meta, stat_result):
    items = build_audit_action_items(report, meta, stat_result)
    lines = ["## 🎯 行动优先级摘要", ""]
    if not items:
        lines.append("> 未形成高优先级行动项；仍建议按报告逐项抽查原文、图表和引用。")
        lines.append("")
        return lines
    lines.append("| 优先级 | 来源 | 事项 | 复核建议 |")
    lines.append("|--------|------|------|----------|")
    for idx, item in enumerate(items, 1):
        title = item["title"]
        if item.get("anchor"):
            title = f"[{title}](#{item['anchor']})"
        lines.append(
            f"| {idx} | {_md_escape_cell(item['source'])} | {_md_escape_cell(title)} | "
            f"{_md_escape_cell(item['detail'])} |"
        )
    lines.append("")
    return lines


def format_audit_action_summary_html(report, meta, stat_result):
    items = build_audit_action_items(report, meta, stat_result)
    if not items:
        content = '<p class="section-hint">未形成高优先级行动项；仍建议按报告逐项抽查原文、图表和引用。</p>'
    else:
        cards = ""
        for idx, item in enumerate(items, 1):
            title_html = _html_escape(item["title"])
            if item.get("anchor"):
                title_html = f'<a href="#{_html_escape(item["anchor"])}">{title_html}</a>'
            cards += f"""
            <div class="action-card">
              <span class="action-rank">#{idx}</span>
              <div>
                <strong>{title_html}</strong>
                <p>{_html_escape(item['detail'])}</p>
              </div>
              <span class="action-source">{_html_escape(item['source'])}</span>
            </div>"""
        content = f'<div class="action-list">{cards}</div>'
    return f"""
  <div class="section action-section">
    <h2>行动优先级摘要</h2>
    {content}
  </div>"""


def build_review_overview(report, meta, stat_result, action_limit=3):
    meta = meta or {}
    report = report or {}
    stat_result = stat_result or {}
    breakdown = report.get("score_breakdown") or {}
    checks = report.get("checks", []) if isinstance(report, dict) else []
    suspicious_count = sum(1 for check in checks if _is_suspicious_check(check))
    evidence_warnings = breakdown.get("evidence_warnings")
    if evidence_warnings is None:
        evidence_warnings = suspicious_count
    extraction_warnings = breakdown.get("extraction_warnings", 0)
    artifact_type = meta.get("artifact_type") or "complete"
    llm_coverage = meta.get("llm_coverage") or (
        f"{meta.get('llm_success_chunks')}/{meta.get('chunk_count')}"
        if meta.get("chunk_count") and meta.get("llm_success_chunks") is not None
        else "单块/未分块"
    )
    artifacts = meta.get("artifact_paths") or {}
    return {
        "report_type": artifact_type,
        "report_type_label": "范围受限审查 (limited)" if artifact_type == "limited" else "完整审查 (complete)",
        "risk_level": report.get("risk_level", "未知"),
        "detection_score": report.get("detection_score", 0),
        "red_flags": breakdown.get("red_flags", suspicious_count),
        "evidence_warnings": evidence_warnings,
        "extraction_warnings": extraction_warnings,
        "p_value_warnings": stat_result.get("p_value_abnormal", 0),
        "llm_coverage": llm_coverage,
        "llm_failed_chunks": meta.get("llm_failed_chunks") or [],
        "top_actions": build_audit_action_items(report, meta, stat_result, limit=action_limit),
        "artifact_paths": artifacts,
        "limited_reasons": meta.get("limited_reasons") or [],
        "completed": [
            "文本提取",
            "本地统计",
            "LLM语义审查",
            *("参考文献校检" for _ in [1] if meta.get("reference_audit") is not None),
            *("资源可用性校检" for _ in [1] if meta.get("resource_audit") is not None),
            *("跨文件一致性审查" for _ in [1] if meta.get("cross_file_consistency_audit") is not None),
            *("证据链审查" for _ in [1] if meta.get("evidence_chain_audit") is not None),
            *("图像审查" for _ in [1] if meta.get("image_audit") is not None),
        ],
    }


def format_review_overview_markdown(report, meta, stat_result):
    overview = build_review_overview(report, meta, stat_result)
    lines = [
        '<a id="review-overview"></a>',
        "## 复核概览",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 报告类型 | {_md_escape_cell(overview['report_type_label'])} |",
        f"| 复核优先级 | {_md_escape_cell(overview['risk_level'])} |",
        f"| 证据风险分 | {overview['detection_score']} / 100 |",
        f"| 红旗/证据/提取警告 | {overview['red_flags']} / {overview['evidence_warnings']} / {overview['extraction_warnings']} |",
        f"| LLM覆盖 | {_md_escape_cell(str(overview['llm_coverage']))} |",
        f"| 失败分块 | {_md_escape_cell(str(overview['llm_failed_chunks'] or '无'))} |",
    ]
    if overview["artifact_paths"]:
        paths = "；".join(f"{key}: {value}" for key, value in overview["artifact_paths"].items())
        lines.append(f"| 产物路径 | {_md_escape_cell(paths)} |")
    lines.append("")
    if overview["top_actions"]:
        lines.append("**Top 3 复核动作**")
        lines.append("")
        for idx, item in enumerate(overview["top_actions"], 1):
            title = item["title"]
            if item.get("anchor"):
                title = f"[{title}](#{item['anchor']})"
            lines.append(f"{idx}. {title} - {item['detail']}")
        lines.append("")
    if overview["report_type"] == "limited":
        lines.append('<a id="limitation-panel"></a>')
        lines.append("### 范围限制面板")
        lines.append("")
        lines.append("**限制原因**: " + ("；".join(overview["limited_reasons"]) if overview["limited_reasons"] else "未记录具体限制原因"))
        lines.append("")
        lines.append("**已完成**: " + "；".join(overview["completed"]))
        lines.append("")
    return lines


def format_review_overview_html(report, meta, stat_result):
    overview = build_review_overview(report, meta, stat_result)
    actions = ""
    for idx, item in enumerate(overview["top_actions"], 1):
        title = _html_escape(item["title"])
        if item.get("anchor"):
            title = f'<a href="#{_html_escape(item["anchor"])}">{title}</a>'
        actions += f"""
        <li><span>#{idx}</span><strong>{title}</strong><p>{_html_escape(item.get('detail', ''))}</p></li>"""
    if not actions:
        actions = "<li><strong>暂无高优先级动作</strong><p>建议按报告章节抽查原文、图表和引用。</p></li>"
    artifacts = ""
    for key, value in (overview.get("artifact_paths") or {}).items():
        artifacts += f"<li><strong>{_html_escape(key)}</strong>: {_html_escape(value)}</li>"
    if not artifacts:
        artifacts = "<li>最终产物路径将在写入后记录。</li>"
    limitation_panel = ""
    if overview["report_type"] == "limited":
        reasons = overview["limited_reasons"] or ["未记录具体限制原因"]
        reason_items = "".join(f"<li>{_html_escape(reason)}</li>" for reason in reasons)
        completed_items = "".join(f"<li>{_html_escape(item)}</li>" for item in overview["completed"])
        limitation_panel = f"""
  <div class="section limitation-panel" id="limitation-panel">
    <h2>范围限制面板</h2>
    <div class="limitation-grid">
      <div><strong>限制来源</strong><ul>{reason_items}</ul></div>
      <div><strong>已完成审查</strong><ul>{completed_items}</ul></div>
    </div>
  </div>"""
    return f"""
  <div class="section review-overview" id="review-overview">
    <h2>复核概览</h2>
    <div class="overview-grid">
      <div><span>报告类型</span><strong>{_html_escape(overview['report_type_label'])}</strong></div>
      <div><span>复核优先级</span><strong>{_html_escape(overview['risk_level'])}</strong></div>
      <div><span>证据风险分</span><strong>{overview['detection_score']} / 100</strong></div>
      <div><span>红旗 / 证据警告 / 提取警告</span><strong>{overview['red_flags']} / {overview['evidence_warnings']} / {overview['extraction_warnings']}</strong></div>
      <div><span>LLM覆盖</span><strong>{_html_escape(overview['llm_coverage'])}</strong></div>
      <div><span>失败分块</span><strong>{_html_escape(overview['llm_failed_chunks'] or '无')}</strong></div>
    </div>
    <div class="overview-columns">
      <div>
        <h3>Top 3 复核动作</h3>
        <ol class="overview-actions">{actions}</ol>
      </div>
      <div>
        <h3>产物路径</h3>
        <ul class="artifact-list">{artifacts}</ul>
      </div>
    </div>
  </div>
  {limitation_panel}"""
