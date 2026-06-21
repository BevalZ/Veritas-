"""Local report action service helpers."""

import json
import platform
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from .report_action_panel import report_action_service_url
from .text_utils import _brief_text

__all__ = [
    "report_action_service_health",
    "_report_action_entrypoint",
    "ensure_report_action_service_from_namespace",
    "open_html_artifact",
    "_read_json_request_body",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def report_action_service_health(host="127.0.0.1", port=8765, timeout=0.5):
    """Return the local report action service health payload, or None when unavailable."""
    try:
        with urllib.request.urlopen(f"{report_action_service_url(host, port)}/health", timeout=timeout) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            if payload.get("ok"):
                return payload
    except Exception:
        return None
    return None


def _report_action_entrypoint():
    candidate = Path(__file__).resolve().parents[1] / "paper_audit.py"
    if candidate.exists():
        return candidate
    return Path(sys.argv[0]).resolve()


def ensure_report_action_service_from_namespace(namespace, host="127.0.0.1", port=8765, log_path: Path = None, startup_timeout=2.0):
    """Start or reuse the localhost action service used by generated HTML reports."""
    health_func = _namespace_value(namespace, "report_action_service_health", report_action_service_health)
    service_url_func = _namespace_value(namespace, "report_action_service_url", report_action_service_url)
    entrypoint_func = _namespace_value(namespace, "_report_action_entrypoint", _report_action_entrypoint)
    subprocess_module = _namespace_value(namespace, "subprocess", subprocess)
    sys_module = _namespace_value(namespace, "sys", sys)

    existing = health_func(host=host, port=port, timeout=0.3)
    if existing:
        return {"ok": True, "status": "already_running", "url": service_url_func(host, port), "health": existing}

    command = [
        sys_module.executable,
        str(entrypoint_func()),
        "--serve-report-actions",
        "--report-actions-port",
        str(int(port)),
    ]
    popen_kwargs = {
        "stdin": subprocess_module.DEVNULL,
        "start_new_session": True,
    }
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8")
        popen_kwargs["stdout"] = log_file
        popen_kwargs["stderr"] = subprocess_module.STDOUT
    else:
        log_file = None
        popen_kwargs["stdout"] = subprocess_module.DEVNULL
        popen_kwargs["stderr"] = subprocess_module.DEVNULL

    try:
        process = subprocess_module.Popen(command, **popen_kwargs)
    except Exception as e:
        if log_file:
            log_file.close()
        return {"ok": False, "status": "start_failed", "url": service_url_func(host, port), "error": f"{type(e).__name__}: {_brief_text(str(e), 240)}"}
    finally:
        if log_file:
            log_file.close()

    deadline = time.time() + float(startup_timeout)
    while time.time() < deadline:
        health = health_func(host=host, port=port, timeout=0.3)
        if health:
            return {"ok": True, "status": "started", "url": service_url_func(host, port), "pid": process.pid, "health": health}
        if process.poll() is not None:
            return {"ok": False, "status": "exited", "url": service_url_func(host, port), "pid": process.pid, "returncode": process.returncode}
        time.sleep(0.1)
    return {"ok": True, "status": "starting", "url": service_url_func(host, port), "pid": process.pid}


def open_html_artifact(html_path: Path):
    html_abs = str(Path(html_path).resolve())
    webbrowser.open(f"file:///{html_abs}" if platform.system() == "Windows" else f"file://{html_abs}")


def _read_json_request_body(handler, max_bytes=2_000_000):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length > max_bytes:
        raise ValueError("request_too_large")
    body = handler.rfile.read(length).decode("utf-8", errors="replace")
    return json.loads(body or "{}")
