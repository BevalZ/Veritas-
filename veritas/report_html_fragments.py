"""Small HTML report fragment builders."""

from .html_utils import _html_escape

__all__ = [
    "build_html_report_body_from_namespace",
    "build_html_report_context_from_namespace",
    "build_html_report_head",
    "build_html_status_fragments_from_namespace",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def build_html_status_fragments_from_namespace(namespace, report, meta, stat_result):
    """Build status fragments used by the top-level HTML report."""
    html_escape = _namespace_value(namespace, "_html_escape", _html_escape)

    limited_notice = ""
    if meta.get("limited_reasons"):
        limited_notice = f"""
  <div class="section coverage-warning">
    <h2>范围受限审查</h2>
    <p>{html_escape('；'.join(meta.get('limited_reasons') or []))}</p>
  </div>"""

    chunk_info = ""
    if meta.get("chunk_count") and meta["chunk_count"] > 1:
        chunk_info = f"""
        <div class="meta-item">
            <span>审查方式</span>
            <strong>分块审查 · {meta['chunk_count']}块 · 单块{meta['chunk_size']}字符 · 重叠{meta['overlap']}字符</strong>
        </div>"""

    number_consistency = ""
    if stat_result.get("number_consistency"):
        number_consistency = f"""
        <tr>
            <td>数字自洽性</td>
            <td>{stat_result['number_consistency']}</td>
            <td><span class="status-warn">⚠️ 矛盾</span></td>
        </tr>"""

    coverage_banner = ""
    if meta.get("llm_coverage"):
        failed_chunks = meta.get("llm_failed_chunks") or []
        if meta.get("llm_partial_report") or failed_chunks:
            coverage_banner = f"""
  <div class="section coverage-warning">
    <h2>LLM覆盖不足</h2>
    <p><strong>成功审查分块</strong>: {html_escape(meta.get('llm_coverage'))}</p>
    <p><strong>失败块</strong>: {html_escape(failed_chunks or '无')}</p>
    <p>本报告只基于成功返回的LLM分块合并，未覆盖失败分块全文；结论只能作为阶段性结果。建议稍后使用 <code>--llm-cache-only</code> 复用成功缓存，或切换更稳定API补跑。</p>
  </div>"""
        else:
            coverage_banner = f"""
  <div class="section coverage-ok">
    <h2>LLM覆盖率</h2>
    <p>{html_escape(meta.get('llm_coverage'))} 个分块全部成功。</p>
  </div>"""

    breakdown = report.get("score_breakdown") or {}
    score_breakdown_html = ""
    if breakdown:
        score_breakdown_html = f"""
      <div class="score-breakdown">
        红旗 {breakdown.get('red_flags', 0)} · 证据型疑点 {breakdown.get('evidence_warnings', 0)} · 提取质量疑点 {breakdown.get('extraction_warnings', 0)} · 统计调整 {html_escape(', '.join(breakdown.get('stat_adjustments') or []) or '无')}
      </div>"""

    return {
        "limited_notice": limited_notice,
        "chunk_info": chunk_info,
        "number_consistency": number_consistency,
        "coverage_banner": coverage_banner,
        "score_breakdown_html": score_breakdown_html,
    }


def build_html_report_head(risk_color):
    """Build the top-level HTML report head and CSS."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>学术论文审查报告</title>
<style>
  :root {{
    --bg: #f7f3ec;
    --paper: #fffdf8;
    --surface: #fffaf1;
    --surface2: #f3eadc;
    --text: #2b241d;
    --text-muted: #7b7065;
    --accent: #c15f3c;
    --accent2: #2f6f73;
    --border: #e4d8c8;
    --red: #b42318;
    --yellow: #b7791f;
    --green: #2f7d50;
    --shadow: 0 22px 70px rgba(61, 45, 31, 0.10);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
    background: #f6f6f6;
    color: var(--text);
    line-height: 1.6;
    padding: 28px 20px;
  }}
  .container {{ max-width: 1120px; margin: 0 auto; }}
  .header {{
    background: rgba(255,253,248,0.86);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 36px;
    margin-bottom: 28px;
    text-align: center;
    box-shadow: none;
  }}
  .header h1 {{ font-size: 32px; margin-bottom: 18px; letter-spacing: 0; }}
  .risk-badge {{
    display: inline-block;
    font-size: 22px;
    font-weight: 700;
    padding: 8px 24px;
    border-radius: 999px;
    color: #fff;
    background: {risk_color};
    margin: 8px 0;
  }}
  .artifact-badge {{
    display: inline-block;
    border-radius: 6px;
    padding: 7px 10px;
    color: #fff;
    font-weight: 800;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 24px;
    text-align: left;
    margin-top: 16px;
    font-size: 14px;
    color: var(--text-muted);
  }}
  .meta-grid strong {{ color: var(--text); }}
  .section {{
    background: rgba(255,253,248,0.88);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 22px;
    box-shadow: 0 10px 34px rgba(61, 45, 31, 0.06);
  }}
  .section h2 {{
    font-size: 20px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--surface2); color: var(--text-muted); font-weight: 650; text-transform: uppercase; font-size: 12px; }}
  tr:hover {{ background: rgba(193,95,60,0.05); }}
  .status-ok {{ color: var(--green); font-weight: 600; }}
  .status-warn {{ color: var(--yellow); font-weight: 600; }}
  .verdict-red {{ color: var(--red); font-weight: 700; }}
  .verdict-yellow {{ color: var(--yellow); font-weight: 700; }}
  .verdict-green {{ color: var(--green); font-weight: 700; }}
  .detail-card {{
    background: var(--surface2);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 4px solid var(--accent);
  }}
  .detail-card[open] {{ background: #f8efe2; }}
  .detail-header {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .detail-summary {{ cursor: pointer; list-style: none; }}
  .detail-summary::-webkit-details-marker {{ display: none; }}
  .detail-summary::after {{
    content: "展开详情";
    margin-left: auto;
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
  }}
  .detail-card[open] .detail-summary::after {{ content: "收起详情"; }}
  .section-hint {{ color: var(--text-muted); margin: -6px 0 14px; font-size: 14px; }}
  .evidence-summary {{ border-left: 4px solid var(--red); }}
  .suspicion-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .suspicion-card {{
    background: #fff8ed;
    border: 1px solid var(--border);
    border-left: 4px solid var(--red);
    border-radius: 8px;
    padding: 12px 14px;
  }}
  .suspicion-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 44px minmax(76px, 120px) minmax(180px, 1fr) auto;
    gap: 8px 12px;
    align-items: center;
  }}
  .suspicion-summary::-webkit-details-marker {{ display: none; }}
  .suspicion-summary::after {{
    content: "展开详情";
    grid-column: 4;
    grid-row: 2;
    justify-self: end;
    color: var(--accent);
    font-size: 12px;
    font-weight: 700;
  }}
  .suspicion-card[open] .suspicion-summary::after {{ content: "收起详情"; }}
  .suspicion-rank {{
    background: rgba(248,113,113,0.16);
    color: var(--red);
    border-radius: 999px;
    padding: 4px 8px;
    text-align: center;
    font-weight: 800;
    font-size: 13px;
  }}
  .suspicion-title {{
    font-weight: 700;
    color: var(--text);
    overflow-wrap: anywhere;
  }}
  .suspicion-score {{
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
  }}
  .suspicion-brief {{
    grid-column: 2 / 4;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.45;
    overflow-wrap: anywhere;
  }}
  .suspicion-body {{
    margin-top: 12px;
  }}
  .action-section {{
    border-left: 5px solid var(--accent);
  }}
  .action-list {{
    display: grid;
    gap: 10px;
  }}
  .action-card {{
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr) 140px;
    gap: 12px;
    align-items: start;
    padding: 14px;
    background: #fff8ed;
    border: 1px solid var(--border);
    border-radius: 12px;
  }}
  .action-rank {{
    background: rgba(193,95,60,0.14);
    color: var(--accent);
    border-radius: 999px;
    padding: 4px 8px;
    font-weight: 800;
    text-align: center;
  }}
  .action-card p {{
    color: var(--text-muted);
    margin-top: 4px;
    font-size: 13px;
  }}
  .action-card a, .review-overview a {{
    color: var(--accent);
    text-decoration: none;
  }}
  .action-source {{
    color: var(--text-muted);
    font-size: 12px;
    text-align: right;
  }}
  .review-overview {{
    border-left: 5px solid var(--accent2);
  }}
  .overview-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 16px;
  }}
  .overview-grid div {{
    border: 1px solid var(--border);
    background: #fff8ed;
    border-radius: 6px;
    padding: 10px;
  }}
  .overview-grid span {{
    display: block;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .overview-grid strong {{
    display: block;
    margin-top: 3px;
    overflow-wrap: anywhere;
  }}
  .overview-columns, .limitation-grid {{
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    gap: 18px;
  }}
  .overview-actions {{
    padding-left: 22px;
  }}
  .overview-actions li {{
    margin-bottom: 10px;
  }}
  .overview-actions li span {{
    color: var(--text-muted);
    font-weight: 800;
    margin-right: 6px;
  }}
  .overview-actions p, .artifact-list {{
    color: var(--text-muted);
    font-size: 13px;
  }}
  .artifact-list {{
    padding-left: 18px;
    overflow-wrap: anywhere;
  }}
  .limitation-panel {{
    border-left: 5px solid var(--yellow);
  }}
  .checks-table {{ table-layout: fixed; }}
  .checks-table th:nth-child(1), .checks-table td:nth-child(1) {{ width: 44px; text-align: center; }}
  .checks-table th:nth-child(2), .checks-table td:nth-child(2) {{ width: 120px; }}
  .evidence-table th:nth-child(4), .evidence-table td:nth-child(4),
  .evidence-table th:nth-child(5), .evidence-table td:nth-child(5) {{ width: 28%; }}
  .evidence-cell, .reason-cell {{
    color: var(--text);
    line-height: 1.55;
    word-break: break-word;
    overflow-wrap: anywhere;
  }}
  .muted {{ color: var(--text-muted); text-align: center; padding: 18px; }}
  .detail-num {{
    background: var(--accent);
    color: var(--bg);
    border-radius: 50%;
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px;
  }}
  .detail-cat {{ color: var(--accent); font-weight: 600; }}
  .detail-item {{ flex: 1; }}
  .detail-verdict {{ font-size: 14px; }}
  .detail-brief {{
    flex-basis: 100%;
    color: var(--text-muted);
    font-size: 13px;
    padding-left: 40px;
  }}
  .detail-body {{ margin-top: 12px; }}
  .detail-evidence {{
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(183,121,31,0.10);
    border-radius: 6px;
    font-size: 14px;
    color: #6f4b12;
  }}
  .detail-evidence blockquote {{
    margin-top: 8px;
    white-space: pre-wrap;
    color: #6f4b12;
  }}
  .table-hint {{
    display: inline-block;
    color: var(--accent);
    font-weight: 600;
    margin-right: 8px;
  }}
  .summary-excerpt {{
    color: var(--text-muted);
    display: block;
    margin-top: 4px;
  }}
  .data-table-details {{
    margin-top: 8px;
  }}
  .data-table-details summary {{
    cursor: pointer;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .data-table-wrap {{
    margin-top: 8px;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fffdf8;
  }}
  .data-table {{
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .data-table th,
  .data-table td {{
    min-width: 96px;
    max-width: 320px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    vertical-align: top;
    white-space: normal;
    color: var(--text);
  }}
  .data-table th {{
    position: sticky;
    top: 0;
    background: #efe3d3;
    color: var(--text);
    z-index: 1;
  }}
  .detail-text {{
    margin-top: 8px;
    font-size: 14px;
    color: var(--text-muted);
    white-space: pre-wrap;
  }}
  .conclusion-section {{ border-left: 4px solid var(--green); }}
  .conclusion-text {{ font-size: 16px; white-space: pre-wrap; color: var(--text); }}
  .coverage-warning {{
    border-left: 5px solid var(--yellow);
    background: rgba(183,121,31,0.10);
  }}
  .coverage-warning code {{ background: var(--surface2); padding: 2px 6px; border-radius: 4px; }}
  .coverage-ok {{
    border-left: 5px solid var(--green);
    background: rgba(47,125,80,0.08);
  }}
  .error-block {{
    background: rgba(180,35,24,0.08);
    border: 1px solid var(--red);
    border-radius: 8px;
    padding: 16px;
    white-space: pre-wrap;
    font-family: monospace;
    font-size: 13px;
    color: #fca5a5;
    overflow-x: auto;
  }}
  .score-bar {{
    height: 8px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
  }}
  .score-fill {{
    height: 100%;
    border-radius: 4px;
    background: var(--red);
    transition: none;
  }}
  .score-breakdown {{
    margin-top: 6px;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .reference-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .cross-file-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .cross-file-card {{
    border: 1px solid var(--border);
    border-left: 4px solid var(--yellow);
    border-radius: 10px;
    background: #fff8ed;
    padding: 12px 14px;
  }}
  .cross-file-card[open] {{
    background: #fbfbfb;
  }}
  .cross-file-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 46px minmax(110px, 160px) minmax(180px, 1fr);
    gap: 8px 12px;
    align-items: center;
  }}
  .cross-file-summary::-webkit-details-marker {{ display: none; }}
  .cross-file-rank {{
    color: var(--accent);
    font-weight: 800;
  }}
  .cross-file-severity {{
    font-weight: 800;
    border-radius: 999px;
    padding: 3px 8px;
    text-align: center;
    background: rgba(183,121,31,0.12);
  }}
  .cross-file-strong {{ color: var(--red); }}
  .cross-file-medium {{ color: var(--yellow); }}
  .cross-file-weak {{ color: var(--text-muted); }}
  .cross-file-title {{
    font-weight: 700;
    overflow-wrap: anywhere;
  }}
  .cross-file-reason {{
    grid-column: 2 / 4;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .cross-file-body {{
    margin-top: 12px;
    color: var(--text-muted);
    font-size: 14px;
    display: grid;
    gap: 10px;
  }}
  .cross-file-body p {{
    margin-top: 4px;
    overflow-wrap: anywhere;
  }}
  .reference-card {{
    border: 1px solid var(--border);
    border-radius: 10px;
    background: #fff8ed;
    padding: 12px 14px;
  }}
  .reference-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 46px minmax(98px, 140px) minmax(220px, 1fr) auto;
    gap: 8px 12px;
    align-items: center;
  }}
  .reference-summary::-webkit-details-marker {{ display: none; }}
  .reference-index {{
    color: var(--accent);
    font-weight: 800;
  }}
  .reference-status {{
    font-weight: 800;
    border-radius: 999px;
    padding: 3px 8px;
    text-align: center;
    background: rgba(47,111,115,0.10);
  }}
  .reference-verified, .reference-likely {{ color: var(--green); }}
  .reference-weak, .reference-not_found, .reference-error {{ color: var(--red); }}
  .reference-title {{
    font-weight: 700;
    overflow-wrap: anywhere;
  }}
  .reference-confidence {{
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
  }}
  .reference-issues {{
    grid-column: 2 / 5;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .reference-body {{
    margin-top: 12px;
    color: var(--text-muted);
    font-size: 14px;
  }}
  .reference-matches {{
    margin-top: 8px;
    padding-left: 22px;
  }}
  .reference-matches li {{
    margin: 8px 0;
  }}
  .reference-matches a, .image-section a {{
    color: var(--accent);
    font-weight: 700;
  }}
  .image-table code {{
    color: var(--text-muted);
    white-space: normal;
    overflow-wrap: anywhere;
  }}
  .detector-hint {{
    display: inline-block;
    color: var(--accent);
    font-weight: 800;
    font-size: 12px;
    margin-bottom: 4px;
  }}
  .web-action-section {{
    border-left: 5px solid #2563eb;
  }}
  .web-action-toolbar {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 12px 0;
  }}
  .action-button, .secondary-button {{
    border: 1px solid #cbd5e1;
    background: #ffffff;
    color: var(--text-main);
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 800;
    cursor: pointer;
  }}
  .action-button {{
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
  }}
  .draft-language-select {{
    border: 1px solid #cbd5e1;
    background: #ffffff;
    color: var(--text-main);
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 800;
  }}
  .identity-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 10px;
    margin: 12px 0;
  }}
  .identity-grid label, .custom-concern-label, .inline-control {{
    display: flex;
    flex-direction: column;
    gap: 5px;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
  }}
  .identity-grid input, .custom-concern-input {{
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px 10px;
    color: var(--text-main);
    background: #ffffff;
    font: inherit;
  }}
  .evidence-picker {{
    margin: 12px 0;
  }}
  .evidence-choice-list {{
    display: grid;
    gap: 8px;
    margin-top: 8px;
  }}
  .evidence-choice {{
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 8px;
    align-items: start;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px;
    background: #ffffff;
  }}
  .evidence-choice small {{
    display: block;
    color: var(--text-muted);
    line-height: 1.45;
    margin-top: 3px;
  }}
  .custom-concern-input {{
    width: 100%;
    min-height: 70px;
    resize: vertical;
  }}
  .manual-confirmation {{
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 8px;
    align-items: start;
    margin: 10px 0;
    color: var(--text-main);
    font-size: 13px;
  }}
  .existing-followups {{
    color: var(--text-muted);
    font-size: 13px;
    margin: 8px 0;
  }}
  .action-button:hover, .secondary-button:hover {{
    filter: brightness(0.96);
  }}
  .web-action-status {{
    color: var(--text-muted);
    font-size: 13px;
    margin: 8px 0;
  }}
  .web-action-status.error {{
    color: #b42318;
    font-weight: 700;
  }}
  .generated-draft {{
    width: 100%;
    min-height: 260px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font: 14px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: var(--text-main);
    background: #fff;
    resize: vertical;
  }}
  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 32px;
    padding: 16px;
  }}
  /* Compact grayscale report skin: evidence first, decoration last. */
  :root {{
    --bg: #f6f6f6;
    --paper: #ffffff;
    --surface: #ffffff;
    --surface2: #eeeeee;
    --text: #171717;
    --text-muted: #666666;
    --accent: #111111;
    --accent2: #3f3f46;
    --border: #d4d4d4;
    --red: #b42318;
    --yellow: #8a5a00;
    --green: #166534;
    --shadow: none;
  }}
  body {{
    background: #f6f6f6;
    color: var(--text);
    line-height: 1.55;
    padding: 18px;
  }}
  .container {{ max-width: 1280px; }}
  .header, .section {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: none;
  }}
  .header {{
    padding: 18px;
    margin-bottom: 14px;
    text-align: left;
  }}
  .report-topline {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 12px;
  }}
  .report-kicker {{
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0;
  }}
  .header h1 {{
    font-size: 24px;
    line-height: 1.2;
    margin: 3px 0 8px;
    letter-spacing: 0;
  }}
  .report-summary {{
    max-width: 820px;
    color: #333333;
    font-size: 14px;
  }}
  .risk-badge {{
    border-radius: 6px;
    padding: 7px 10px;
    margin: 0;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }}
  .score-panel {{
    display: grid;
    grid-template-columns: 170px minmax(220px, 1fr);
    gap: 12px;
    align-items: center;
    padding: 12px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .score-value {{
    font-size: 34px;
    line-height: 1;
    font-weight: 900;
    color: {risk_color};
  }}
  .score-caption {{
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 4px;
  }}
  .priority-label {{
    font-weight: 900;
    color: {risk_color};
    margin-bottom: 4px;
  }}
  .score-bar {{
    height: 7px;
    background: #e5e5e5;
    border-radius: 4px;
    margin-top: 0;
  }}
  .score-fill {{
    background: {risk_color};
    border-radius: 4px;
    transition: none;
  }}
  .score-breakdown {{
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
  }}
  .meta-grid > div, .meta-item {{
    min-width: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 9px 10px;
    background: #fafafa;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .meta-grid strong, .meta-item strong {{
    display: block;
    color: var(--text);
    font-size: 13px;
    margin-top: 3px;
    overflow-wrap: anywhere;
  }}
  .section {{
    padding: 16px;
    margin-bottom: 14px;
  }}
  .section h2 {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 17px;
    line-height: 1.25;
    margin-bottom: 12px;
    padding-bottom: 8px;
  }}
  .section-hint {{
    margin: -4px 0 12px;
    color: var(--text-muted);
    font-size: 13px;
  }}
  table {{ font-size: 13px; }}
  th, td {{
    padding: 8px 9px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  th {{
    background: #f1f1f1;
    color: #444444;
    font-size: 11px;
    letter-spacing: 0;
  }}
  .action-card, .suspicion-card, .detail-card, .reference-card {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-left: 3px solid #111111;
    border-radius: 6px;
    padding: 10px 12px;
  }}
  .cross-file-card {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-left: 3px solid var(--yellow);
    border-radius: 6px;
    padding: 10px 12px;
  }}
  .evidence-summary {{ border-left: 3px solid var(--red); }}
  .suspicion-summary {{
    grid-template-columns: 44px minmax(72px, 112px) minmax(180px, 1fr) 96px;
    gap: 7px 10px;
  }}
  .suspicion-rank, .action-rank, .detail-num {{
    background: #f1f1f1;
    color: #111111;
    border: 1px solid var(--border);
    border-radius: 5px;
  }}
  .suspicion-brief {{
    grid-column: 2 / 4;
    color: var(--text-muted);
  }}
  .summary-action {{
    grid-column: 4;
    grid-row: 2;
    justify-self: end;
    color: #111111;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
  }}
  .detail-summary .summary-action {{
    grid-column: auto;
    grid-row: auto;
    margin-left: auto;
  }}
  .detail-card[open], .suspicion-card[open] {{
    background: #fbfbfb;
  }}
  .cross-file-card[open] {{
    background: #fbfbfb;
  }}
  .detail-summary::after, .suspicion-summary::after {{
    content: none;
  }}
  .detail-body, .suspicion-body {{
    border-top: 1px solid var(--border);
    margin-top: 10px;
    padding-top: 10px;
  }}
  .detail-evidence {{
    background: #f7f7f7;
    color: #222222;
    border: 1px solid var(--border);
    border-radius: 6px;
  }}
  .detail-evidence blockquote {{
    color: #222222;
  }}
  .detail-text {{
    color: #4b4b4b;
  }}
  .data-table-wrap {{
    background: #ffffff;
    border-radius: 6px;
  }}
  .data-table th {{
    background: #ededed;
  }}
  .merged-group {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 10px;
    background: #fff;
  }}
  .merged-group summary {{
    cursor: pointer;
    font-weight: 800;
    color: #111111;
  }}
  .coverage-warning, .coverage-ok, .conclusion-section, .action-section, .web-action-section {{
    border-left-width: 3px;
    background: #ffffff;
  }}
  .web-action-section {{ border-left-color: #2563eb; }}
  .action-button, .secondary-button {{
    border-radius: 6px;
    padding: 8px 11px;
    color: #111111;
  }}
  .action-button {{ color: #ffffff; }}
  .generated-draft {{
    border-radius: 6px;
    min-height: 220px;
    color: #111111;
  }}
  .image-thumb {{
    max-width: 84px;
    max-height: 64px;
    object-fit: contain;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: #ffffff;
  }}
  .muted-inline {{
    color: var(--text-muted);
    font-size: 12px;
  }}
  @media (max-width: 900px) {{
    body {{ padding: 10px; }}
    .report-topline {{ flex-direction: column; }}
    .score-panel {{ grid-template-columns: 1fr; }}
    .meta-grid {{ grid-template-columns: 1fr 1fr; }}
    .overview-grid {{ grid-template-columns: 1fr 1fr; }}
    .overview-columns, .limitation-grid {{ grid-template-columns: 1fr; }}
    .suspicion-summary, .reference-summary {{
      grid-template-columns: 40px minmax(70px, 100px) 1fr;
    }}
    .suspicion-score, .reference-confidence, .summary-action {{
      grid-column: 2 / 4;
      justify-self: start;
    }}
    .suspicion-brief, .reference-issues {{
      grid-column: 1 / 4;
    }}
  }}
  @media (max-width: 560px) {{
    .meta-grid {{ grid-template-columns: 1fr; }}
    .overview-grid {{ grid-template-columns: 1fr; }}
    .checks-table {{ table-layout: auto; }}
  }}
</style>
</head>
"""


def build_html_report_context_from_namespace(namespace, report, pdf_path, meta, stat_result):
    """Build computed values consumed by the top-level HTML report template."""
    html_escape = _namespace_value(namespace, "_html_escape", _html_escape)
    normalize_run_meta = _namespace_value(namespace, "normalize_run_meta")
    status_builder = _namespace_value(namespace, "build_html_status_fragments_from_namespace")
    check_section_builder = _namespace_value(namespace, "format_html_check_sections_from_namespace")
    action_summary_renderer = _namespace_value(namespace, "format_audit_action_summary_html")
    review_overview_renderer = _namespace_value(namespace, "format_review_overview_html")
    resource_renderer = _namespace_value(namespace, "format_resource_audit_html")
    reference_renderer = _namespace_value(namespace, "format_reference_audit_html")
    image_renderer = _namespace_value(namespace, "format_image_audit_html")
    cross_file_renderer = _namespace_value(namespace, "format_cross_file_consistency_html")
    evidence_chain_renderer = _namespace_value(namespace, "format_evidence_chain_audit_html")
    web_action_panel_renderer = _namespace_value(namespace, "format_web_action_panel_html")

    if callable(normalize_run_meta):
        meta = normalize_run_meta(meta, pdf_path)
    risk_colors = {"高": "#b42318", "中": "#a16207", "低": "#166534", "严重证据冲突": "#111827"}
    risk_icons = {"高": "高复核优先级", "中": "中复核优先级", "低": "低复核优先级", "严重证据冲突": "严重证据冲突"}
    risk = report.get("risk_level", "未知")
    artifact_type = meta.get("artifact_type") or "complete"
    runtime = meta.get("runtime") or {}

    if callable(status_builder):
        status_fragments = status_builder(namespace, report, meta, stat_result)
    else:
        status_fragments = build_html_status_fragments_from_namespace(namespace, report, meta, stat_result)

    if callable(check_section_builder):
        checks_html, conclusion_html = check_section_builder(namespace, report)
    else:
        checks_html, conclusion_html = "", ""

    parse_error = report.get("parse_error")

    return {
        "report": report,
        "pdf_path": pdf_path,
        "meta": meta,
        "stat_result": stat_result,
        "risk": risk,
        "risk_color": risk_colors.get(risk, "#6b7280"),
        "risk_icon": risk_icons.get(risk, "未知风险"),
        "artifact_type": artifact_type,
        "artifact_label": "范围受限审查 (limited)" if artifact_type == "limited" else "完整审查 (complete)",
        "artifact_badge": "范围受限 limited" if artifact_type == "limited" else "完整审查 complete",
        "artifact_color": "#8a5a00" if artifact_type == "limited" else "#166534",
        "runtime": runtime,
        "benford_val": round(stat_result["benford_deviation"], 3) if stat_result["benford_deviation"] else "样本不足",
        "benford_status": stat_result.get("benford_status", "N/A") or "N/A",
        "p_abnormal": stat_result["p_value_abnormal"],
        "p_status_class": "status-warn" if stat_result["p_value_abnormal"] else "status-ok",
        "limited_notice": status_fragments["limited_notice"],
        "chunk_info": status_fragments["chunk_info"],
        "number_consistency": status_fragments["number_consistency"],
        "coverage_banner": status_fragments["coverage_banner"],
        "score_breakdown_html": status_fragments["score_breakdown_html"],
        "action_summary_html": action_summary_renderer(report, meta, stat_result) if callable(action_summary_renderer) and not parse_error else "",
        "review_overview_html": review_overview_renderer(report, meta, stat_result) if callable(review_overview_renderer) and not parse_error else "",
        "resource_audit_html": resource_renderer(meta.get("resource_audit")) if callable(resource_renderer) else "",
        "reference_audit_html": reference_renderer(meta.get("reference_audit")) if callable(reference_renderer) else "",
        "image_audit_html": image_renderer(meta.get("image_audit")) if callable(image_renderer) else "",
        "cross_file_audit_html": cross_file_renderer(meta.get("cross_file_consistency_audit")) if callable(cross_file_renderer) else "",
        "evidence_chain_audit_html": evidence_chain_renderer(meta.get("evidence_chain_audit")) if callable(evidence_chain_renderer) else "",
        "web_action_panel_html": web_action_panel_renderer(report, pdf_path, meta, stat_result) if callable(web_action_panel_renderer) and not parse_error else "",
        "summary_text": html_escape(report.get("summary", "N/A")),
        "extracted_chars": meta.get("total_chars", meta.get("chars", "N/A")),
        "extraction_method": meta.get("extraction_method", meta.get("source", "N/A")),
        "checks_html": checks_html,
        "conclusion_html": conclusion_html,
    }


def build_html_report_body_from_namespace(namespace, context):
    """Build the top-level HTML report body from precomputed render context."""
    html_escape = _namespace_value(namespace, "_html_escape", _html_escape)
    time_module = _namespace_value(namespace, "time")
    runtime_year = _namespace_value(namespace, "runtime_utc_year")
    prompt_version = _namespace_value(namespace, "PROMPT_VERSION", "")
    schema_version = _namespace_value(namespace, "SCHEMA_VERSION", "")
    adapter_version = _namespace_value(namespace, "ADAPTER_VERSION", "")
    risk_rule_version = _namespace_value(namespace, "RISK_RULE_VERSION", "")
    now = time_module.strftime("%Y-%m-%d %H:%M:%S") if time_module is not None else ""
    current_year = runtime_year() if callable(runtime_year) else ""

    report = context["report"]
    meta = context["meta"]
    stat_result = context["stat_result"]
    runtime = context["runtime"]

    return f"""<body>
<div class="container">
  <div class="header">
    <div class="report-topline">
      <div>
        <div class="report-kicker">Paper Audit / Veritas</div>
        <h1>学术论文审查报告</h1>
        <div class="report-summary">{context["summary_text"]}</div>
      </div>
      <div class="artifact-badge" style="background:{context["artifact_color"]};">{html_escape(context["artifact_badge"])}</div>
    </div>
    <div class="score-panel">
      <div>
        <div class="score-value">{report.get('detection_score', 0)}</div>
        <div class="score-caption">证据风险分 / 100，越高表示越需要优先复核</div>
      </div>
      <div>
        <div class="priority-label">复核优先级：{html_escape(context["risk_icon"])}</div>
        <div class="score-bar"><div class="score-fill" style="width:{min(report.get('detection_score', 0), 100)}%; background:{context["risk_color"]};"></div></div>
      {context["score_breakdown_html"]}
      </div>
    </div>
    <div class="meta-grid">
      <div><span>文件</span><strong>{html_escape(context["pdf_path"])}</strong></div>
      <div><span>产物类型</span><strong>{html_escape(context["artifact_label"])}</strong></div>
      <div><span>Prompt版本</span><strong>{html_escape(meta.get('prompt_version', prompt_version))}</strong></div>
      <div><span>Schema版本</span><strong>{html_escape(meta.get('schema_version', schema_version))}</strong></div>
      <div><span>Adapter版本</span><strong>{html_escape(meta.get('adapter_version', adapter_version))}</strong></div>
      <div><span>规则版本</span><strong>{html_escape(meta.get('risk_rule_version', report.get('rule_version', risk_rule_version)))}</strong></div>
      <div><span>文件大小</span><strong>{meta.get('size_mb', 'N/A')} MB</strong></div>
      <div><span>提取字符数</span><strong>{context["extracted_chars"]}</strong></div>
      <div><span>提取方式</span><strong>{context["extraction_method"]}</strong></div>
      {context["chunk_info"] if context["chunk_info"] else ''}
      <div><span>审查时间</span><strong>{html_escape(runtime.get('local_time') or now)}</strong></div>
      <div><span>运行时UTC年份</span><strong>{html_escape(runtime.get('utc_year', current_year))}</strong></div>
    </div>
  </div>

  {context["review_overview_html"]}
  {context["coverage_banner"]}
  {context["limited_notice"]}
  {context["action_summary_html"]}

  <div class="section" id="local-statistics">
    <h2>本地统计检测结果</h2>
    <table>
      <thead><tr><th>检测项</th><th>结果</th><th>状态</th></tr></thead>
      <tbody>
        <tr><td>Benford分布偏差</td><td>{context["benford_val"]}</td><td>{context["benford_status"]}</td></tr>
        <tr><td>p值数量/异常</td><td>{stat_result['p_value_count']} / {stat_result['p_value_abnormal']}个&gt;0.05</td><td><span class="{context["p_status_class"]}">{'⚠️异常' if context["p_abnormal"] else '✅正常'}</span></td></tr>
        <tr><td>标准差提及</td><td>{stat_result['sd_count']}处</td><td>N/A</td></tr>
        <tr><td>提取数字数</td><td>{stat_result['number_count']}</td><td>-</td></tr>
        {context["number_consistency"]}
      </tbody>
    </table>
  </div>

  {context["checks_html"]}
  {context["web_action_panel_html"]}
  {context["conclusion_html"]}
  {context["evidence_chain_audit_html"]}
  {context["image_audit_html"]}
  {context["cross_file_audit_html"]}
  {context["resource_audit_html"]}
  {context["reference_audit_html"]}

  <div class="footer">
    Generated by <strong>Veritas</strong> — 学术论文自动审查工具（耿同学标准） | {now}
  </div>
</div>
</body>
</html>"""
