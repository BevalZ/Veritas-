"""Formal audit artifact path and outcome helpers."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .file_utils import _safe_name


def failed_audit_artifact_paths(input_path: Path, output_dir: Path = None, output_stem: str = None) -> Tuple[Path, Path, Path]:
    """Return Markdown, HTML, and JSON artifact paths for failed audit diagnostics."""
    input_path = Path(input_path)
    if output_dir:
        output_dir = Path(output_dir)
        stem = _safe_name(output_stem or ("audit_report" if input_path.is_dir() else input_path.stem))
        return output_dir / f"{stem}.failed.md", output_dir / f"{stem}.failed.html", output_dir / f"{stem}.failed.json"
    if input_path.is_dir():
        return input_path / "audit_report.failed.md", input_path / "audit_report.failed.html", input_path / "audit_report.failed.json"
    return input_path.with_suffix(".failed.md"), input_path.with_suffix(".failed.html"), input_path.with_suffix(".failed.json")


def _artifact_base_from_output(output_path: Path) -> Path:
    base = Path(output_path)
    if base.suffix in {".md", ".html", ".json"}:
        base = base.with_suffix("")
    for suffix in (".audit", ".limited", ".failed"):
        if base.name.endswith(suffix):
            base = base.with_name(base.name[: -len(suffix)])
            break
    return base


def explicit_output_path_from_args(args) -> Path:
    """Return an explicit artifact stem/path using CLI cwd-relative semantics."""
    output = getattr(args, "output", None)
    if not output:
        return None
    base = _artifact_base_from_output(Path(output))
    if not base.is_absolute():
        base = Path.cwd() / base
    return base


def audit_artifact_paths(input_path: Path, artifact_type: str = "complete", output_path: Path = None) -> Tuple[Path, Path, Path]:
    """Return Markdown, HTML, and JSON paths for complete or limited audit artifacts."""
    suffix = "limited" if artifact_type == "limited" else "audit"
    input_path = Path(input_path)
    if output_path:
        base = _artifact_base_from_output(Path(output_path))
        return (
            base.with_suffix(f".{suffix}.md"),
            base.with_suffix(f".{suffix}.html"),
            base.with_suffix(f".{suffix}.json"),
        )
    if input_path.is_dir():
        return (
            input_path / f"audit_report.{suffix}.md",
            input_path / f"audit_report.{suffix}.html",
            input_path / f"audit_report.{suffix}.json",
        )
    return (
        input_path.with_suffix(f".{suffix}.md"),
        input_path.with_suffix(f".{suffix}.html"),
        input_path.with_suffix(f".{suffix}.json"),
    )


def audit_limited_reasons(args, meta: Dict[str, Any], has_pdf_input=False) -> List[str]:
    """Return user-visible reasons why a successful run is limited instead of complete."""
    meta = meta or {}
    reasons = []
    image_count = ((meta.get("image_audit") or {}).get("image_count") or 0)
    reference_count = meta.get("reference_count") or ((meta.get("reference_audit") or {}).get("reference_count") or 0)
    reference_checked = ((meta.get("reference_audit") or {}).get("online_checked") or 0)
    resource_count = meta.get("resource_count") or ((meta.get("resource_audit") or {}).get("resource_count") or 0)
    image_audit = meta.get("image_audit") or {}
    if has_pdf_input and getattr(args, "no_mineru", False):
        reasons.append("用户禁用MinerU正式PDF解析。")
    if reference_count and getattr(args, "no_reference_online", False):
        reasons.append("用户关闭参考文献在线核验。")
    elif reference_count and getattr(args, "reference_online_limit", None) is not None:
        reasons.append(f"用户设置参考文献在线核验上限: {getattr(args, 'reference_online_limit')}。")
    elif reference_count and reference_checked < reference_count:
        reasons.append(f"参考文献在线核验覆盖不足: {reference_checked}/{reference_count}。")
    if resource_count and getattr(args, "no_resource_online", False):
        reasons.append("用户关闭代码仓库与在线资源可用性校检。")
    if image_count and getattr(args, "image_audit_limit", None) is not None:
        reasons.append(f"用户设置图像审查上限: {getattr(args, 'image_audit_limit')}。")
    if image_count and getattr(args, "no_image_semantic", False):
        reasons.append("用户关闭图像语义分析。")
    elif image_count and getattr(args, "image_semantic_limit", None) is not None:
        reasons.append(f"用户设置图像语义分析上限: {getattr(args, 'image_semantic_limit')}。")
    elif image_count and (image_audit.get("semantic_checked") or 0) < image_count:
        reasons.append(f"图像语义分析覆盖不足: {image_audit.get('semantic_checked') or 0}/{image_count}。")
    if image_count and getattr(args, "no_image_detector", False):
        reasons.append("用户关闭imagedetector自动检测。")
    elif image_count and getattr(args, "image_detector_limit", None) is not None:
        reasons.append(f"用户设置imagedetector检测上限: {getattr(args, 'image_detector_limit')}。")
    elif image_count and (image_audit.get("detector_checked") or 0) < image_count:
        reasons.append(f"imagedetector自动检测覆盖不足: {image_audit.get('detector_checked') or 0}/{image_count}。")
    if getattr(args, "llm_cache_only", False):
        reasons.append("用户启用LLM cache-only模式，未进行实时文本语义审查。")
    if meta.get("llm_partial_report"):
        reasons.append(f"LLM分块覆盖不足: {meta.get('llm_coverage', '未知')}；失败块: {meta.get('llm_failed_chunks') or '无'}。")
    return reasons


def coverage_blocking_failure(meta: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """Return capability failure if relevant content exists but a critical service failed service-wide."""
    meta = meta or {}
    reference_audit = meta.get("reference_audit") or {}
    references = reference_audit.get("references") or []
    if reference_audit.get("reference_count", 0) and reference_audit.get("online_enabled") and references:
        checked = [ref.get("online") or {} for ref in references if (ref.get("online") or {}).get("online_status")]
        if checked and all(item.get("online_status") == "error" for item in checked):
            return "reference_lookup", "参考文献在线核验服务全部失败。", {"reference_count": reference_audit.get("reference_count"), "online_checked": reference_audit.get("online_checked")}

    resource_audit = meta.get("resource_audit") or {}
    resources = resource_audit.get("resources") or []
    if resource_audit.get("resource_count", 0) and resource_audit.get("online_enabled") and resources:
        checked = [item.get("availability") or {} for item in resources if (item.get("availability") or {}).get("status")]
        provider_errors = [item for item in checked if item.get("status") == "error"]
        if checked and provider_errors and len(provider_errors) == len(checked):
            return "resource_availability", "代码仓库与在线资源可用性校检服务全部失败。", {"resource_count": resource_audit.get("resource_count"), "online_checked": resource_audit.get("online_checked")}

    image_audit = meta.get("image_audit") or {}
    images = image_audit.get("images") or []
    if image_audit.get("image_count") and images:
        semantic_results = [img.get("semantic") or {} for img in images if img.get("semantic")]
        if image_audit.get("semantic_enabled") and semantic_results and all(result.get("status") == "error" for result in semantic_results):
            return "image_semantic", "图像语义分析服务全部失败。", {"image_count": image_audit.get("image_count"), "semantic_checked": image_audit.get("semantic_checked")}
        detector_results = [img.get("detector") or {} for img in images if img.get("detector")]
        if image_audit.get("detector_enabled") and detector_results and all(result.get("status") == "error" for result in detector_results):
            return "image_detector", "imagedetector自动检测服务全部失败。", {"image_count": image_audit.get("image_count"), "detector_checked": image_audit.get("detector_checked")}
    return "", "", {}


def apply_audit_artifact_type(meta: Dict[str, Any], limited_reasons: List[str]) -> Dict[str, Any]:
    """Annotate successful audit metadata with complete/limited artifact type."""
    meta = meta if isinstance(meta, dict) else {}
    reasons = list(limited_reasons or [])
    if reasons:
        meta["artifact_type"] = "limited"
        meta["artifact_suffix"] = "limited"
        meta["limited_reasons"] = reasons
    else:
        meta["artifact_type"] = "complete"
        meta["artifact_suffix"] = "audit"
        meta.pop("limited_reasons", None)
    return meta


__all__ = [
    "failed_audit_artifact_paths",
    "_artifact_base_from_output",
    "explicit_output_path_from_args",
    "audit_artifact_paths",
    "audit_limited_reasons",
    "coverage_blocking_failure",
    "apply_audit_artifact_type",
]
