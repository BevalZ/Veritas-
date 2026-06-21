"""Run logging, progress, and resume-event helpers."""

import builtins
import json
import time
from pathlib import Path

from .file_utils import _safe_name

__all__ = [
    "get_output_base",
    "setup_run_logging",
    "get_resume_dir",
    "resume_event",
    "_allow_llm_cache_read",
    "detect_pdf_input",
    "run_cache_use_manifest",
    "run_input_manifest",
    "record_preflight_result",
    "run_extraction_route",
    "run_scope_flags_from_args",
    "progress_bar",
    "save_mineru_artifacts",
]

_ORIGINAL_PRINT = builtins.print
_RUN_LOG_FILE = None
_RUN_OUTPUT_DIR = None
_RUN_OUTPUT_STEM = None
_RESUME_EVENTS_ENABLED = True


def get_output_base(input_path: Path):
    """Return the base output directory and stem for run artifacts."""
    input_path = Path(input_path)
    if input_path.is_dir():
        return input_path, input_path.name or "audit_report"
    return input_path.parent, input_path.stem


def setup_run_logging(input_path: Path):
    """Tee print output to the console and the run log file."""
    global _RUN_LOG_FILE, _RUN_OUTPUT_DIR, _RUN_OUTPUT_STEM
    out_dir, stem = get_output_base(Path(input_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    _RUN_OUTPUT_DIR = out_dir
    _RUN_OUTPUT_STEM = _safe_name(stem)
    _RUN_LOG_FILE = out_dir / f"{_RUN_OUTPUT_STEM}.paper_audit.log"
    _RUN_LOG_FILE.write_text(
        f"Paper Audit Log\nSTART {time.strftime('%F %T')}\nINPUT {Path(input_path)}\nOUTPUT_DIR {out_dir}\n\n",
        encoding="utf-8",
    )

    def tee_print(*args, **kwargs):
        _ORIGINAL_PRINT(*args, **kwargs)
        try:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            msg = sep.join(str(a) for a in args) + end
            with _RUN_LOG_FILE.open("a", encoding="utf-8", errors="replace") as f:
                f.write(msg)
        except Exception:
            pass

    builtins.print = tee_print
    print(f"🧾 日志文件: {_RUN_LOG_FILE}")
    return _RUN_LOG_FILE


def get_resume_dir(output_dir: Path, output_stem: str):
    """Return and create the resume cache directory for a run."""
    d = Path(output_dir) / f".{_safe_name(output_stem)}.paper_audit_resume"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resume_event(resume_dir: Path, step: str, status: str, detail: str = "", **extra):
    """Record a resume event in JSONL form and mirror it to the run log."""
    if not _RESUME_EVENTS_ENABLED:
        return
    try:
        event = {"time": time.strftime("%F %T"), "step": step, "status": status, "detail": detail}
        event.update(extra)
        manifest = Path(resume_dir) / "resume_manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(f"🧭 断点记录: {step} | {status} | {detail}")
    except Exception as e:
        print(f"⚠️ 写入断点记录失败: {e}")


def _allow_llm_cache_read(no_resume=False, llm_cache_only=False):
    return (not bool(no_resume)) or bool(llm_cache_only)


def detect_pdf_input(input_path, pdf_suffixes=None):
    """Return whether the input path is a PDF or a directory containing a PDF."""
    path = Path(input_path)
    suffixes = {s.lower() for s in (pdf_suffixes or {".pdf"})}
    if path.suffix.lower() in suffixes:
        return True
    if path.is_dir():
        try:
            return any(p.is_file() and p.suffix.lower() in suffixes for p in path.rglob("*"))
        except Exception:
            return False
    return False


def run_input_manifest(input_path, runtime):
    """Build the input manifest recorded in a per-run workspace."""
    path = Path(input_path)
    return {
        "input": str(path),
        "resolved_input": str(path.resolve()),
        "input_type": "directory" if path.is_dir() else "file",
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "created_at": runtime["local_time"],
        "runtime": runtime,
    }


def run_cache_use_manifest(
    resume_dir,
    no_resume,
    allow_llm_cache_read,
    allow_llm_cache_write,
    extract_cache_version,
    image_semantic_cache_version,
):
    """Build the cache-use manifest recorded in a per-run workspace."""
    return {
        "shared_resume_dir": str(resume_dir),
        "no_resume": bool(no_resume),
        "allow_llm_cache_read": bool(allow_llm_cache_read),
        "allow_llm_cache_write": bool(allow_llm_cache_write),
        "extract_cache_version": extract_cache_version,
        "image_semantic_cache_version": image_semantic_cache_version,
    }


def record_preflight_result(
    preflight_results,
    result,
    run_workspace,
    resume_dir,
    record_json,
    resume_event_func,
    timestamp_func=None,
):
    """Append and persist a critical-capability preflight result."""
    timestamp = timestamp_func or (lambda: time.strftime("%F %T"))
    preflight_results.append(result.to_dict())
    record_json(run_workspace, "preflight.json", {
        "results": preflight_results,
        "updated_at": timestamp(),
    })
    resume_event_func(
        resume_dir,
        f"preflight_{result.capability}",
        "ok" if result.ok else "failed",
        result.message or "ok",
        error_class=result.error_class,
    )


def run_extraction_route(input_path, use_mineru_default=False):
    """Return the run-summary extraction route label for an input path."""
    path = Path(input_path)
    suffix = path.suffix.lower()
    if path.is_dir():
        return "directory_multi_format"
    if suffix == ".pdf":
        return "mineru_pdf" if use_mineru_default else "raw_pdf_stream"
    if suffix == ".docx":
        return "direct_docx"
    if suffix in {".xlsx", ".xlsm", ".csv"}:
        return "spreadsheet_text"
    return f"{suffix.lstrip('.') or 'file'}_text"


def run_scope_flags_from_args(args):
    """Return user-visible scope-limiting flags for the run summary."""
    scope_flags = []
    for attr, label in (
        ("no_mineru", "--no-mineru"),
        ("no_reference_online", "--no-reference-online"),
        ("no_image_semantic", "--no-image-semantic"),
        ("no_image_detector", "--no-image-detector"),
        ("llm_cache_only", "--llm-cache-only"),
    ):
        if getattr(args, attr, False):
            scope_flags.append(label)
    for attr, label in (
        ("reference_online_limit", "--reference-online-limit"),
        ("image_audit_limit", "--image-audit-limit"),
        ("image_semantic_limit", "--image-semantic-limit"),
        ("image_detector_limit", "--image-detector-limit"),
    ):
        if getattr(args, attr, None) is not None:
            scope_flags.append(f"{label}={getattr(args, attr)}")
    return scope_flags


def progress_bar(current, total, label="", width=28):
    """Print a text progress bar and keep each update in the run log."""
    try:
        total = max(int(total), 1)
        current = max(0, min(int(current), total))
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        pct = current * 100 / total
        print(f"📊 [{bar}] {current}/{total} {pct:5.1f}% {label}")
    except Exception:
        print(f"📊 {current}/{total} {label}")


def save_mineru_artifacts(zip_url: str, zip_data: bytes, source_name: str, output_dir=None, batch_id=None):
    """Save MinerU download URL and ZIP artifacts alongside the run outputs."""
    out_dir = Path(output_dir) if output_dir else (_RUN_OUTPUT_DIR or Path.cwd())
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(Path(source_name).stem if source_name else (batch_id or "mineru"))
    suffix = f".{_safe_name(batch_id)}" if batch_id else ""
    link_path = out_dir / f"{stem}{suffix}.mineru_url.txt"
    zip_path = out_dir / f"{stem}{suffix}.mineru.zip"
    link_path.write_text(zip_url + "\n", encoding="utf-8")
    zip_path.write_bytes(zip_data)
    print(f"  🔗 MinerU下载链接已保存: {link_path}")
    print(f"  📦 MinerU zip已保存: {zip_path} ({len(zip_data)/1024/1024:.2f}MB)")
    return zip_path, link_path
