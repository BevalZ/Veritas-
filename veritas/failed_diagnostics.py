"""Stable failed-audit diagnostic payload helpers."""

from pathlib import Path
from typing import Any, Dict, List

from .adapter_types import AdapterResult
from .models import AuditFailure
from .preflight_types import PreflightResult
from .runtime_metadata import ensure_runtime_meta


def failed_audit_payload(failure: AuditFailure, input_path: Path, meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """Return the stable JSON payload for a failed audit diagnostic artifact."""
    meta = ensure_runtime_meta(meta)
    payload = {
        "report_type": "failed",
        "complete_report_generated": False,
        "input_path": str(input_path),
        "created_at": failure.created_at,
        "failure": {
            "capability": failure.capability,
            "error_class": failure.error_class,
            "message": failure.message,
            "fix_hints": list(failure.fix_hints),
            "completed_stages": list(failure.completed_stages),
            "retry_command": failure.retry_command,
            "details": dict(failure.details),
        },
        "meta": meta,
    }
    for key in ("reference_audit", "resource_audit", "image_audit"):
        if key in meta:
            payload[key] = meta[key]
    return payload


def preflight_failure_to_audit_failure(
    result: PreflightResult,
    retry_command: str,
    completed_stages: List[str],
) -> AuditFailure:
    hints = {
        "mineru": [
            "检查config.py或环境变量中的MINERU_TOKEN和MINERU_BASE。",
            "确认MinerU第三方服务可访问，网络代理和服务商状态正常。",
            "修复配置或网络后使用下方命令重试。",
        ],
        "text_llm": [
            "检查config.py或环境变量中的LLM_API_KEY、LLM_API_URL和LLM_MODEL。",
            "确认文本语义审查LLM服务可访问，账号额度、模型名和网关状态正常。",
            "修复配置或网络后使用下方命令重试。",
        ],
    }
    return AuditFailure(
        capability=result.capability,
        error_class=result.error_class or "preflight_failed",
        message=result.message or "关键能力预检失败。",
        fix_hints=hints.get(result.capability, ["检查关键服务配置、网络连通性和服务商返回状态后重试。"]),
        completed_stages=list(completed_stages),
        retry_command=retry_command,
        details=result.to_dict(),
        created_at=result.created_at,
    )


def adapter_failure_to_audit_failure(
    capability: str,
    result: AdapterResult,
    retry_command: str,
    completed_stages: List[str],
) -> AuditFailure:
    return AuditFailure(
        capability=capability,
        error_class=result.error_class or "adapter_failed",
        message=result.message or f"{capability} adapter failed",
        fix_hints=[
            "检查第三方服务配置、网络、账号额度和模型/接口参数。",
            "修复后使用下方命令重试。",
        ],
        completed_stages=list(completed_stages),
        retry_command=retry_command,
        details=result.to_dict(),
    )


__all__ = [
    "failed_audit_payload",
    "preflight_failure_to_audit_failure",
    "adapter_failure_to_audit_failure",
]
