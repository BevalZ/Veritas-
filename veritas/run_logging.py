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
    "extract_cache_matches",
    "stage1_extract_cache_state",
    "extract_cache_payload",
    "save_stage1_extract_cache",
    "run_cache_use_manifest",
    "text_llm_stage_plan",
    "apply_llm_chunk_coverage_meta",
    "llm_success_cache_payload",
    "llm_failure_cache_payload",
    "llm_chunk_cache_read_state",
    "apply_llm_partial_report_warning",
    "save_llm_failure_cache_result",
    "llm_retry_failure_summary",
    "llm_no_success_failure_summary",
    "llm_merge_done_detail",
    "online_cache_state",
    "save_online_cache_result",
    "image_audit_cache_state",
    "image_semantic_cache_save_callback",
    "image_detector_cache_save_callback",
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


def extract_cache_matches(cached_extract, input_path, use_mineru, cache_version):
    """Return whether a stage-1 extraction cache matches the current run."""
    if not isinstance(cached_extract, dict):
        return False
    return (
        cached_extract.get("input") == str(Path(input_path).resolve())
        and cached_extract.get("use_mineru") == use_mineru
        and cached_extract.get("cache_version") == cache_version
    )


def stage1_extract_cache_state(cached_extract, input_path, use_mineru_default, cache_version):
    """Return normalized stage-1 extraction state for a matching cache payload."""
    if not extract_cache_matches(cached_extract, input_path, use_mineru_default, cache_version):
        return None
    return {
        "full_text": cached_extract.get("full_text", ""),
        "meta": cached_extract.get("meta", {}),
        "file_texts": cached_extract.get("file_texts") or [],
        "raw_pdf": None,
        "use_mineru": cached_extract.get("use_mineru", use_mineru_default),
    }


def extract_cache_payload(
    input_path,
    cache_version,
    use_mineru,
    mineru_lang,
    full_text,
    meta,
    file_texts,
    timestamp_func=None,
):
    """Build the stage-1 extraction cache payload."""
    timestamp = timestamp_func or (lambda: time.strftime("%F %T"))
    return {
        "input": str(Path(input_path).resolve()),
        "cache_version": cache_version,
        "use_mineru": use_mineru,
        "mineru_lang": mineru_lang,
        "full_text": full_text,
        "meta": meta,
        "file_texts": file_texts,
        "saved_at": timestamp(),
    }


def save_stage1_extract_cache(
    extract_cache_path,
    input_path,
    cache_version,
    use_mineru,
    mineru_lang,
    full_text,
    meta,
    file_texts,
    json_save,
    resume_event_func,
    resume_dir,
    timestamp_func=None,
):
    """Persist the stage-1 extraction cache and record its resume event."""
    json_save(
        extract_cache_path,
        extract_cache_payload(
            input_path,
            cache_version,
            use_mineru,
            mineru_lang,
            full_text,
            meta,
            file_texts,
            timestamp_func=timestamp_func,
        ),
    )
    resume_event_func(
        resume_dir,
        "stage1_extract",
        "saved",
        f"chars={len(full_text)}; use_mineru={use_mineru}",
        cache=str(extract_cache_path),
    )


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


def text_llm_stage_plan(audit_text, max_chars, resume_dir, llm_api_url, llm_model, chunker, fingerprint_func):
    """Build text-LLM chunking and cache-dir state for a run."""
    chunk_size = min(int(max_chars), 4096)
    overlap = min(512, chunk_size // 8)
    chunks = chunker(audit_text, chunk_size=chunk_size, overlap=overlap)
    total_chunks = len(chunks)
    cache_key = fingerprint_func(audit_text, f"{llm_api_url}|{llm_model}|{chunk_size}|{overlap}|refs_excluded")
    cache_dir = Path(resume_dir) / f"llm_{cache_key}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunks": chunks,
        "total_chunks": total_chunks,
        "cache_key": cache_key,
        "cache_dir": cache_dir,
    }


def apply_llm_chunk_coverage_meta(meta, chunk_reports, total_chunks, chunk_size, overlap):
    """Update run meta with text-LLM chunk coverage and return successful reports."""
    successful_count = sum(1 for report in chunk_reports if report is not None and not report.get("parse_error"))
    failed_final = []
    for idx in range(total_chunks):
        report = chunk_reports[idx] if idx < len(chunk_reports) else None
        if report is None or report.get("parse_error"):
            failed_final.append(idx + 1)
    meta["llm_success_chunks"] = successful_count
    meta["llm_failed_chunks"] = failed_final
    meta["llm_coverage"] = f"{successful_count}/{total_chunks}"
    meta["llm_partial_report"] = bool(failed_final)
    meta["chunk_count"] = total_chunks
    meta["chunk_size"] = chunk_size
    meta["overlap"] = overlap
    successful_reports = [report for report in chunk_reports if report is not None and not report.get("parse_error")]
    return successful_reports, failed_final


def llm_success_cache_payload(report, raw_content, timestamp_func=None, chunk_index=None, total_chunks=None, retry=None):
    """Build a successful text-LLM cache payload."""
    timestamp = timestamp_func or (lambda: time.strftime("%F %T"))
    payload = {
        "report": report,
        "raw_content": raw_content,
        "saved_at": timestamp(),
    }
    if chunk_index is not None:
        payload["chunk_index"] = chunk_index
    if total_chunks is not None:
        payload["total_chunks"] = total_chunks
    if retry is not None:
        payload["status"] = "ok"
        payload["retry"] = bool(retry)
    return payload


def llm_failure_cache_payload(error, chunk_index, total_chunks, status, first_error=None, timestamp_func=None):
    """Build a failed text-LLM cache payload."""
    timestamp = timestamp_func or (lambda: time.strftime("%F %T"))
    payload = {
        "report": {"parse_error": True, "raw_output": str(error)},
        "raw_content": str(error),
        "saved_at": timestamp(),
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "status": status,
    }
    if first_error is not None:
        payload["first_error"] = first_error
    return payload


def llm_chunk_cache_read_state(
    llm_cache_dir,
    chunk_idx,
    total_chunks,
    allow_llm_cache_read,
    llm_cache_only,
    json_load,
    resume_event_func,
    resume_dir,
):
    """Return cache status for one text-LLM chunk and record resume events."""
    chunk_cache = Path(llm_cache_dir) / f"chunk_{chunk_idx:04d}.json"
    cached = json_load(chunk_cache) if allow_llm_cache_read else None
    if cached and cached.get("status") == "ok" and cached.get("report") and not cached.get("report", {}).get("parse_error"):
        resume_event_func(
            resume_dir,
            "stage3_llm_chunk",
            "cache_hit",
            f"chunk={chunk_idx+1}/{total_chunks}",
            cache=str(chunk_cache),
        )
        return {
            "status": "cache_hit",
            "cache_path": chunk_cache,
            "report": cached.get("report"),
        }
    if llm_cache_only:
        resume_event_func(
            resume_dir,
            "stage3_llm_chunk",
            "cache_only_miss",
            f"chunk={chunk_idx+1}/{total_chunks}",
            cache=str(chunk_cache),
        )
        return {
            "status": "cache_only_miss",
            "cache_path": chunk_cache,
            "first_error": "cache_only_no_success_cache",
        }
    return {
        "status": "call_required",
        "cache_path": chunk_cache,
        "report": None,
    }


def apply_llm_partial_report_warning(report, meta):
    """Apply the standard partial text-LLM warning to a merged report."""
    if not isinstance(report, dict) or not meta.get("llm_partial_report"):
        return None
    warning = (
        f"注意：本报告仅覆盖 {meta.get('llm_coverage')} 个LLM分块；"
        f"失败块: {meta.get('llm_failed_chunks')}。结论不完整，建议换稳定API后断点续跑。"
    )
    report["_partial_warning"] = warning
    report["summary"] = warning + " " + str(report.get("summary", ""))
    return warning


def save_llm_failure_cache_result(
    chunk_cache,
    error,
    chunk_idx,
    total_chunks,
    status,
    json_save,
    resume_event_func,
    resume_dir,
    first_error=None,
):
    """Persist a failed text-LLM chunk cache and record its resume event."""
    json_save(
        chunk_cache,
        llm_failure_cache_payload(
            error,
            chunk_idx,
            total_chunks,
            status,
            first_error=first_error,
        ),
    )
    resume_event_func(
        resume_dir,
        "stage3_llm_chunk",
        status,
        f"chunk={chunk_idx+1}/{total_chunks}; error={error}",
        cache=str(chunk_cache),
    )


def llm_retry_failure_summary(still_failed, strict_failed_chunks):
    """Build summary fields for text-LLM chunks that still failed after retry."""
    failed_nums = [idx + 1 for idx, _ in still_failed]
    detail = "; ".join([f"第{idx+1}块: {err}" for idx, err in still_failed])
    return {
        "failed_chunks": failed_nums,
        "detail": detail,
        "event_detail": f"still_failed={failed_nums}; strict={strict_failed_chunks}",
        "message": "LLM分块重试后仍失败，停止生成完整审查报告: " + detail,
    }


def llm_no_success_failure_summary(failed_chunks):
    """Build summary fields when no text-LLM chunks produced usable reports."""
    message = f"所有LLM分块均失败，无法生成语义审查报告。失败块: {failed_chunks}。"
    return {
        "message": message,
        "details": {"failed_chunks": failed_chunks},
    }


def llm_merge_done_detail(report, meta):
    """Build the resume-event detail for successful text-LLM merge completion."""
    checks_count = len(report.get("checks", [])) if isinstance(report, dict) else "N/A"
    return f"checks={checks_count}; coverage={meta.get('llm_coverage')}"


def online_cache_state(resume_dir, filename, no_resume, json_load):
    """Build and load a resume-scoped online-check cache."""
    path = Path(resume_dir) / filename
    cache = {} if no_resume else (json_load(path, {}) or {})
    return {
        "no_resume": bool(no_resume),
        "path": path,
        "cache": cache,
    }


def save_online_cache_result(cache_state, audit_result, step, checked_key, json_save, resume_event_func, resume_dir):
    """Persist an online-check cache and record its resume event."""
    if not cache_state or cache_state.get("no_resume"):
        return
    cache = cache_state["cache"]
    path = cache_state["path"]
    json_save(path, cache)
    resume_event_func(
        resume_dir,
        step,
        "saved",
        f"checked={audit_result.get(checked_key, 0)}; cache_entries={len(cache)}",
        cache=str(path),
    )


def image_audit_cache_state(output_dir, resume_dir, no_resume, json_load, load_merged_json_dicts):
    """Build image-audit cache paths and load resume-visible cache state."""
    output_dir = Path(output_dir)
    resume_dir = Path(resume_dir)
    semantic_resume_path = resume_dir / "image_semantic_cache.json"
    semantic_local_path = output_dir / "image_semantic_cache.json"
    detector_path = resume_dir / "image_detector_cache.json"
    if no_resume:
        semantic_cache = {}
        detector_cache = {}
    else:
        semantic_cache = load_merged_json_dicts(semantic_local_path, semantic_resume_path)
        detector_cache = json_load(detector_path, {}) or {}
    return {
        "no_resume": bool(no_resume),
        "semantic_resume_path": semantic_resume_path,
        "semantic_local_path": semantic_local_path,
        "detector_path": detector_path,
        "semantic_cache": semantic_cache,
        "detector_cache": detector_cache,
    }


def image_semantic_cache_save_callback(cache_state, json_save):
    """Return a callback that saves image semantic cache to resume and visible files."""
    if not cache_state or cache_state.get("no_resume"):
        return None

    def save():
        json_save(cache_state["semantic_resume_path"], cache_state["semantic_cache"])
        json_save(cache_state["semantic_local_path"], cache_state["semantic_cache"])

    return save


def image_detector_cache_save_callback(cache_state, json_save):
    """Return a callback that saves the image detector resume cache."""
    if not cache_state or cache_state.get("no_resume"):
        return None

    def save():
        json_save(cache_state["detector_path"], cache_state["detector_cache"])

    return save


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
