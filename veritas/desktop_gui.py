"""Desktop GUI helper boundary."""

import html
import json
import re
import webbrowser
from pathlib import Path

from .runtime_config import DEFAULT_LLM_API_URL, DEFAULT_LLM_MODEL

DESKTOP_GUI_ARTIFACT_LABELS = {
    "html": "HTML",
    "markdown": "Markdown",
    "json": "JSON",
    "folder": "目录",
}

DESKTOP_GUI_FOLLOWUP_LABELS = {
    "pubpeer_comment": "写 PubPeer",
    "journal_letter": "写 Letter",
}

DESKTOP_GUI_CONFIG_CAPABILITIES = (
    ("text_llm", "LLM"),
    ("mineru", "MinerU"),
    ("image_semantic", "图像语义"),
    ("reference_lookup", "参考核验"),
    ("image_detector", "图像检测"),
)

DESKTOP_GUI_CONFIG_DEPENDENCIES = (
    ("python_docx", "DOCX"),
    ("openpyxl", "Excel"),
)

DESKTOP_GUI_LLM_CONFIG_FIELDS = ("LLM_API_KEY", "LLM_API_URL", "LLM_MODEL")

DESKTOP_GUI_STAGE_LABELS = {
    "初始化完成": "初始化完成",
    "文本提取完成": "文本提取完成",
    "单文件文本提取完成": "文本提取完成",
    "MinerU文本提取完成": "MinerU 提取完成",
    "PDF文本提取完成": "PDF 提取完成",
    "开始本地统计检测": "本地统计",
    "本地统计检测完成": "本地统计完成",
    "开始合并审查结果": "合并结果",
    "审查结果合并完成": "结果合并完成",
    "开始生成报告": "生成报告",
    "全部完成": "已完成",
}


def desktop_gui_config_file_path(config_path=None):
    return Path(config_path or "config.py")


def desktop_gui_write_llm_config(
    api_key,
    api_url,
    model,
    config_path=None,
    default_api_url=DEFAULT_LLM_API_URL,
    default_model=DEFAULT_LLM_MODEL,
):
    """Persist text LLM settings to config.py while preserving unrelated settings."""
    path = desktop_gui_config_file_path(config_path)
    values = {
        "LLM_API_KEY": str(api_key or "").strip(),
        "LLM_API_URL": str(api_url or "").strip() or default_api_url,
        "LLM_MODEL": str(model or "").strip() or default_model,
    }
    existing_lines = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()
    else:
        existing_lines = [
            "# Local Veritas configuration.",
            "# This file is read by the desktop GUI and CLI. Do not commit secrets.",
            "",
        ]
    updated = set()
    output_lines = []
    assignment_re = re.compile(r"^\s*(LLM_API_KEY|LLM_API_URL|LLM_MODEL)\s*=")
    for line in existing_lines:
        match = assignment_re.match(line)
        if match:
            name = match.group(1)
            output_lines.append(f"{name} = {json.dumps(values[name], ensure_ascii=False)}")
            updated.add(name)
        else:
            output_lines.append(line)
    if updated != set(DESKTOP_GUI_LLM_CONFIG_FIELDS):
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.append("# Text LLM settings saved by Veritas desktop GUI.")
        for name in DESKTOP_GUI_LLM_CONFIG_FIELDS:
            if name not in updated:
                output_lines.append(f"{name} = {json.dumps(values[name], ensure_ascii=False)}")
    path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    return path


def _desktop_gui_status_label(status):
    return {
        "idle": "待命",
        "running": "处理中",
        "succeeded": "已完成",
        "failed": "需处理",
        "canceled": "已停止",
    }.get(str(status or "").lower(), str(status or "未知"))


def _desktop_gui_report_type_label(report_type):
    return {
        "complete": "完整报告",
        "limited": "受限报告",
        "failed": "诊断报告",
        "succeeded": "完整报告",
        "running": "生成中",
        "canceled": "已停止",
        "idle": "待生成",
    }.get(str(report_type or "").lower(), str(report_type or "待生成"))


def _desktop_gui_risk_label(risk_level, status=None):
    risk_text = str(risk_level or "").strip()
    if risk_text.lower() == "failed":
        return "暂无评分"
    risk_map = {
        "低": "低",
        "中": "中",
        "高": "高",
        "严重证据冲突": "严重",
    }
    if risk_text:
        return risk_map.get(risk_text, risk_text)
    if str(status or "").lower() == "failed":
        return "暂无评分"
    return "待评估"


def _desktop_gui_stage_label(current, total, raw_label):
    label = str(raw_label or "").strip()
    label = re.sub(r"^阶段\s*\d+\s*/\s*\d+\s*", "", label).strip()
    if "开始LLM审查" in label:
        label = "LLM 审查"
    elif "LLM审查完成" in label:
        label = "LLM 审查完成"
    else:
        label = DESKTOP_GUI_STAGE_LABELS.get(label, label)
    return f"阶段 {current}/{total} · {label}" if label else f"阶段 {current}/{total}"


def desktop_gui_progress_from_log_line(line):
    text = str(line or "")
    match = re.search(r"(\d+)\s*/\s*(\d+)\s+([0-9]+(?:\.[0-9]+)?)%\s*(.*)$", text)
    if not match:
        return None
    current = int(match.group(1))
    total = max(int(match.group(2)), 1)
    percent = max(0.0, min(float(match.group(3)), 100.0))
    label = _desktop_gui_stage_label(current, total, match.group(4))
    return {"current": current, "total": total, "percent": percent, "label": label}


def _desktop_gui_preflight_status_label(result):
    error_class = str(getattr(result, "error_class", "") or (result.get("error_class") if isinstance(result, dict) else "") or "")
    ok = bool(getattr(result, "ok", False) if not isinstance(result, dict) else result.get("ok"))
    explicit_status = result.get("status") if isinstance(result, dict) else ""
    if explicit_status:
        return str(explicit_status), ok
    if ok:
        return "可达", True
    if error_class == "missing_required_config":
        return "配置", False
    if error_class == "provider_auth_failed":
        return "认证", False
    if error_class == "provider_unavailable":
        return "不可达", False
    return "失败", False


def desktop_gui_config_snapshot(config, preflight_results=None):
    """Return compact, secret-free config rows for the desktop sidebar."""
    config = config or {}
    preflight_results = preflight_results or {}
    rows = []
    capabilities = config.get("capabilities") or {}
    for key, label in DESKTOP_GUI_CONFIG_CAPABILITIES:
        capability = capabilities.get(key) or {}
        ok = bool(capability.get("ok"))
        status = "正常" if ok else "配置"
        if key in preflight_results:
            status, ok = _desktop_gui_preflight_status_label(preflight_results[key])
        rows.append({"label": label, "status": status, "ok": ok})
    dependencies = config.get("optional_dependencies") or {}
    for key, label in DESKTOP_GUI_CONFIG_DEPENDENCIES:
        ok = bool(dependencies.get(key))
        rows.append({"label": label, "status": "正常" if ok else "缺失", "ok": ok})
    ready_count = sum(1 for row in rows if row["ok"])
    if not rows:
        return {"summary": "不可用", "rows": []}
    suffix = " · 待配置" if not config.get("ok", True) else ""
    return {"summary": f"{ready_count}/{len(rows)} 正常{suffix}", "rows": rows}


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def desktop_gui_checked_config_snapshot_from_namespace(namespace, llm_preflight_runner=None, mineru_preflight_runner=None, timeout=6):
    """Run desktop capability checks through a globals-like namespace."""
    load_runtime_config = _namespace_value(namespace, "load_runtime_config")
    apply_runtime_config = _namespace_value(namespace, "apply_runtime_config")
    web_runner_config_status = _namespace_value(namespace, "web_runner_config_status")
    preflight_text_llm = _namespace_value(namespace, "preflight_text_llm")
    preflight_mineru = _namespace_value(namespace, "preflight_mineru")
    if not all(callable(func) for func in (load_runtime_config, apply_runtime_config, web_runner_config_status, preflight_text_llm, preflight_mineru)):
        raise RuntimeError("desktop GUI config check namespace is incomplete")
    runtime_config = load_runtime_config(verbose=False)
    apply_runtime_config(runtime_config)
    config = web_runner_config_status()
    preflight_results = {}
    runners = {
        "text_llm": llm_preflight_runner or (lambda: preflight_text_llm(timeout=timeout)),
        "mineru": mineru_preflight_runner or (lambda: preflight_mineru(timeout=timeout)),
    }
    for capability, runner in runners.items():
        preflight_results[capability] = runner()
    return desktop_gui_config_snapshot(config, preflight_results=preflight_results)


def desktop_gui_run_summary(run):
    run = run or {}
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    report_type = summary.get("report_type") or run.get("report_type") or run.get("status") or ""
    status = run.get("status") or "idle"
    risk_level = summary.get("risk_level") or ""
    return {
        "status": status,
        "status_label": _desktop_gui_status_label(status),
        "input_path": run.get("input_path") or "",
        "output": run.get("output") or "",
        "report_type": report_type,
        "report_type_label": _desktop_gui_report_type_label(report_type),
        "risk_level": risk_level,
        "risk_label": _desktop_gui_risk_label(risk_level, status=status),
        "summary": summary.get("summary") or run.get("message") or "",
        "artifacts": {k: v for k, v in (run.get("artifacts") or {}).items() if k in DESKTOP_GUI_ARTIFACT_LABELS and v},
    }


def desktop_gui_start_run(state, input_path, output="", fresh=False):
    output_text = str(output or "").strip()
    return state.start_run(input_path, output=output_text or None, fresh=bool(fresh))


def open_desktop_path(path):
    target = Path(path).expanduser().resolve()
    webbrowser.open(target.as_uri())


def desktop_gui_artifact_preview(path, kind, max_chars=500000):
    """Return a read-only text preview for a desktop report artifact."""
    artifact_path = Path(path).expanduser()
    if kind == "json":
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = artifact_path.read_text(encoding="utf-8", errors="replace")
    if kind == "html":
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "\n", text)
        text = re.sub(r"(?i)</?(?:p|div|section|article|header|footer|main|h[1-6]|li|tr|table|br)[^>]*>", "\n", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + f"\n\n[预览已截断，完整文件: {artifact_path}]"
    return text


def desktop_gui_followup_context_from_namespace(namespace, run):
    """Build the formal follow-up context from a recorded desktop GUI run."""
    report_action_context = _namespace_value(namespace, "_report_action_context")
    if not callable(report_action_context):
        raise RuntimeError("desktop GUI follow-up namespace is incomplete")
    run = run if isinstance(run, dict) else {}
    artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), dict) else {}
    json_path = artifacts.get("json")
    if not json_path:
        raise ValueError("followup_json_artifact_required")
    payload = json.loads(Path(json_path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("followup_json_artifact_invalid")
    report_type = payload.get("report_type") or (payload.get("meta") or {}).get("artifact_type") or "complete"
    if report_type == "failed":
        raise ValueError("failed_report_followup_blocked")
    report = payload.get("llm_report") if isinstance(payload.get("llm_report"), dict) else {}
    meta = dict(payload.get("meta") if isinstance(payload.get("meta"), dict) else {})
    stat_result = payload.get("stat_result") if isinstance(payload.get("stat_result"), dict) else {}
    artifact_paths = dict(meta.get("artifact_paths") if isinstance(meta.get("artifact_paths"), dict) else {})
    for kind in ("html", "markdown", "json"):
        if artifacts.get(kind):
            artifact_paths[kind] = artifacts[kind]
    meta["artifact_type"] = report_type
    meta["report_type"] = report_type
    meta["artifact_paths"] = artifact_paths
    if not meta.get("followups_dir"):
        anchor = artifact_paths.get("html") or artifact_paths.get("markdown") or json_path
        meta["followups_dir"] = str(Path(anchor).expanduser().parent / "followups")
    input_path = run.get("input_path") or payload.get("paper") or json_path
    return report_action_context(report, input_path, meta, stat_result)


def desktop_gui_generate_followup_draft_from_namespace(namespace, kind, run, language="zh", tone="conservative", timeout=None):
    generator = _namespace_value(namespace, "generate_and_save_followup_draft")
    if not callable(generator):
        raise RuntimeError("desktop GUI follow-up namespace is incomplete")
    context = desktop_gui_followup_context_from_namespace(namespace, run)
    return generator(
        kind,
        context,
        language=language,
        identity=context.get("paper_identity"),
        selected_issues=context.get("top_issues"),
        custom_concerns=None,
        tone=tone,
        disclaimer_confirmed=True,
        timeout=timeout,
    )


__all__ = [
    "DESKTOP_GUI_ARTIFACT_LABELS",
    "DESKTOP_GUI_FOLLOWUP_LABELS",
    "DESKTOP_GUI_CONFIG_CAPABILITIES",
    "DESKTOP_GUI_CONFIG_DEPENDENCIES",
    "DESKTOP_GUI_LLM_CONFIG_FIELDS",
    "DESKTOP_GUI_STAGE_LABELS",
    "desktop_gui_config_file_path",
    "desktop_gui_write_llm_config",
    "_desktop_gui_status_label",
    "_desktop_gui_report_type_label",
    "_desktop_gui_risk_label",
    "_desktop_gui_stage_label",
    "desktop_gui_progress_from_log_line",
    "_desktop_gui_preflight_status_label",
    "desktop_gui_config_snapshot",
    "desktop_gui_checked_config_snapshot_from_namespace",
    "desktop_gui_run_summary",
    "desktop_gui_start_run",
    "open_desktop_path",
    "desktop_gui_artifact_preview",
    "desktop_gui_followup_context_from_namespace",
    "desktop_gui_generate_followup_draft_from_namespace",
]
