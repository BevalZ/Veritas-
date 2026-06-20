"""Runtime clock metadata used by reports and deterministic date rules."""

import datetime
from typing import Any, Dict


def runtime_utc_year() -> int:
    """Return the runtime UTC year for deterministic date checks."""
    return datetime.datetime.now(datetime.timezone.utc).year


def runtime_metadata() -> Dict[str, Any]:
    """Return runtime clock metadata used by reports and deterministic date rules."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    local_now = utc_now.astimezone()
    return {
        "local_time": local_now.isoformat(timespec="seconds"),
        "timezone": local_now.tzname() or str(local_now.tzinfo or ""),
        "utc_time": utc_now.isoformat(timespec="seconds"),
        "utc_year": utc_now.year,
        "future_year_basis": "utc_year",
    }


def ensure_runtime_meta(meta: Dict[str, Any] = None) -> Dict[str, Any]:
    normalized = dict(meta or {})
    runtime = dict(normalized.get("runtime") or {})
    defaults = runtime_metadata()
    for key, value in defaults.items():
        runtime.setdefault(key, value)
    normalized["runtime"] = runtime
    return normalized


__all__ = [
    "runtime_utc_year",
    "runtime_metadata",
    "ensure_runtime_meta",
]
