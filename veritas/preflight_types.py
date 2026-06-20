"""Preflight result types and per-run cache helper."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PreflightResult:
    """One critical capability preflight result for the current run only."""
    capability: str
    ok: bool
    error_class: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "ok": self.ok,
            "error_class": self.error_class,
            "message": self.message,
            "details": dict(self.details),
            "created_at": self.created_at,
        }


def run_preflight_once(preflight_state: Dict[str, PreflightResult], capability: str, runner) -> PreflightResult:
    """Run and cache a preflight only in the caller's in-memory run state."""
    if capability not in preflight_state:
        preflight_state[capability] = runner()
    return preflight_state[capability]


__all__ = ["PreflightResult", "run_preflight_once"]
