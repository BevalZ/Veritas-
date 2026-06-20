"""Audit run orchestration boundary."""

from .run_types import RunRequest, RunResult


def run_audit(*args, **kwargs):
    from .legacy import run_audit as legacy_run_audit

    return legacy_run_audit(*args, **kwargs)


__all__ = ["RunRequest", "RunResult", "run_audit"]
