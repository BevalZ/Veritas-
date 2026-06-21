"""Image provider response normalization helpers."""

import json
import re

from .text_utils import _brief_text

__all__ = [
    "_normalize_glm_image_result",
    "_glm_error_result",
    "_normalize_detector_result",
    "_glm_timeout_result",
    "_detector_timeout_result",
    "_extract_json_object",
]


def _normalize_glm_image_result(parsed, model):
    if not isinstance(parsed, dict):
        parsed = {}
    risks = parsed.get("risks")
    if isinstance(risks, str):
        risks = [risks] if risks.strip() else []
    elif not isinstance(risks, list):
        risks = []
    manual_checks = parsed.get("manual_checks")
    if isinstance(manual_checks, str):
        manual_checks = [manual_checks] if manual_checks.strip() else []
    elif not isinstance(manual_checks, list):
        manual_checks = []
    try:
        confidence = float(parsed.get("confidence") or 0)
    except Exception:
        confidence = 0
    confidence = max(0.0, min(1.0, confidence))
    reasonability = str(parsed.get("reasonability") or "需人工核对").strip()
    if reasonability not in {"合理", "需人工核对", "可疑"}:
        reasonability = "需人工核对"
    summary = str(parsed.get("summary") or "图像语义分析未返回明确摘要。").strip()
    visible_text = str(parsed.get("visible_text") or "").strip()
    risks = [str(r).strip() for r in risks if str(r).strip()]
    manual_checks = [str(c).strip() for c in manual_checks if str(c).strip()]
    joined = " ".join([summary, visible_text, " ".join(risks), " ".join(manual_checks)]).lower()
    image_missing_markers = (
        "no_image",
        "未收到图片",
        "没有收到图片",
        "未提供图片",
        "未检测到上传的图片",
        "无法看到图片",
        "看不到图片",
        "缺少图片",
        "缺少图像",
        "无图片可分析",
        "missing image",
        "no image",
    )
    image_not_received = any(marker in joined for marker in image_missing_markers)
    status = parsed.get("status") or "ok"
    if image_not_received:
        status = "error"
        if "image_input_not_supported" not in risks:
            risks.append("image_input_not_supported")
        if not manual_checks:
            manual_checks = ["更换支持 image_url 多模态输入的图像语义分析模型或检查 OpenAI-compatible 网关配置。"]
    return {
        "status": status,
        "model": parsed.get("model") or model,
        "summary": summary,
        "image_type": str(parsed.get("image_type") or "").strip(),
        "scientific_context": str(parsed.get("scientific_context") or "").strip(),
        "visible_text": visible_text,
        "reasonability": reasonability,
        "risks": risks,
        "manual_checks": manual_checks,
        "confidence": confidence,
        **({"error_reason": "image_input_not_received"} if image_not_received else {}),
    }


def _glm_error_result(exc, model):
    reason = type(exc).__name__
    message = str(exc)
    status_code = None
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        try:
            payload = response.json()
            message = (((payload.get("error") or {}).get("message")) or payload.get("message") or message)
            code = (((payload.get("error") or {}).get("code")) or payload.get("code"))
            if code:
                reason = f"{reason}:{code}"
        except Exception:
            text = getattr(response, "text", "") or ""
            if text:
                message = _brief_text(text, 220)
    if status_code == 429:
        summary = "图像语义分析被服务端限流或模型当前繁忙，建议稍后重试。"
        risk = "glm_rate_limited"
    else:
        summary = "图像语义分析暂未完成该图语义理解，建议稍后重试或人工核对图注与原图。"
        risk = "glm_temporary_unavailable"
    return {
        "status": "error",
        "model": model,
        "summary": summary,
        "reasonability": "需人工核对",
        "risks": [risk],
        "manual_checks": ["稍后重试图像语义分析；必要时人工核对图片内容、图注、正文结论是否一致。"],
        "confidence": 0,
        "error_reason": reason,
        "error_message": _brief_text(message, 220),
        "http_status": status_code,
    }


def _normalize_detector_result(data):
    data = data if isinstance(data, dict) else {}
    details = data.get("result_details") if isinstance(data.get("result_details"), dict) else {}
    score = data.get("result", details.get("result"))
    try:
        score = float(score)
    except Exception:
        score = None
    confidence = data.get("confidence", details.get("confidence"))
    label = data.get("final_result") or details.get("final_result") or data.get("prediction")
    if not label:
        if data.get("isAI") is True:
            label = "AI生成"
        elif data.get("isAI") is False:
            label = "真实/人工"
        elif score is not None:
            label = "AI生成" if score >= 50 else "真实/人工"
        else:
            label = "未知"
    source = data.get("source") or details.get("source") or details.get("ml_model") or ""
    return {
        "status": "ok",
        "provider": "imagedetector.com",
        "score": score,
        "is_ai": data.get("isAI"),
        "label": str(label),
        "confidence": confidence,
        "source": source,
        "watermark": details.get("watermark"),
        "heatmap_url": details.get("heatmap_url"),
        "preview_url": data.get("preview_url"),
        "image_id": data.get("image_id"),
        "raw": data,
    }


def _glm_timeout_result(model, timeout):
    return {
        "status": "error",
        "model": model,
        "summary": f"图像语义分析超过{timeout}s未返回，建议检查第三方服务或网络后重试。",
        "reasonability": "需人工核对",
        "risks": ["glm_timeout"],
        "manual_checks": ["检查图像语义分析服务配置、网络情况和服务商状态后重试。"],
        "confidence": 0,
        "error_reason": "timeout",
        "error_message": f"timeout>{timeout}s",
        "http_status": None,
    }


def _detector_timeout_result(timeout):
    return {
        "status": "error",
        "provider": "imagedetector.com",
        "reason": "timeout",
        "summary": f"imagedetector自动检测超过{timeout}s未返回，建议检查第三方服务或网络后重试。",
    }


def _extract_json_object(text):
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None
