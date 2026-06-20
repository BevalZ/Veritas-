"""Report rendering boundary.

Renderers accept stable dataclass models or plain dictionaries, normalize them
at the boundary, then delegate to the existing Markdown/HTML renderer logic.
"""

from typing import Any, Dict

from .models import model_to_dict


def _report_to_dict(report: Any) -> Dict[str, Any]:
    payload = model_to_dict(report)
    checks = []
    for check in payload.get("checks") or []:
        checks.append(model_to_dict(check))
    payload["checks"] = checks
    return payload


def render_markdown_report(report: Any, input_path: Any, meta: Dict[str, Any], stat_result: Dict[str, Any]) -> str:
    from .legacy import format_report

    return format_report(_report_to_dict(report), input_path, dict(meta or {}), dict(stat_result or {}))


def render_html_report(report: Any, input_path: Any, meta: Dict[str, Any], stat_result: Dict[str, Any]) -> str:
    from .legacy import format_html_report

    return format_html_report(_report_to_dict(report), input_path, dict(meta or {}), dict(stat_result or {}))


__all__ = ["render_markdown_report", "render_html_report"]
