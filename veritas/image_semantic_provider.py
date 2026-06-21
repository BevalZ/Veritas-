"""OpenAI-compatible image semantic provider flow."""

import json
from pathlib import Path

from .external_timeout import _run_with_alarm_timeout
from .image_payloads import _image_to_data_url
from .image_results import _extract_json_object, _glm_error_result, _glm_timeout_result, _normalize_glm_image_result
from .preflight import _chat_completions_endpoint
from .runtime_config import DEFAULT_IMAGE_SEMANTIC_API_URL, DEFAULT_IMAGE_SEMANTIC_MODEL
from .text_utils import _brief_text

DEFAULT_GLM_API_URL = DEFAULT_IMAGE_SEMANTIC_API_URL
DEFAULT_GLM_VISION_MODEL = DEFAULT_IMAGE_SEMANTIC_MODEL
DEFAULT_GLM_IMAGE_MAX_BYTES = 5 * 1024 * 1024

__all__ = [
    "DEFAULT_GLM_API_URL",
    "DEFAULT_GLM_VISION_MODEL",
    "DEFAULT_GLM_IMAGE_MAX_BYTES",
    "call_glm_image_semantics_from_namespace",
    "_call_glm_image_semantics_unbounded_from_namespace",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _glm_image_semantic_prompt():
    return (
        "你是科研论文图像审查助手。请只基于这张图片本身做语义理解与合理性审查。"
        "不要输出推理过程、解释、Markdown或代码块；只返回一个合法JSON对象。"
        "不要把低分辨率、OCR错误、压缩噪声、表格截断或排版问题直接当作造假证据。"
        "如果图片是表格/局部截图，请重点说明可读内容和截断风险。"
        "reasonability字段必须严格取值为：合理、需人工核对、可疑。"
        "请返回严格JSON："
        "{\"summary\":\"一句话描述图片内容\","
        "\"image_type\":\"图/表/显微图/热图/流程图/照片/其他\","
        "\"scientific_context\":\"可能对应的科研用途\","
        "\"visible_text\":\"能读出的关键文字，读不出写空字符串\","
        "\"reasonability\":\"合理/需人工核对/可疑\","
        "\"risks\":[\"可疑点短语\"],"
        "\"manual_checks\":[\"建议人工核对事项\"],"
        "\"confidence\":0到1}"
    )


def _glm_image_semantic_payload(model, image_data_url):
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _glm_image_semantic_prompt()},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 10000,
    }


def call_glm_image_semantics_from_namespace(namespace, image_path: str, timeout=45, api_key=None, model=None):
    """Use the configured image semantic model to flag visual reasonability risks."""
    selected_api_key = api_key or _namespace_value(namespace, "GLM_API_KEY", "")
    selected_model = model or _namespace_value(namespace, "GLM_VISION_MODEL", DEFAULT_GLM_VISION_MODEL)

    def _call():
        return _call_glm_image_semantics_unbounded_from_namespace(
            namespace,
            image_path,
            timeout=timeout,
            api_key=selected_api_key,
            model=selected_model,
        )

    timeout_result = _namespace_value(namespace, "_glm_timeout_result", _glm_timeout_result)
    timeout_runner = _namespace_value(namespace, "_run_with_alarm_timeout", _run_with_alarm_timeout)
    return timeout_runner(_call, timeout, lambda: timeout_result(selected_model, timeout))


def _call_glm_image_semantics_unbounded_from_namespace(namespace, image_path: str, timeout=45, api_key=None, model=None):
    """Unbounded implementation; call through call_glm_image_semantics in orchestration."""
    selected_api_key = api_key or _namespace_value(namespace, "GLM_API_KEY", "")
    selected_model = model or _namespace_value(namespace, "GLM_VISION_MODEL", DEFAULT_GLM_VISION_MODEL)
    image_max_bytes = _namespace_value(namespace, "GLM_IMAGE_MAX_BYTES", DEFAULT_GLM_IMAGE_MAX_BYTES)
    image_to_data_url = _namespace_value(namespace, "_image_to_data_url", _image_to_data_url)
    http_request = _namespace_value(namespace, "_http_request")
    endpoint_builder = _namespace_value(namespace, "_chat_completions_endpoint", _chat_completions_endpoint)
    extract_json_object = _namespace_value(namespace, "_extract_json_object", _extract_json_object)
    normalize_result = _namespace_value(namespace, "_normalize_glm_image_result", _normalize_glm_image_result)
    error_result = _namespace_value(namespace, "_glm_error_result", _glm_error_result)
    brief_text = _namespace_value(namespace, "_brief_text", _brief_text)
    api_url = _namespace_value(namespace, "GLM_API_URL", DEFAULT_GLM_API_URL)

    path = Path(image_path)
    if not selected_api_key:
        return {
            "status": "skipped",
            "model": selected_model,
            "summary": "图像语义分析API Key未配置，已跳过图像语义分析。",
            "risks": ["glm_key_missing"],
            "confidence": 0,
        }
    try:
        if path.exists() and path.stat().st_size > image_max_bytes:
            return {
                "status": "skipped",
                "model": selected_model,
                "summary": "图片超过图像语义分析的本地压缩前安全上限，已跳过。",
                "reasonability": "需人工核对",
                "risks": ["glm_image_too_large"],
                "manual_checks": ["人工核对该图原图、图注和正文结论是否一致。"],
                "confidence": 0,
            }
    except Exception:
        pass

    payload = _glm_image_semantic_payload(selected_model, image_to_data_url(image_path))
    headers = {
        "Authorization": f"Bearer {selected_api_key}",
        "Content-Type": "application/json",
    }
    try:
        data, _ = http_request(
            endpoint_builder(api_url),
            "POST",
            headers=headers,
            data=json.dumps(payload).encode("utf-8"),
            timeout=timeout,
        )
        result = json.loads(data.decode("utf-8", errors="replace"))
        message = ((result.get("choices") or [{}])[0].get("message") or {})
        content = (
            message.get("content")
            or message.get("reasoning_content")
            or message.get("reasoning")
            or ""
        ).strip()
        parsed = extract_json_object(content)
        if not isinstance(parsed, dict):
            parsed = {"summary": brief_text(content, 260), "risks": ["glm_json_parse_failed"], "confidence": 0}
        return normalize_result(parsed, selected_model)
    except Exception as e:
        return error_result(e, selected_model)
