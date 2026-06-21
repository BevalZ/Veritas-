"""Resource audit Markdown and HTML rendering helpers."""

import re

from .html_utils import _html_escape
from .text_utils import _brief_text

__all__ = [
    "RESOURCE_STATUS_LABELS",
    "_resource_status_text",
    "_resource_type_text",
    "format_resource_audit_markdown",
    "format_resource_audit_html",
]


RESOURCE_STATUS_LABELS = {
    "available": "可访问",
    "unavailable": "不可访问",
    "access_restricted": "访问受限",
    "malformed": "链接格式错误",
    "error": "检测异常",
    "skipped": "未检测",
}


def _md_escape_cell(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("|", "\\|")


def _resource_status_text(status):
    return RESOURCE_STATUS_LABELS.get(str(status or ""), str(status or "N/A"))


def _resource_type_text(resource_type):
    mapping = {
        "code_repository": "代码仓库",
        "data_repository": "数据资源库",
        "deployed_resource": "在线资源/部署平台",
    }
    return mapping.get(str(resource_type or ""), str(resource_type or "N/A"))


def format_resource_audit_markdown(resource_audit):
    if resource_audit is None:
        return []
    lines = [
        '<a id="resource-audit"></a>',
        "## 🔗 代码仓库与在线资源可用性校检",
        "",
        f"**状态**: {resource_audit.get('status', 'N/A')}",
        f"**资源数量**: {resource_audit.get('resource_count', 0)}",
        f"**在线检测**: {'启用' if resource_audit.get('online_enabled') else '未启用'}"
        + (f"（已检测 {resource_audit.get('online_checked', 0)} 项）" if resource_audit.get("online_enabled") else ""),
        f"> {resource_audit.get('note', '')}",
        "",
    ]
    resources = resource_audit.get("resources") or []
    if resources:
        lines.append("| # | 类型 | URL | 可用性 | 问题 | 上下文 |")
        lines.append("|---|------|-----|--------|------|--------|")
        for idx, resource in enumerate(resources[:40], 1):
            availability = resource.get("availability") or {}
            lines.append(
                f"| {idx} | {_md_escape_cell(_resource_type_text(resource.get('type')))} | "
                f"{_md_escape_cell(resource.get('url', ''))} | "
                f"{_md_escape_cell(_resource_status_text(availability.get('status')))} | "
                f"{_md_escape_cell(availability.get('problem', '') or '-')} | "
                f"{_md_escape_cell(_brief_text(resource.get('context', ''), 180))} |"
            )
    else:
        lines.append("> 未识别到代码仓库或论文部署的在线资源链接。")
    lines.append("")
    return lines


def format_resource_audit_html(resource_audit):
    if resource_audit is None:
        return ""
    rows = ""
    for idx, resource in enumerate((resource_audit.get("resources") or [])[:80], 1):
        availability = resource.get("availability") or {}
        url = resource.get("url", "")
        href = _html_escape(url) if re.match(r"^https?://", url, flags=re.I) else ""
        url_html = f'<a href="{href}" target="_blank" rel="noopener">{_html_escape(url)}</a>' if href else _html_escape(url)
        rows += (
            "<tr>"
            f"<td>{idx}</td>"
            f"<td>{_html_escape(_resource_type_text(resource.get('type')))}</td>"
            f"<td>{url_html}</td>"
            f"<td>{_html_escape(_resource_status_text(availability.get('status')))}</td>"
            f"<td>{_html_escape(availability.get('problem', '') or '-')}</td>"
            f"<td>{_html_escape(_brief_text(resource.get('context', ''), 220))}</td>"
            "</tr>"
        )
    if rows:
        body = f"""
    <table>
      <thead><tr><th>#</th><th>类型</th><th>URL</th><th>可用性</th><th>问题</th><th>上下文</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""
    else:
        body = '<p class="section-hint">未识别到代码仓库或论文部署的在线资源链接。</p>'
    return f"""
  <div class="section resource-section" id="resource-audit">
    <h2>代码仓库与在线资源可用性校检</h2>
    <p><strong>状态</strong>: {_html_escape(resource_audit.get('status', 'N/A'))} | <strong>数量</strong>: {resource_audit.get('resource_count', 0)} | <strong>在线检测</strong>: {'启用' if resource_audit.get('online_enabled') else '未启用'}（{resource_audit.get('online_checked', 0)}项）</p>
    <p class="section-hint">{_html_escape(resource_audit.get('note', ''))}</p>
    {body}
  </div>"""
