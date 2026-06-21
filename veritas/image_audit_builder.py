"""Image audit orchestration across local checks and provider calls."""

from .image_cache import _image_file_fingerprint_from_namespace, _image_semantic_cache_key_from_namespace
from .image_collection import collect_image_files_from_namespace
from .image_detector_provider import DEFAULT_IMAGE_DETECT_URL, call_imagedetector_from_namespace
from .image_local_analysis import analyze_image_reasonability_from_namespace
from .image_semantic_provider import call_glm_image_semantics_from_namespace
from .image_selection import (
    _flush_image_cache,
    _image_audit_sort_key,
    _image_detector_priority_key,
    _image_semantic_priority_key,
)
from .limit_utils import _effective_limit

__all__ = ["build_image_audit_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _run_semantic_image_checks(
    analyses,
    semantic_limit,
    semantic_timeout,
    semantic_cache,
    semantic_cache_save,
    semantic_priority_key,
    effective_limit,
    semantic_cache_key,
    flush_image_cache,
    call_semantic,
):
    semantic_checked = 0
    semantic_candidates = sorted(analyses, key=semantic_priority_key)
    semantic_queue = semantic_candidates[:effective_limit(semantic_limit, len(semantic_candidates))]
    for idx, item in enumerate(semantic_queue, 1):
        cache_key = semantic_cache_key(item.get("path", ""))
        semantic_result = semantic_cache.get(cache_key)
        if isinstance(semantic_result, dict) and semantic_result.get("status") == "error":
            semantic_cache.pop(cache_key, None)
            flush_image_cache(semantic_cache_save, "图像语义")
            semantic_result = None
        if not semantic_result:
            print(f"  🖼️ 图像语义分析 [{idx}/{len(semantic_queue)}] {item.get('file', '')}")
            semantic_result = call_semantic(item.get("path", ""), timeout=semantic_timeout)
            if semantic_result.get("status") != "error":
                semantic_cache[cache_key] = semantic_result
                flush_image_cache(semantic_cache_save, "图像语义")
        item["semantic"] = semantic_result
        semantic_checked += 1
    return semantic_checked


def build_image_audit_from_namespace(
    namespace,
    input_path: str,
    output_dir=None,
    limit=None,
    semantic=True,
    semantic_limit=None,
    semantic_timeout=45,
    semantic_cache=None,
    semantic_cache_save=None,
    detector=True,
    detector_limit=None,
    detector_timeout=60,
    detector_cache=None,
    detector_cache_save=None,
):
    collect_images = _namespace_value(namespace, "collect_image_files")
    analyze_image = _namespace_value(namespace, "analyze_image_reasonability")
    image_sort_key = _namespace_value(namespace, "_image_audit_sort_key", _image_audit_sort_key)
    semantic_priority_key = _namespace_value(namespace, "_image_semantic_priority_key", _image_semantic_priority_key)
    detector_priority_key = _namespace_value(namespace, "_image_detector_priority_key", _image_detector_priority_key)
    effective_limit = _namespace_value(namespace, "_effective_limit", _effective_limit)
    semantic_cache_key = _namespace_value(namespace, "_image_semantic_cache_key")
    image_fingerprint = _namespace_value(namespace, "_image_file_fingerprint")
    flush_image_cache = _namespace_value(namespace, "_flush_image_cache", _flush_image_cache)
    call_semantic = _namespace_value(namespace, "call_glm_image_semantics")
    call_detector = _namespace_value(namespace, "call_imagedetector")

    if not callable(collect_images):
        collect_images = lambda path, **kwargs: collect_image_files_from_namespace(namespace, path, **kwargs)
    if not callable(analyze_image):
        analyze_image = lambda path: analyze_image_reasonability_from_namespace(namespace, path)
    if not callable(semantic_cache_key):
        semantic_cache_key = lambda path: _image_semantic_cache_key_from_namespace(namespace, path)
    if not callable(image_fingerprint):
        image_fingerprint = lambda path: _image_file_fingerprint_from_namespace(namespace, path)
    if not callable(call_semantic):
        call_semantic = lambda path, timeout=45: call_glm_image_semantics_from_namespace(namespace, path, timeout=timeout)
    if not callable(call_detector):
        call_detector = lambda path, timeout=60: call_imagedetector_from_namespace(namespace, path, timeout=timeout)

    images = collect_images(input_path, include_pdf=False, include_mineru=True, output_dir=output_dir)
    analyses = sorted((analyze_image(path) for path in images), key=image_sort_key)
    analyses = analyses[:effective_limit(limit, len(analyses))]
    semantic_cache = semantic_cache if isinstance(semantic_cache, dict) else {}
    detector_cache = detector_cache if isinstance(detector_cache, dict) else {}
    semantic_checked = 0
    if semantic:
        semantic_checked = _run_semantic_image_checks(
            analyses,
            semantic_limit,
            semantic_timeout,
            semantic_cache,
            semantic_cache_save,
            semantic_priority_key,
            effective_limit,
            semantic_cache_key,
            flush_image_cache,
            call_semantic,
        )
    detector_checked = 0
    if detector:
        detector_candidates = sorted(analyses, key=detector_priority_key)
        detector_queue = detector_candidates[:effective_limit(detector_limit, len(detector_candidates))]
        for idx, item in enumerate(detector_queue, 1):
            cache_key = image_fingerprint(item.get("path", "")) + ":imagedetector_v1"
            detector_result = detector_cache.get(cache_key)
            if isinstance(detector_result, dict) and detector_result.get("status") == "error":
                detector_cache.pop(cache_key, None)
                flush_image_cache(detector_cache_save, "imagedetector")
                detector_result = None
            if not detector_result:
                print(f"  🖼️ imagedetector自动检测 [{idx}/{len(detector_queue)}] {item.get('file', '')}")
                detector_result = call_detector(item.get("path", ""), timeout=detector_timeout)
                if detector_result.get("status") != "error":
                    detector_cache[cache_key] = detector_result
                    flush_image_cache(detector_cache_save, "imagedetector")
            item["detector"] = detector_result
            detector_checked += 1
    return {
        "enabled": bool(analyses),
        "site": _namespace_value(namespace, "IMAGE_DETECT_URL", DEFAULT_IMAGE_DETECT_URL),
        "semantic_enabled": bool(semantic),
        "semantic_model": _namespace_value(namespace, "GLM_VISION_MODEL", ""),
        "semantic_checked": semantic_checked,
        "detector_enabled": bool(detector),
        "detector_checked": detector_checked,
        "image_count": len(images),
        "checked_count": len(analyses),
        "images": analyses,
        "note": "本地做尺寸、空白、噪声/对比度筛查；图像语义分析模型做图片语义理解；imagedetector.com子工具自动上传并记录AI概率。",
    }
