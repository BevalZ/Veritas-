"""Stable data models for audit evidence and run outcomes."""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict

from .legacy import (
    AuditFailure,
    AuditReportModel,
    CoverageModel,
    EvidenceFinding,
    ImageAuditModel,
    ReferenceAuditModel,
    RunMetadataModel,
    RunRequest,
    RunResult,
)


def model_to_dict(value: Any) -> Dict[str, Any]:
    """Convert a stable audit model or dict into renderer-compatible data."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Unsupported audit model type: {type(value).__name__}")


__all__ = [
    "AuditFailure",
    "RunRequest",
    "RunResult",
    "EvidenceFinding",
    "AuditReportModel",
    "ReferenceAuditModel",
    "ImageAuditModel",
    "RunMetadataModel",
    "CoverageModel",
    "model_to_dict",
]
