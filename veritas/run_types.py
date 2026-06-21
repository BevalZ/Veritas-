"""Stable request types for audit run orchestration."""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class RunRequest:
    """Structured audit request used by CLI, Web Runner, and GUI entry points."""
    input_path: Path
    output: str = ""
    json_output: bool = False
    no_open: bool = False
    mineru: bool = False
    no_mineru: bool = False
    mineru_model: str = "vlm"
    mineru_lang: str = "ch"
    max_chars: int = 4096
    no_reference_online: bool = False
    reference_online_limit: int = None
    reference_timeout: int = 10
    no_resource_online: bool = False
    resource_timeout: int = 10
    image_audit_limit: int = None
    no_image_semantic: bool = False
    image_semantic_limit: int = None
    image_semantic_timeout: int = 45
    no_image_detector: bool = False
    image_detector_limit: int = None
    image_detector_timeout: int = 60
    no_resume: bool = False
    fresh: bool = False
    llm_timeout: int = 45
    llm_retries: int = 1
    strict_failed_chunks: bool = False
    llm_cache_only: bool = False
    ai_detect: bool = False
    image_detect: bool = False
    report_actions_port: int = 8765

    @classmethod
    def from_args(cls, args) -> "RunRequest":
        return cls(
            input_path=Path(args.pdf_path),
            output=getattr(args, "output", "") or "",
            json_output=bool(getattr(args, "json", False)),
            no_open=bool(getattr(args, "no_open", False)),
            mineru=bool(getattr(args, "mineru", False)),
            no_mineru=bool(getattr(args, "no_mineru", False)),
            mineru_model=getattr(args, "mineru_model", "vlm"),
            mineru_lang=getattr(args, "mineru_lang", "ch"),
            max_chars=int(getattr(args, "max_chars", 4096)),
            no_reference_online=bool(getattr(args, "no_reference_online", False)),
            reference_online_limit=getattr(args, "reference_online_limit", None),
            reference_timeout=int(getattr(args, "reference_timeout", 10)),
            no_resource_online=bool(getattr(args, "no_resource_online", False)),
            resource_timeout=int(getattr(args, "resource_timeout", 10)),
            image_audit_limit=getattr(args, "image_audit_limit", None),
            no_image_semantic=bool(getattr(args, "no_image_semantic", False)),
            image_semantic_limit=getattr(args, "image_semantic_limit", None),
            image_semantic_timeout=int(getattr(args, "image_semantic_timeout", 45)),
            no_image_detector=bool(getattr(args, "no_image_detector", False)),
            image_detector_limit=getattr(args, "image_detector_limit", None),
            image_detector_timeout=int(getattr(args, "image_detector_timeout", 60)),
            no_resume=bool(getattr(args, "no_resume", False)),
            fresh=bool(getattr(args, "fresh", False)),
            llm_timeout=int(getattr(args, "llm_timeout", 45)),
            llm_retries=int(getattr(args, "llm_retries", 1)),
            strict_failed_chunks=bool(getattr(args, "strict_failed_chunks", False)),
            llm_cache_only=bool(getattr(args, "llm_cache_only", False)),
            ai_detect=bool(getattr(args, "ai_detect", False)),
            image_detect=bool(getattr(args, "image_detect", False)),
            report_actions_port=int(getattr(args, "report_actions_port", 8765)),
        )

    def to_args(self) -> argparse.Namespace:
        """Build the legacy argparse-shaped namespace required by the current engine."""
        return argparse.Namespace(
            pdf_path=str(self.input_path),
            output=self.output,
            json=self.json_output,
            no_open=self.no_open,
            mineru=self.mineru,
            no_mineru=self.no_mineru,
            mineru_model=self.mineru_model,
            mineru_lang=self.mineru_lang,
            max_chars=self.max_chars,
            no_reference_online=self.no_reference_online,
            reference_online_limit=self.reference_online_limit,
            reference_timeout=self.reference_timeout,
            no_resource_online=self.no_resource_online,
            resource_timeout=self.resource_timeout,
            image_audit_limit=self.image_audit_limit,
            no_image_semantic=self.no_image_semantic,
            image_semantic_limit=self.image_semantic_limit,
            image_semantic_timeout=self.image_semantic_timeout,
            no_image_detector=self.no_image_detector,
            image_detector_limit=self.image_detector_limit,
            image_detector_timeout=self.image_detector_timeout,
            no_resume=self.no_resume,
            fresh=self.fresh,
            llm_timeout=self.llm_timeout,
            llm_retries=self.llm_retries,
            strict_failed_chunks=self.strict_failed_chunks,
            llm_cache_only=self.llm_cache_only,
            ai_detect=self.ai_detect,
            image_detect=self.image_detect,
            report_actions_port=self.report_actions_port,
        )


@dataclass
class RunAuditContext:
    """Prepared runtime context for one legacy audit orchestration run."""
    output_dir: Path
    output_stem: str
    resume_dir: Path
    retry_command: str
    failed_artifact_kwargs: Dict[str, Any]
    run_runtime: Dict[str, Any]
    run_workspace: Dict[str, Any]
    allow_llm_cache_read: bool
    allow_llm_cache_write: bool
    has_pdf_input: bool
    use_mineru_default: bool


def _failure_field(failure: Any, name: str, default=None):
    if isinstance(failure, dict):
        return failure.get(name, default)
    return getattr(failure, name, default)


def _run_failure_payload(failure: Any) -> Dict[str, Any]:
    return {
        "capability": _failure_field(failure, "capability", ""),
        "error_class": _failure_field(failure, "error_class", ""),
        "message": _failure_field(failure, "message", ""),
        "fix_hints": list(_failure_field(failure, "fix_hints", []) or []),
        "completed_stages": list(_failure_field(failure, "completed_stages", []) or []),
        "retry_command": _failure_field(failure, "retry_command", ""),
        "details": dict(_failure_field(failure, "details", {}) or {}),
    }


@dataclass
class RunResult:
    """Structured audit run result returned by orchestration seams."""
    outcome: str
    exit_code: int = 0
    artifact_type: str = ""
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    workspace: Dict[str, Any] = field(default_factory=dict)
    failure: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def complete(cls, artifact_paths: Dict[str, str], workspace=None, meta=None):
        return cls("complete", exit_code=0, artifact_type="complete", artifact_paths=dict(artifact_paths), workspace=dict(workspace or {}), meta=dict(meta or {}))

    @classmethod
    def limited(cls, artifact_paths: Dict[str, str], workspace=None, meta=None):
        return cls("limited", exit_code=0, artifact_type="limited", artifact_paths=dict(artifact_paths), workspace=dict(workspace or {}), meta=dict(meta or {}))

    @classmethod
    def failed(cls, failure: Any, artifact_paths: Dict[str, str], workspace=None, meta=None):
        return cls(
            "failed",
            exit_code=1,
            artifact_type="failed",
            artifact_paths=dict(artifact_paths),
            workspace=dict(workspace or {}),
            failure=_run_failure_payload(failure),
            meta=dict(meta or {}),
        )


__all__ = ["RunRequest", "RunAuditContext", "RunResult"]
