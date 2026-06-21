"""Local Web Runner helper boundary."""

import datetime
import hashlib
import json
import os
import sys
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


def web_runner_start_command_from_namespace(namespace, input_path, output=None, fresh=False):
    """Resolve a Web Runner input and build the isolated audit subprocess command."""
    path_cls = _namespace_value(namespace, "Path", Path)
    brief_text = _namespace_value(namespace, "_brief_text", _brief_text)
    resolve_input = _namespace_value(namespace, "resolve_web_runner_input_path")
    search_roots = _namespace_value(namespace, "_web_runner_common_search_roots")
    default_output = _namespace_value(namespace, "web_runner_default_output_stem", web_runner_default_output_stem)
    entrypoint = _namespace_value(namespace, "_report_action_entrypoint")
    sys_module = _namespace_value(namespace, "sys", sys)

    input_text = str(input_path or "").strip()
    if not input_text:
        return {
            "ok": False,
            "response": {"ok": False, "error": "input_path_required", "message": "请输入文件或目录路径。"},
            "status": 400,
        }
    if not callable(resolve_input) or not callable(search_roots):
        raise RuntimeError("web runner start namespace is incomplete")
    resolved = resolve_input(input_text, search_roots=search_roots())
    if not resolved.get("ok"):
        return {
            "ok": False,
            "response": resolved,
            "status": 409 if resolved.get("error") == "ambiguous_input_path" else 400,
        }

    resolved_input = str(path_cls(resolved.get("path")).expanduser())
    if not callable(entrypoint):
        raise RuntimeError("web runner entrypoint namespace is incomplete")
    command = [
        sys_module.executable,
        str(entrypoint()),
        resolved_input,
        "--json",
        "--no-open",
    ]
    output_text = str(output or "").strip()
    if not output_text:
        output_text = default_output(resolved_input) if callable(default_output) else web_runner_default_output_stem(resolved_input)
    if output_text:
        try:
            path_cls(output_text).expanduser().parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {
                "ok": False,
                "response": {"ok": False, "error": "output_prepare_failed", "message": f"{type(e).__name__}: {brief_text(str(e), 240)}"},
                "status": 500,
            }
        command.extend(["-o", output_text])
    if fresh:
        command.append("--fresh")

    return {
        "ok": True,
        "input_path": resolved_input,
        "output": output_text,
        "fresh": bool(fresh),
        "command": command,
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


def web_runner_page_styles():
    """Return the static CSS used by the local Web Runner page."""
    return """:root { color-scheme: light; --bg:#f5f5f3; --panel:#ffffff; --line:#d8d8d3; --text:#191919; --muted:#6a6a64; --accent:#155e75; --danger:#b42318; --ok:#237a4b; --warn:#9a5b00; --soft:#f0f7f8; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; font-size:14px; letter-spacing:0; }
header { height:54px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; border-bottom:1px solid var(--line); background:#fff; }
h1 { font-size:18px; margin:0; font-weight:750; }
main { display:grid; grid-template-columns:minmax(360px, 520px) minmax(420px, 1fr); gap:16px; padding:16px; max-width:1440px; margin:0 auto; }
section { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
h2 { font-size:14px; margin:0 0 12px; font-weight:750; }
label { display:block; color:var(--muted); font-size:12px; margin:10px 0 5px; }
input[type="text"] { width:100%; min-height:38px; border:1px solid var(--line); border-radius:6px; padding:8px 10px; font:inherit; background:#fff; color:var(--text); }
input[readonly] { background:#f7f7f5; color:#2f2f2c; cursor:default; }
.drop-zone { border:1px dashed var(--line); border-radius:8px; padding:10px; background:#fbfbfa; transition:border-color .12s ease, background .12s ease; }
.drop-zone.dragover { border-color:var(--accent); background:#edf7f8; }
.drop-zone input[type="text"] { margin-top:5px; }
.drop-hint { min-height:18px; margin-top:6px; }
.path-row { display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:8px; align-items:end; }
.path-row.output { grid-template-columns:minmax(0,1fr) auto; margin-top:5px; }
.row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.actions { margin-top:12px; display:flex; gap:8px; }
button, .linkbtn { min-height:36px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--text); padding:7px 12px; font:inherit; font-weight:650; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
button.danger { border-color:#e3aaa5; color:var(--danger); }
button:disabled { opacity:.55; cursor:not-allowed; }
.status { display:inline-flex; min-height:26px; align-items:center; padding:3px 8px; border-radius:999px; border:1px solid var(--line); color:var(--muted); font-size:12px; }
.status.succeeded { color:var(--ok); border-color:#9bc7ad; }
.status.failed, .status.canceled { color:var(--danger); border-color:#e3aaa5; }
.hero-strip { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-bottom:12px; }
.step { border:1px solid var(--line); border-radius:6px; padding:8px; background:#fbfbfa; min-height:58px; }
.step span { display:block; color:var(--muted); font-size:12px; }
.step strong { display:block; margin-top:3px; font-size:13px; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.cell { border:1px solid var(--line); border-radius:6px; padding:8px; min-height:54px; overflow-wrap:anywhere; }
.cell span { display:block; color:var(--muted); font-size:12px; }
.cell strong { display:block; margin-top:3px; font-size:13px; }
#log { height:430px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#161616; color:#f4f4f0; border-radius:6px; padding:12px; font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.run { border-top:1px solid var(--line); padding:10px 0; }
.run:first-child { border-top:0; padding-top:0; }
.run-title { display:flex; justify-content:space-between; gap:8px; align-items:center; }
.run path, code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.muted { color:var(--muted); font-size:12px; overflow-wrap:anywhere; }
.links { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
.check { display:flex; align-items:center; gap:7px; margin-top:10px; color:var(--text); }
.current-card { border:1px solid var(--line); border-radius:6px; padding:9px; margin-bottom:10px; min-height:58px; }
.current-card span { display:block; color:var(--muted); font-size:12px; }
.current-card strong { display:block; margin-top:3px; overflow-wrap:anywhere; }
.current-actions { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0 10px; min-height:36px; }
.report-panel { border:1px solid var(--line); border-radius:8px; padding:10px; margin:0 0 10px; background:var(--soft); }
.report-panel.failed, .report-panel.canceled { background:#fff7f6; }
.report-panel.succeeded, .report-panel.complete, .report-panel.limited { background:#f3faf6; }
.report-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
.report-head h3 { margin:0; font-size:14px; }
.report-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.report-cell { border:1px solid rgba(0,0,0,.08); border-radius:6px; padding:8px; background:rgba(255,255,255,.72); overflow-wrap:anywhere; }
.report-cell span { display:block; color:var(--muted); font-size:12px; }
.report-cell strong { display:block; margin-top:3px; font-size:13px; }
.report-summary { margin:8px 0 0; color:#2f2f2c; line-height:1.55; overflow-wrap:anywhere; }
.feedback { min-height:34px; border:1px solid var(--line); border-radius:6px; padding:8px; margin-bottom:10px; background:#fbfbfa; color:#2f2f2c; overflow-wrap:anywhere; }
.feedback.failed { border-color:#e3aaa5; color:var(--danger); background:#fff7f6; }
.feedback.succeeded { border-color:#9bc7ad; color:var(--ok); background:#f3faf6; }
@media (max-width:900px) { main { grid-template-columns:1fr; padding:10px; } header { padding:0 12px; } #log { height:320px; } .hero-strip, .report-grid { grid-template-columns:1fr; } }"""


def render_web_runner_page():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Veritas Web Runner</title>
<style>
""" + web_runner_page_styles() + """
</style>
</head>
<body>
<header><h1>Veritas Web Runner</h1><span id="topStatus" class="status">local</span></header>
<main>
  <div>
    <section>
      <h2>审查任务</h2>
      <div class="hero-strip" aria-label="workflow">
        <div class="step"><span>1. 输入</span><strong>选择论文文件或项目目录</strong></div>
        <div class="step"><span>2. 审查</span><strong>本地启动正式 CLI 流程</strong></div>
        <div class="step"><span>3. 输出</span><strong>直接打开生成报告</strong></div>
      </div>
      <div id="inputDropZone" class="drop-zone">
        <label for="inputPath">输入路径 / 拖拽区域</label>
        <div class="path-row">
          <input id="inputPath" type="text" autocomplete="off" readonly placeholder="/path/to/paper-or-folder">
          <button id="pickFileBtn" type="button">文件</button>
          <button id="pickDirectoryBtn" type="button">目录</button>
        </div>
        <div id="dropHint" class="muted drop-hint">拖拽文件或目录到这里</div>
      </div>
      <label for="outputPath">输出路径</label>
      <div class="path-row output">
        <input id="outputPath" type="text" autocomplete="off" readonly placeholder="">
        <button id="pickOutputBtn" type="button">输出</button>
      </div>
      <label class="check"><input id="fresh" type="checkbox"> 从头重跑</label>
      <div class="actions">
        <button id="startBtn" class="primary">Start</button>
        <button id="cancelBtn" class="danger" disabled>Cancel</button>
      </div>
    </section>
    <section style="margin-top:16px">
      <h2>配置状态</h2>
      <div id="config" class="grid"></div>
    </section>
  </div>
  <div>
    <section>
      <div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">当前运行</h2><span id="runStatus" class="status">idle</span></div>
      <div id="currentRun" class="current-card"><span>输入</span><strong>No active run</strong></div>
      <div id="currentOutput" class="current-card"><span>输出</span><strong></strong></div>
      <div id="runFeedback" class="feedback">选择输入后点击 Start，生成的报告会在这里显示。</div>
      <div id="reportPanel" class="report-panel">
        <div class="report-head"><h3>报告输出</h3><span id="reportState" class="status">pending</span></div>
        <div class="report-grid">
          <div class="report-cell"><span>报告类型</span><strong id="reportType">待生成</strong></div>
          <div class="report-cell"><span>风险级别</span><strong id="reportRisk">待生成</strong></div>
          <div class="report-cell"><span>输出目录</span><strong id="reportFolder">待生成</strong></div>
        </div>
        <p id="reportSummary" class="report-summary">报告生成后会显示摘要和打开入口。</p>
        <div id="currentActions" class="current-actions"></div>
      </div>
      <div id="log" aria-label="live log"></div>
    </section>
    <section style="margin-top:16px">
      <h2>最近运行</h2>
      <div id="runs"></div>
    </section>
  </div>
</main>
<script>
const $ = (id) => document.getElementById(id);
let activeRunId = null;
let logOffset = 0;
let timer = null;
let selectedInputKind = '';
let lastRun = null;
async function api(path, options={}) {
  const res = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}
function setStatus(text, cls='') {
  const el = $('runStatus');
  el.className = 'status ' + cls;
  el.textContent = text;
}
function setFeedback(text, cls='') {
  const el = $('runFeedback');
  if (!el) return;
  el.className = 'feedback ' + cls;
  el.textContent = text || '选择输入后点击 Start，生成的报告会在这里显示。';
}
function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function pathSeparator(path) {
  return String(path || '').includes('\\\\') ? '\\\\' : '/';
}
function trimPath(path) {
  return String(path || '').trim().replace(/[\\\\/]+$/, '');
}
function pathBaseName(path) {
  const cleaned = trimPath(path);
  const sep = pathSeparator(cleaned);
  return cleaned.split(sep).filter(Boolean).pop() || 'audit_project';
}
function pathParent(path) {
  const cleaned = trimPath(path);
  const sep = pathSeparator(cleaned);
  const parts = cleaned.split(sep);
  parts.pop();
  const parent = parts.join(sep);
  if (parent) return parent;
  return cleaned.startsWith(sep) ? sep : '.';
}
function joinPath(...parts) {
  const filtered = parts.map(p => String(p || '')).filter(Boolean);
  const sep = filtered.some(p => p.includes('\\\\')) ? '\\\\' : '/';
  const joined = filtered.join(sep);
  return sep === '\\\\' ? joined.replace(/\\\\{2,}/g, '\\\\') : joined.replace(/\\/{2,}/g, '/');
}
function stripExtension(name) {
  const dot = String(name || '').lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}
function safeProjectName(name) {
  return String(name || 'audit_project').replace(/[<>:"/\\\\|?*\\x00-\\x1f]+/g, '_').replace(/[ .]+$/g, '') || 'audit_project';
}
function timestampForOutput(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}
function defaultOutputStemForInput(inputPath, kind = selectedInputKind, date = new Date()) {
  const cleaned = trimPath(inputPath);
  if (!cleaned) return '';
  const base = pathBaseName(cleaned);
  const project = safeProjectName(kind === 'directory' ? base : stripExtension(base));
  return joinPath(pathParent(cleaned), `${project}_${timestampForOutput(date)}`, 'audit_report');
}
function localPathFromFileUri(rawUri) {
  const uri = String(rawUri || '').trim();
  if (!uri.toLowerCase().startsWith('file://')) return '';
  try {
    const parsed = new URL(uri);
    if (parsed.protocol !== 'file:') return '';
    return decodeURIComponent(parsed.pathname || '').replace(/^\\/([A-Za-z]:\\/)/, '$1');
  } catch (_e) {
    return decodeURIComponent(uri.replace(/^file:\\/\\//i, ''));
  }
}
function droppedPathFromUriText(text) {
  const lines = String(text || '').split(/\\r?\\n/).map(line => line.trim()).filter(Boolean);
  for (const line of lines) {
    if (line.startsWith('#')) continue;
    const path = localPathFromFileUri(line);
    if (path) return path;
  }
  return '';
}
function droppedPathFromTransferText(dataTransfer) {
  if (!dataTransfer || !dataTransfer.getData) return '';
  for (const type of ['text/uri-list', 'text/plain']) {
    const path = droppedPathFromUriText(dataTransfer.getData(type));
    if (path) return path;
  }
  return '';
}
function setSelectedInputPath(path, kind = '') {
  selectedInputKind = kind;
  $('inputPath').value = path;
  $('dropHint').textContent = path;
  $('outputPath').value = defaultOutputStemForInput(path, kind);
  $('outputPath').dataset.userSelected = '';
  $('inputPath').dispatchEvent(new Event('change', {bubbles: true}));
}
function droppedPathInfoFromDataTransfer(dataTransfer) {
  const uriPath = droppedPathFromTransferText(dataTransfer);
  if (uriPath) return {path: uriPath, kind: 'file'};
  const items = Array.from((dataTransfer && dataTransfer.items) || []);
  for (const item of items) {
    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
    if (entry) {
      const entryPath = entry.fullPath && entry.fullPath !== '/' ? entry.fullPath.replace(/^\\//, '') : entry.name;
      if (entryPath) return {path: entryPath, kind: entry.isDirectory ? 'directory' : 'file'};
    }
  }
  const files = Array.from((dataTransfer && dataTransfer.files) || []);
  if (!files.length) return {path: '', kind: ''};
  const file = files[0];
  return {path: file.path || file.webkitRelativePath || file.name || '', kind: 'file'};
}
function droppedPathFromDataTransfer(dataTransfer) {
  return droppedPathInfoFromDataTransfer(dataTransfer).path;
}
function applyDroppedPath(dataTransfer) {
  const info = droppedPathInfoFromDataTransfer(dataTransfer);
  if (!info.path) return false;
  setSelectedInputPath(info.path, info.kind);
  return true;
}
function dragHasFiles(event) {
  const types = Array.from((event.dataTransfer && event.dataTransfer.types) || []);
  return types.includes('Files');
}
async function chooseLocalPath(mode) {
  try {
    const data = await api('/api/pick-path', {method:'POST', body: JSON.stringify({mode})});
    if (mode === 'input_file') setSelectedInputPath(data.path, 'file');
    if (mode === 'input_directory') setSelectedInputPath(data.path, 'directory');
    if (mode === 'output_directory') {
      $('outputPath').value = joinPath(data.path, 'audit_report');
      $('outputPath').dataset.userSelected = 'true';
    }
  } catch (e) {
    setStatus(e.error || 'picker failed', 'failed');
    setFeedback(e.message || e.error || JSON.stringify(e), 'failed');
    renderReportPanel({status: 'failed', message: e.message || e.error || JSON.stringify(e)});
  }
}
function artifactLinks(run) {
  const arts = run.artifacts || {};
  return ['html','markdown','json','folder'].filter(k => arts[k]).map(k => `<a class="linkbtn" target="_blank" href="/artifact/${encodeURIComponent(run.id)}/${k}">${k}</a>`).join('');
}
function currentArtifactActions(run) {
  const links = artifactLinks(run);
  const retry = run && run.input_path && ['failed', 'canceled'].includes(run.status || '') ? '<button id="retryRunBtn" type="button">Retry</button>' : '';
  return `${links}${retry}`;
}
function reportLabel(reportType, status) {
  const value = reportType || status || '';
  const labels = {
    complete: '完整审查',
    limited: '范围受限审查',
    failed: '失败诊断',
    succeeded: '审查完成',
    running: '审查中',
    canceled: '已取消'
  };
  return labels[value] || value || '待生成';
}
function reportFolderForRun(run) {
  const arts = (run && run.artifacts) || {};
  if (arts.folder) return arts.folder;
  if (run && run.output) return pathParent(run.output);
  return '待生成';
}
function reportSummaryFallback(run) {
  const status = (run && run.status) || '';
  if (status === 'running') return '审查正在运行，日志会持续刷新。';
  if (status === 'succeeded') return '审查完成，报告入口已在下方列出。';
  if (status === 'failed') return (run && run.message) || '审查失败，请查看日志和失败诊断产物。';
  if (status === 'canceled') return (run && run.message) || '运行已取消，可在需要时重试。';
  return '报告生成后会显示摘要和打开入口。';
}
function safePanelClass(value) {
  const allowed = ['complete', 'limited', 'failed', 'succeeded', 'running', 'canceled'];
  return allowed.includes(value || '') ? value : '';
}
function renderReportPanel(run) {
  const active = run || {};
  const summary = active.summary || {};
  const reportType = summary.report_type || active.report_type || '';
  const status = active.status || '';
  const panelClass = safePanelClass(reportType) || safePanelClass(status);
  $('reportPanel').className = `report-panel ${panelClass}`;
  $('reportState').className = `status ${panelClass}`;
  $('reportState').textContent = reportLabel(reportType, status);
  $('reportType').textContent = reportLabel(reportType, status);
  $('reportRisk').textContent = summary.risk_level || (reportType || status ? '未标注' : '待生成');
  $('reportFolder').textContent = reportFolderForRun(active);
  $('reportSummary').textContent = summary.summary || reportSummaryFallback(active);
  $('currentActions').innerHTML = currentArtifactActions(active);
  const retry = $('retryRunBtn');
  if (retry) retry.addEventListener('click', () => retryRun(active));
}
function renderCurrentRun(run) {
  lastRun = run || lastRun;
  const active = run || {};
  const input = active.input_path || $('inputPath').value || 'No active run';
  const output = active.output || $('outputPath').value || '';
  $('currentRun').innerHTML = `<span>输入</span><strong>${escapeHtml(input)}</strong>`;
  $('currentOutput').innerHTML = `<span>输出</span><strong>${escapeHtml(output)}</strong>`;
  renderReportPanel(active);
  setFeedback(active.message || '', active.status || '');
}
function renderRun(run) {
  const summary = run.summary || {};
  const reportType = summary.report_type || run.report_type || run.status || '';
  const summaryLine = summary.summary ? `<div class="muted">${escapeHtml(summary.summary)}</div>` : '';
  const risk = summary.risk_level ? `<span class="status">${escapeHtml(summary.risk_level)}</span>` : '';
  return `<div class="run"><div class="run-title"><strong>${escapeHtml(reportLabel(reportType, run.status))}</strong><span class="status ${escapeHtml(run.status || '')}">${escapeHtml(run.status || '')}</span></div><div class="muted">${escapeHtml(run.input_path || '')}</div><div class="muted">${escapeHtml(run.started_at || '')}</div>${summaryLine}<div class="links">${risk}${artifactLinks(run)}</div></div>`;
}
async function startRunWithPayload(payload) {
  $('log').textContent = '';
  logOffset = 0;
  try {
    const data = await api('/api/runs', {method:'POST', body: JSON.stringify(payload)});
    activeRunId = data.run.id;
    lastRun = data.run;
    $('cancelBtn').disabled = false;
    setStatus('running');
    renderCurrentRun(data.run);
    if (!timer) timer = setInterval(pollLogs, 1200);
    pollLogs();
    refreshRuns();
  } catch (e) {
    setStatus(e.error || 'start failed', 'failed');
    setFeedback(e.message || e.error || JSON.stringify(e), 'failed');
    renderReportPanel({status: 'failed', message: e.message || e.error || JSON.stringify(e)});
  }
}
function startPayloadFromForm() {
  const payload = {input_path: $('inputPath').value, fresh: $('fresh').checked};
  if ($('outputPath').dataset.userSelected === 'true' && $('outputPath').value) {
    payload.output = $('outputPath').value;
  }
  return payload;
}
function retryRun(run) {
  if (!run || !run.input_path) return;
  if (activeRunId) return;
  $('inputPath').value = run.input_path || '';
  $('outputPath').value = run.output || '';
  $('fresh').checked = !!run.fresh;
  startRunWithPayload({input_path: run.input_path, output: run.output, fresh: !!run.fresh});
}
async function refreshRuns() {
  const data = await api('/api/runs');
  $('runs').innerHTML = (data.runs || []).map(renderRun).join('') || '<div class="muted">No runs yet</div>';
  const active = (data.runs || []).find(r => r.status === 'running');
  if (active && !activeRunId) {
    activeRunId = active.id; logOffset = 0; pollLogs();
  }
}
async function refreshConfig() {
  const data = await api('/api/config');
  const caps = data.capabilities || {};
  $('config').innerHTML = Object.keys(caps).map(k => `<div class="cell"><span>${k}</span><strong>${caps[k].ok ? 'ready' : 'needs config'}</strong><div class="muted">${(caps[k].missing || []).join(', ')}</div></div>`).join('') +
    `<div class="cell"><span>python-docx</span><strong>${data.optional_dependencies.python_docx ? 'available' : 'missing'}</strong></div><div class="cell"><span>openpyxl</span><strong>${data.optional_dependencies.openpyxl ? 'available' : 'missing'}</strong></div>`;
}
async function pollLogs() {
  if (!activeRunId) return;
  try {
    const data = await api(`/api/runs/${encodeURIComponent(activeRunId)}/logs?offset=${logOffset}`);
    logOffset = data.offset;
    if (data.lines && data.lines.length) {
      $('log').textContent += data.lines.join('\\n') + '\\n';
      $('log').scrollTop = $('log').scrollHeight;
    }
    const runData = await api(`/api/runs/${encodeURIComponent(activeRunId)}`);
    const run = runData.run;
    renderCurrentRun(run);
    setStatus(run.status || 'unknown', run.status || '');
    $('cancelBtn').disabled = run.status !== 'running';
    if (run.status !== 'running') {
      activeRunId = null;
      clearInterval(timer);
      timer = null;
      refreshRuns();
    }
  } catch (e) {
    setStatus(e.error || 'error', 'failed');
  }
}
$('startBtn').addEventListener('click', async () => {
  if (!$('outputPath').value && $('inputPath').value) {
    $('outputPath').value = defaultOutputStemForInput($('inputPath').value);
  }
  await startRunWithPayload(startPayloadFromForm());
});
$('pickFileBtn').addEventListener('click', () => chooseLocalPath('input_file'));
$('pickDirectoryBtn').addEventListener('click', () => chooseLocalPath('input_directory'));
$('pickOutputBtn').addEventListener('click', () => chooseLocalPath('output_directory'));
$('cancelBtn').addEventListener('click', async () => {
  if (!activeRunId) return;
  await api(`/api/runs/${encodeURIComponent(activeRunId)}/cancel`, {method:'POST', body:'{}'});
  pollLogs();
});
const dropZone = $('inputDropZone');
['dragenter', 'dragover'].forEach(name => dropZone.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
  event.stopPropagation();
  dropZone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach(name => dropZone.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
  event.stopPropagation();
  dropZone.classList.remove('dragover');
  if (name === 'drop') applyDroppedPath(event.dataTransfer);
}));
['dragover', 'drop'].forEach(name => document.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
}));
refreshConfig();
renderCurrentRun(null);
refreshRuns();
</script>
</body>
</html>"""


def web_runner_cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


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
    "web_runner_start_command_from_namespace",
    "pick_local_path",
    "dropped_local_path_from_uri_text",
    "web_runner_page_styles",
    "render_web_runner_page",
    "web_runner_cors_headers",
]
