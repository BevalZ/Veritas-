"""imagedetector.com provider flow."""

import json
import urllib.parse

from .external_timeout import _run_with_alarm_timeout
from .image_payloads import _prepare_detector_upload_file
from .image_results import _detector_timeout_result, _normalize_detector_result

DEFAULT_IMAGE_DETECT_URL = "https://imagedetector.com/"
DEFAULT_IMAGE_DETECT_UPLOAD_BASE = "https://ai-image-detector-prod.nyc3.digitaloceanspaces.com"

__all__ = [
    "DEFAULT_IMAGE_DETECT_URL",
    "DEFAULT_IMAGE_DETECT_UPLOAD_BASE",
    "call_imagedetector_from_namespace",
    "_call_imagedetector_unbounded_from_namespace",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def call_imagedetector_from_namespace(namespace, image_path: str, timeout=60):
    """Upload an image to imagedetector.com using the site's public web flow."""
    def _call():
        return _call_imagedetector_unbounded_from_namespace(namespace, image_path, timeout=timeout)

    timeout_result = _namespace_value(namespace, "_detector_timeout_result", _detector_timeout_result)
    timeout_runner = _namespace_value(namespace, "_run_with_alarm_timeout", _run_with_alarm_timeout)
    return timeout_runner(_call, timeout, lambda: timeout_result(timeout))


def _call_imagedetector_unbounded_from_namespace(namespace, image_path: str, timeout=60):
    prepare_file = _namespace_value(namespace, "_prepare_detector_upload_file", _prepare_detector_upload_file)
    http_request = _namespace_value(namespace, "_http_request")
    normalize_result = _namespace_value(namespace, "_normalize_detector_result", _normalize_detector_result)
    detect_url = _namespace_value(namespace, "IMAGE_DETECT_URL", DEFAULT_IMAGE_DETECT_URL)
    upload_base = _namespace_value(namespace, "IMAGE_DETECT_UPLOAD_BASE", DEFAULT_IMAGE_DETECT_UPLOAD_BASE)
    if not callable(http_request):
        raise RuntimeError("imagedetector namespace is incomplete")
    try:
        file_name, mime, content = prepare_file(image_path)
        if len(content) < 1024:
            return {
                "status": "skipped",
                "provider": "imagedetector.com",
                "reason": "too_small",
                "summary": "图片小于imagedetector网页最小上传要求，跳过自动检测。",
            }
        if len(content) > 10 * 1024 * 1024:
            return {
                "status": "skipped",
                "provider": "imagedetector.com",
                "reason": "too_large",
                "summary": "图片超过imagedetector网页10MB限制，跳过自动检测。",
            }
        query = urllib.parse.urlencode({"fileName": file_name, "fileType": mime})
        headers = {
            "Accept": "application/json",
            "Referer": detect_url,
            "User-Agent": "PaperAudit/1.0",
        }
        data, _ = http_request(
            f"{detect_url.rstrip('/')}/api/get-presigned-url?{query}",
            "GET",
            headers=headers,
            timeout=timeout,
        )
        upload_info = json.loads(data.decode("utf-8", errors="replace"))
        presigned_url = upload_info.get("presignedUrl")
        file_path = upload_info.get("filePath")
        expected_type = upload_info.get("expectedContentType") or mime
        if not presigned_url or not file_path:
            return {
                "status": "error",
                "provider": "imagedetector.com",
                "reason": "missing_upload_url",
                "summary": "imagedetector未返回可用上传地址。",
            }
        http_request(
            presigned_url,
            "PUT",
            headers={"Content-Type": expected_type, "x-amz-acl": "private"},
            data=content,
            timeout=timeout,
        )
        image_url = f"{upload_base.rstrip('/')}/{file_path.lstrip('/')}"
        detect_payload = json.dumps({"imageUrl": image_url}).encode("utf-8")
        data, _ = http_request(
            f"{detect_url.rstrip('/')}/api/detect",
            "POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Referer": detect_url,
                "User-Agent": "PaperAudit/1.0",
            },
            data=detect_payload,
            timeout=timeout,
        )
        return normalize_result(json.loads(data.decode("utf-8", errors="replace")))
    except Exception as e:
        return {
            "status": "error",
            "provider": "imagedetector.com",
            "reason": type(e).__name__,
            "summary": f"imagedetector自动检测失败：{type(e).__name__}",
        }
