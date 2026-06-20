"""Local Web Runner helper boundary."""

import datetime
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .artifacts import _artifact_base_from_output
from .file_utils import _safe_name
from .text_utils import _brief_text


def _web_runner_now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _web_runner_history_path(path=None):
    return Path(path) if path else Path(".veritas_web") / "runs.json"


def _web_runner_output_base(output):
    if not output:
        return None
    base = _artifact_base_from_output(Path(output))
    if not base.is_absolute():
        base = Path.cwd() / base
    return base


def _web_runner_run_id(input_path):
    seed = f"{time.time()}:{input_path}:{os.getpid()}"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]}"


def _web_runner_timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _web_runner_input_parts(input_path):
    path = Path(str(input_path or "").strip()).expanduser()
    name = path.name or "audit_project"
    looks_like_file = path.is_file() or (not path.exists() and bool(path.suffix))
    project = path.stem if looks_like_file else name
    parent = path.parent if looks_like_file else path.parent
    return parent, _safe_name(project)


def web_runner_default_output_stem(input_path, timestamp=None):
    parent, project = _web_runner_input_parts(input_path)
    stamp = timestamp or _web_runner_timestamp()
    return str(parent / f"{project}_{stamp}" / "audit_report")


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def web_runner_default_output_stem_from_namespace(namespace, input_path, timestamp=None):
    timestamp_func = _namespace_value(namespace, "_web_runner_timestamp", _web_runner_timestamp)
    return web_runner_default_output_stem(input_path, timestamp=timestamp or timestamp_func())


def _web_runner_safe_run(run):
    public = dict(run or {})
    public.pop("_process", None)
    public.pop("_cancel_requested", None)
    return public


def _web_runner_report_summary_from_payload(payload, report_type):
    if not isinstance(payload, dict):
        return {}
    report = payload.get("llm_report") if isinstance(payload.get("llm_report"), dict) else {}
    if not report:
        report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    source = report or payload
    summary = {
        "summary": _brief_text(source.get("summary", ""), 500),
        "risk_level": source.get("risk_level", ""),
        "report_type": payload.get("report_type") or source.get("report_type") or report_type,
    }
    failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
    if failure or summary["report_type"] == "failed":
        summary.update({
            "summary": _brief_text(failure.get("message") or summary.get("summary") or "审查失败，已生成失败诊断。", 500),
            "risk_level": summary.get("risk_level") or "failed",
            "report_type": "failed",
            "failure_capability": failure.get("capability", ""),
            "failure_error": failure.get("error_class", ""),
            "complete_report_generated": bool(payload.get("complete_report_generated")),
        })
    return summary


def _web_runner_capability_status(config, capability_name, errors):
    capability = getattr(config, capability_name)
    missing = [e for e in errors if e.get("capability") == capability.name]
    payload = {
        "name": capability.name,
        "ok": not missing,
        "missing": [e.get("field") for e in missing],
        "api_key_configured": bool(capability.api_key),
        "api_url_configured": bool(capability.api_url),
        "base_url_configured": bool(capability.base_url),
        "model_configured": bool(capability.model),
    }
    if capability.model:
        payload["model"] = capability.model
    return payload


def web_runner_config_status_from_namespace(namespace):
    """Return local configuration status without exposing secret values."""
    load_runtime_config = _namespace_value(namespace, "load_runtime_config")
    if not callable(load_runtime_config):
        raise RuntimeError("web runner config namespace is incomplete")
    config = load_runtime_config(verbose=False)
    errors = config.validation_errors()
    return {
        "ok": not errors,
        "errors": errors,
        "capabilities": {
            "text_llm": _web_runner_capability_status(config, "text_llm", errors),
            "mineru": _web_runner_capability_status(config, "mineru", errors),
            "image_semantic": _web_runner_capability_status(config, "image_semantic", errors),
            "reference_lookup": _web_runner_capability_status(config, "reference_lookup", errors),
            "image_detector": _web_runner_capability_status(config, "image_detector", errors),
        },
        "optional_dependencies": {
            "python_docx": bool(_namespace_value(namespace, "DOCX_SUPPORTED", False)),
            "openpyxl": bool(_namespace_value(namespace, "EXCEL_SUPPORTED", False)),
        },
        "repair_files": ["config.example.py", "config.py", "environment variables"],
    }


def pick_local_path(mode, dialog_runner=None):
    """Open a local native picker when available; never browse files over HTTP."""
    if mode not in {"input_file", "input_directory", "output_directory"}:
        return {"ok": False, "error": "unsupported_picker_mode"}
    try:
        if dialog_runner is not None:
            selected = dialog_runner(mode)
        else:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if mode == "input_file":
                selected = filedialog.askopenfilename(title="选择审查文件")
            elif mode == "input_directory":
                selected = filedialog.askdirectory(title="选择审查目录", mustexist=True)
            else:
                selected = filedialog.askdirectory(title="选择输出目录", mustexist=False)
            root.destroy()
        if not selected:
            return {"ok": False, "error": "canceled", "mode": mode}
        return {"ok": True, "mode": mode, "path": str(Path(selected).expanduser())}
    except Exception as exc:
        return {"ok": False, "error": "picker_unavailable", "message": f"{type(exc).__name__}: {_brief_text(str(exc), 240)}", "mode": mode}


def dropped_local_path_from_uri_text(text):
    """Resolve the first file:// URI from a drag-and-drop text payload."""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.lower().startswith("file://"):
            continue
        parsed = urllib.parse.urlparse(line)
        if parsed.scheme.lower() != "file":
            continue
        path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path or ""))
        if path:
            return path
    return ""


__all__ = [
    "_web_runner_now",
    "_web_runner_history_path",
    "_web_runner_output_base",
    "_web_runner_run_id",
    "_web_runner_timestamp",
    "_web_runner_input_parts",
    "web_runner_default_output_stem",
    "web_runner_default_output_stem_from_namespace",
    "_web_runner_safe_run",
    "_web_runner_report_summary_from_payload",
    "_web_runner_capability_status",
    "web_runner_config_status_from_namespace",
    "pick_local_path",
    "dropped_local_path_from_uri_text",
]
