"""Image audit report and review-manifest rendering helpers."""

import re
from pathlib import Path

from .html_utils import _html_escape
from .text_utils import _brief_text

DEFAULT_IMAGE_DETECT_URL = "https://imagedetector.com/"

__all__ = [
    "_image_semantic_display",
    "_image_detector_display",
    "format_image_audit_html",
    "format_image_audit_markdown",
    "save_image_review_manifest",
]


def _md_escape_cell(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("|", "\\|")


def _image_semantic_display(item):
    semantic = item.get("semantic") or {}
    if semantic:
        parts = [semantic.get("summary", "未返回语义摘要")]
        if semantic.get("image_type"):
            parts.append(f"类型: {semantic.get('image_type')}")
        if semantic.get("scientific_context"):
            parts.append(f"用途: {_brief_text(semantic.get('scientific_context'), 80)}")
        if semantic.get("visible_text"):
            parts.append(f"可读文字: {_brief_text(semantic.get('visible_text'), 100)}")
        risks = semantic.get("risks") or []
        if risks:
            parts.append("风险: " + "；".join(_brief_text(risk, 60) for risk in risks[:3]))
        manual_checks = semantic.get("manual_checks") or []
        if manual_checks:
            parts.append("复核: " + "；".join(_brief_text(check, 60) for check in manual_checks[:2]))
        confidence = semantic.get("confidence")
        try:
            confidence_text = f"{float(confidence):.2f}"
        except Exception:
            confidence_text = ""
        status = semantic.get("reasonability") or semantic.get("status", "")
        if confidence_text:
            status = f"{status} / 置信度 {confidence_text}" if status else f"置信度 {confidence_text}"
        return ("；".join(str(part) for part in parts if part), status)
    issues = set(item.get("issues") or [])
    if item.get("risk") == "local_warning" or {"low_resolution", "extreme_aspect_ratio", "near_blank_or_flat"} & issues:
        return (
            "未进入图像语义分析优先队列；该图信息量低或形态异常，优先按本地异常上传imagedetector并人工核对原图。",
            "人工优先",
        )
    return (
        "未进入本次图像语义分析上限；需要时可提高 --image-semantic-limit 后重跑。",
        "未覆盖",
    )


def _image_detector_display(item):
    detector = item.get("detector") or {}
    if not detector:
        return ("未进入本次自动检测上限；需要时可提高 --image-detector-limit 后重跑。", "未覆盖")
    status = detector.get("status")
    if status == "ok":
        score = detector.get("score")
        label = detector.get("label") or ("AI生成" if detector.get("is_ai") else "真实/人工")
        confidence = detector.get("confidence")
        score_text = f"{score:.1f}" if isinstance(score, (int, float)) else "N/A"
        parts = [f"{label}", f"AI分数 {score_text}"]
        if confidence:
            parts.append(f"置信度 {confidence}")
        if detector.get("source"):
            parts.append(f"来源 {detector.get('source')}")
        return ("；".join(parts), "AI概率偏高" if isinstance(score, (int, float)) and score >= 50 else "未提示AI")
    reason = detector.get("reason") or status or "unknown"
    summary = detector.get("summary") or f"imagedetector未完成：{reason}"
    return (summary, "自动检测未完成")


def format_image_audit_html(image_audit, image_detect_url=DEFAULT_IMAGE_DETECT_URL):
    if not image_audit:
        return ""
    rows = ""
    for idx, item in enumerate(image_audit.get("images") or [], 1):
        issues = ", ".join(item.get("issues") or ["local_ok"])
        semantic_summary, semantic_reasonability = _image_semantic_display(item)
        detector_summary, detector_status = _image_detector_display(item)
        path = _html_escape(item.get("path", ""))
        try:
            img_uri = Path(item.get("path", "")).resolve().as_uri()
        except Exception:
            img_uri = ""
        preview = f'<img class="image-thumb" src="{_html_escape(img_uri)}" alt="{_html_escape(item.get("file", ""))}">' if img_uri else "-"
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td>{preview}</td>
          <td>{_html_escape(item.get('file', ''))}</td>
          <td>{_html_escape(str(item.get('width') or '?'))} x {_html_escape(str(item.get('height') or '?'))}</td>
          <td>{_html_escape(item.get('risk', ''))}</td>
          <td>{_html_escape(issues)}</td>
          <td>{_html_escape(_brief_text(semantic_summary, 180))}<br><span class="muted-inline">{_html_escape(semantic_reasonability)}</span></td>
          <td>{_html_escape(_brief_text(detector_summary, 180))}<br><span class="detector-hint">{_html_escape(detector_status)}</span><br><code>{path}</code></td>
        </tr>"""
    if not rows:
        rows = '<tr><td colspan="8" class="muted">未发现可检测图片。</td></tr>'
    return f"""
  <div class="section image-section" id="image-audit">
    <h2>图像AI/合理性检测</h2>
    <p class="section-hint">{_html_escape(image_audit.get('note', ''))}</p>
    <p><strong>检测网站</strong>: <a href="{image_detect_url}" target="_blank" rel="noopener">{image_detect_url}</a> | <strong>图片</strong>: {image_audit.get('checked_count', 0)} / {image_audit.get('image_count', 0)} | <strong>语义模型</strong>: {_html_escape(image_audit.get('semantic_model', 'N/A'))}（{image_audit.get('semantic_checked', 0)}张） | <strong>imagedetector</strong>: {image_audit.get('detector_checked', 0)}张</p>
    <table class="checks-table image-table">
      <thead><tr><th>#</th><th>预览</th><th>文件</th><th>尺寸</th><th>本地结论</th><th>本地问题</th><th>图像语义分析</th><th>imagedetector自动结果 / 路径</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""


def format_image_audit_markdown(image_audit, image_detect_url=DEFAULT_IMAGE_DETECT_URL):
    if not image_audit:
        return []
    lines = [
        '<a id="image-audit"></a>',
        "## 🖼️ 图像AI/合理性检测",
        "",
        f"**检测网站**: {image_audit.get('site', image_detect_url)}",
        f"**语义模型**: {image_audit.get('semantic_model', 'N/A')}（{image_audit.get('semantic_checked', 0)}张）",
        f"**imagedetector自动检测**: {image_audit.get('detector_checked', 0)}张",
        f"**图片数量**: {image_audit.get('checked_count', 0)} / {image_audit.get('image_count', 0)}",
        f"> {image_audit.get('note', '')}",
        "",
    ]
    images = image_audit.get("images") or []
    if images:
        lines.append("| # | 文件 | 尺寸 | 本地结论 | 图像语义分析 | imagedetector | 本地问题 |")
        lines.append("|---|------|------|----------|-------------|---------------|----------|")
        for idx, item in enumerate(images[:30], 1):
            size = f"{item.get('width') or '?'} x {item.get('height') or '?'}"
            issues = ", ".join(item.get("issues") or ["local_ok"])
            semantic_text, _ = _image_semantic_display(item)
            detector_text, detector_status = _image_detector_display(item)
            lines.append(
                f"| {idx} | {_md_escape_cell(item.get('file', ''))} | {_md_escape_cell(size)} | "
                f"{_md_escape_cell(item.get('risk', ''))} | {_md_escape_cell(_brief_text(semantic_text, 180))} | "
                f"{_md_escape_cell(_brief_text(detector_text + ' / ' + detector_status, 180))} | {_md_escape_cell(issues)} |"
            )
    else:
        lines.append("> 未发现可检测图片。")
    lines.append("")
    return lines


def save_image_review_manifest(image_audit, output_dir, image_detect_url=DEFAULT_IMAGE_DETECT_URL):
    if not image_audit or not image_audit.get("images"):
        return None
    cards = ""
    for idx, item in enumerate(image_audit.get("images") or [], 1):
        path = _html_escape(item.get("path", ""))
        issues = _html_escape(", ".join(item.get("issues") or ["local_ok"]))
        semantic_summary_raw, semantic_reasonability_raw = _image_semantic_display(item)
        detector_summary_raw, detector_status_raw = _image_detector_display(item)
        semantic_summary = _html_escape(semantic_summary_raw)
        semantic_reasonability = _html_escape(semantic_reasonability_raw)
        detector_summary = _html_escape(detector_summary_raw)
        detector_status = _html_escape(detector_status_raw)
        try:
            img_uri = Path(item.get("path", "")).resolve().as_uri()
        except Exception:
            img_uri = ""
        preview = f'<img src="{_html_escape(img_uri)}" alt="{_html_escape(item.get("file", ""))}">' if img_uri else '<div class="preview-empty">无预览</div>'
        cards += f"""
        <section class="image-card">
          <div class="rank">#{idx}</div>
          <div class="preview">{preview}</div>
          <div class="image-main">
            <h2>{_html_escape(item.get('file', ''))}</h2>
            <div class="meta">
              <span>本地结论: <strong>{_html_escape(item.get('risk', ''))}</strong></span>
              <span>本地问题: <strong>{issues}</strong></span>
            </div>
            <p class="semantic"><strong>图像语义分析</strong>: {semantic_summary}<br><span>{semantic_reasonability}</span></p>
            <p class="semantic"><strong>imagedetector自动结果</strong>: {detector_summary}<br><span>{detector_status}</span></p>
            <code>{path}</code>
          </div>
          <div class="result-box">
            <label>自动检测复核</label>
            <div class="write-space"></div>
          </div>
          <div class="result-box">
            <label>复核备注</label>
            <div class="write-space"></div>
          </div>
        </section>"""
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>图像AI检测复核清单</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f7f3ec; color:#2b241d; padding:24px; }}
main {{ max-width: 1180px; margin: 0 auto; background:#fffdf8; border:1px solid #e4d8c8; border-radius:18px; padding:28px; box-shadow:0 20px 60px rgba(61,45,31,.09); }}
a {{ color:#c15f3c; font-weight:700; }}
.hint {{ color:#7b7065; max-width: 900px; }}
.image-list {{ display:flex; flex-direction:column; gap:14px; margin-top:22px; }}
.image-card {{ display:grid; grid-template-columns:48px 118px minmax(0,1fr) 180px 180px; gap:14px; align-items:stretch; border:1px solid #e4d8c8; border-left:4px solid #c15f3c; border-radius:14px; background:#fffaf1; padding:14px; page-break-inside:avoid; }}
.rank {{ font-weight:800; color:#b42318; background:#fde5db; border-radius:999px; width:38px; height:28px; display:flex; align-items:center; justify-content:center; }}
.preview {{ width:110px; min-height:96px; display:flex; align-items:center; justify-content:center; background:#fff; border:1px solid #e4d8c8; border-radius:10px; overflow:hidden; }}
.preview img {{ width:100%; max-height:110px; object-fit:contain; }}
.preview-empty {{ color:#7b7065; font-size:12px; }}
.image-main h2 {{ font-size:15px; margin:0 0 8px; overflow-wrap:anywhere; }}
.meta {{ display:flex; gap:10px; flex-wrap:wrap; color:#7b7065; font-size:13px; margin-bottom:8px; }}
.semantic {{ margin:8px 0; color:#2b241d; background:#fff; border:1px solid #e4d8c8; border-radius:8px; padding:8px; font-size:13px; }}
.semantic span {{ color:#7b7065; }}
code {{ display:block; color:#7b7065; background:#fff; border:1px solid #e4d8c8; border-radius:8px; padding:8px; overflow-wrap:anywhere; word-break:break-word; font-size:12px; }}
.result-box {{ background:#fff; border:1px dashed #d3bda6; border-radius:10px; padding:10px; min-height:110px; }}
.result-box label {{ display:block; color:#7b7065; font-size:12px; font-weight:700; margin-bottom:8px; }}
.write-space {{ min-height:64px; }}
@media (max-width: 980px) {{
  .image-card {{ grid-template-columns:42px 100px minmax(0,1fr); }}
  .result-box {{ grid-column: 2 / 4; }}
}}
</style>
</head>
<body>
<main>
<h1>图像AI检测复核清单</h1>
<p class="hint">本清单已由子工具自动调用 <a href="{image_detect_url}" target="_blank" rel="noopener">{image_detect_url}</a> 的网页检测流程，右侧空栏用于人工复核自动结果、记录截图或补充说明。</p>
<div class="image-list">{cards}</div>
</main>
</body>
</html>"""
    path = Path(output_dir) / "image_ai_review_manifest.html"
    path.write_text(html_doc, encoding="utf-8")
    return path
