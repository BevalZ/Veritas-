"""Stable data models for audit evidence and run outcomes."""

import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List

from .run_types import RunRequest, RunResult


@dataclass
class AuditFailure:
    """Structured diagnostic record for a run that cannot produce a complete audit."""
    capability: str
    error_class: str
    message: str
    fix_hints: List[str] = field(default_factory=list)
    completed_stages: List[str] = field(default_factory=list)
    retry_command: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class EvidenceFinding:
    category: str
    item: str
    verdict: str
    source_text: str
    evidence: str
    reason: str
    recommendation: str
    confidence: float
    detail: str = ""


@dataclass
class AuditReportModel:
    summary: str
    risk_level: str
    detection_score: int
    checks: List[EvidenceFinding]
    conclusion: str


@dataclass
class ReferenceAuditModel:
    status: str
    reference_count: int
    online_checked: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ImageAuditModel:
    image_count: int
    semantic_checked: int = 0
    detector_checked: int = 0
    items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RunMetadataModel:
    artifact_type: str
    extraction_method: str
    total_chars: int = 0
    limited_reasons: List[str] = field(default_factory=list)


@dataclass
class CoverageModel:
    capability: str
    successful: int
    total: int
    failed: List[Any] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.successful == self.total and not self.failed


def _as_str(value: Any) -> str:
    return "" if value is None else str(value)


def evidence_finding_from_dict(value: Any) -> EvidenceFinding:
    """Normalize renderer-compatible finding data into a stable model."""
    if isinstance(value, EvidenceFinding):
        return value
    if not isinstance(value, dict):
        raise TypeError(f"Unsupported evidence finding type: {type(value).__name__}")
    try:
        confidence = float(value.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return EvidenceFinding(
        category=_as_str(value.get("category")),
        item=_as_str(value.get("item")),
        verdict=_as_str(value.get("verdict")),
        source_text=_as_str(value.get("source_text") or value.get("source")),
        evidence=_as_str(value.get("evidence")),
        reason=_as_str(value.get("reason")),
        recommendation=_as_str(value.get("recommendation")),
        confidence=confidence,
        detail=_as_str(value.get("detail")),
    )


def audit_report_from_dict(value: Any) -> AuditReportModel:
    """Normalize parsed report dictionaries into the stable audit report model."""
    if isinstance(value, AuditReportModel):
        return value
    if not isinstance(value, dict):
        raise TypeError(f"Unsupported audit report type: {type(value).__name__}")
    try:
        detection_score = int(value.get("detection_score", 0) or 0)
    except (TypeError, ValueError):
        detection_score = 0
    return AuditReportModel(
        summary=_as_str(value.get("summary")),
        risk_level=_as_str(value.get("risk_level")),
        detection_score=detection_score,
        checks=[evidence_finding_from_dict(check) for check in (value.get("checks") or [])],
        conclusion=_as_str(value.get("conclusion")),
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
    "evidence_finding_from_dict",
    "audit_report_from_dict",
    "model_to_dict",
]
