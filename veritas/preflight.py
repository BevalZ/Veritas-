"""Critical capability preflight boundary."""

from .failed_diagnostics import preflight_failure_to_audit_failure
from .legacy import (
    preflight_mineru,
    preflight_text_llm,
)
from .preflight_types import PreflightResult, run_preflight_once

__all__ = [
    "PreflightResult",
    "preflight_mineru",
    "preflight_text_llm",
    "run_preflight_once",
    "preflight_failure_to_audit_failure",
]
