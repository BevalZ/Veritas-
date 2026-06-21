"""Versioned deterministic risk scoring and chunk-report merge rules."""

from typing import Any, Dict

from .risk_rule_helpers import (
    _build_merged_conclusion,
    _build_merged_summary,
    _downgrade_extraction_red_flags,
    _downgrade_unverified_future_publication_checks,
    _is_extraction_limited_check,
    _max_risk,
    _merge_check_into,
    _same_or_similar_check,
)
from .runtime_metadata import runtime_utc_year
from .versions import RISK_RULE_VERSION


def apply_risk_rules(report: Dict[str, Any], stat_result=None, image_audit=None) -> Dict[str, Any]:
    """Apply versioned deterministic rules for final risk and evidence risk score."""
    report = dict(report or {})
    checks = [dict(check) for check in report.get("checks", []) if isinstance(check, dict)]
    checks = _downgrade_unverified_future_publication_checks(checks, current_year=runtime_utc_year())
    checks = _downgrade_extraction_red_flags(checks)
    warning_checks = [check for check in checks if "疑点" in str(check.get("verdict", ""))]
    red_flags = sum(1 for check in checks if "红旗" in str(check.get("verdict", "")))
    extraction_warnings = sum(1 for check in warning_checks if _is_extraction_limited_check(check))
    evidence_warnings = len(warning_checks) - extraction_warnings
    stat_adjustments = []
    detector_high = 0
    if isinstance(image_audit, dict):
        for image in image_audit.get("images", []) or []:
            detector = image.get("detector") or {}
            try:
                detector_score = float(detector.get("score"))
            except (TypeError, ValueError):
                detector_score = 0
            if detector.get("status") == "ok" and detector_score >= 80:
                detector_high += 1

    if red_flags >= 2 and evidence_warnings >= 2:
        risk_level = "严重证据冲突"
    elif red_flags >= 1 or evidence_warnings >= 3:
        risk_level = "高"
    elif evidence_warnings >= 1 or extraction_warnings >= 1 or detector_high:
        risk_level = "中"
    else:
        risk_level = "低"

    raw_detection_score = red_flags * 35 + min(evidence_warnings, 10) * 5 + min(extraction_warnings, 10) + min(detector_high, 3) * 5
    if stat_result and stat_result.get("benford_deviation"):
        benford_weight = 30 if (red_flags or evidence_warnings) else 12
        raw_detection_score += int(stat_result["benford_deviation"] * benford_weight)
        if stat_result["benford_deviation"] > 0.45:
            stat_adjustments.append("benford_high_deviation")
    if stat_result and stat_result.get("p_value_abnormal", 0) > 0:
        stat_adjustments.append("p_value_abnormal")

    detection_score = min(100, raw_detection_score)
    if risk_level == "严重证据冲突":
        detection_score = max(detection_score, 85)
    elif not red_flags and not evidence_warnings:
        detection_score = min(detection_score, 60)

    report["checks"] = checks
    report["risk_level"] = risk_level
    report["detection_score"] = detection_score
    report["rule_version"] = RISK_RULE_VERSION
    report["score_breakdown"] = {
        "rule_version": RISK_RULE_VERSION,
        "red_flags": red_flags,
        "evidence_warnings": evidence_warnings,
        "extraction_warnings": extraction_warnings,
        "image_detector_high": detector_high,
        "stat_adjustments": stat_adjustments,
        "raw_score": raw_detection_score,
    }
    return report


def _collect_chunk_checks(reports):
    all_checks = []
    for index, report in enumerate(reports):
        if report.get("parse_error"):
            continue
        for check in report.get("checks", []):
            if not isinstance(check, dict):
                continue
            candidate = dict(check)
            candidate["_source_chunk"] = index + 1
            for existing in all_checks:
                if _same_or_similar_check(existing, candidate):
                    _merge_check_into(existing, candidate, index)
                    break
            else:
                candidate["_source_chunks"] = [index + 1]
                all_checks.append(candidate)
    return all_checks


def merge_chunk_reports(reports, stat_result=None):
    """Merge chunk reports, deduplicate findings, and recalculate final risk."""
    all_checks = _collect_chunk_checks(reports)

    all_checks = _downgrade_unverified_future_publication_checks(all_checks, current_year=runtime_utc_year())
    all_checks = _downgrade_extraction_red_flags(all_checks)

    red_flags = sum(1 for check in all_checks if "红旗" in check.get("verdict", ""))
    warning_checks = [check for check in all_checks if "疑点" in check.get("verdict", "")]
    extraction_warnings = sum(1 for check in warning_checks if _is_extraction_limited_check(check))
    evidence_warnings = len(warning_checks) - extraction_warnings
    warnings = len(warning_checks)

    if red_flags >= 3:
        risk_level = "高"
    elif red_flags >= 1 or evidence_warnings >= 3:
        risk_level = "中"
    elif evidence_warnings >= 1 or extraction_warnings >= 1:
        risk_level = "低"
    else:
        risk_level = "低"

    stat_adjustments = []
    if stat_result:
        if stat_result.get("benford_deviation") and stat_result["benford_deviation"] > 0.3:
            stat_adjustments.append("benford_high_deviation")
            if red_flags or evidence_warnings:
                risk_level = _max_risk(risk_level, "中")
        if stat_result.get("p_value_abnormal", 0) > 2:
            stat_adjustments.append("p_value_abnormal")
            risk_level = _max_risk(risk_level, "中")

    raw_detection_score = red_flags * 35 + min(evidence_warnings, 10) * 5 + min(extraction_warnings, 10)
    if stat_result and stat_result.get("benford_deviation"):
        benford_weight = 30 if (red_flags or evidence_warnings) else 12
        raw_detection_score += int(stat_result["benford_deviation"] * benford_weight)
    detection_score = min(100, raw_detection_score)
    if red_flags == 0:
        detection_score = min(detection_score, 85)

    merged_summary = _build_merged_summary(
        len([report for report in reports if not report.get("parse_error")]) or len(reports),
        risk_level,
        red_flags,
        evidence_warnings,
        extraction_warnings,
    )
    merged_conclusion = _build_merged_conclusion(
        reports,
        all_checks,
        risk_level,
        red_flags,
        evidence_warnings,
        extraction_warnings,
        stat_adjustments,
    )

    for check in all_checks:
        check.pop("_source_chunk", None)
        check.pop("_source_chunks", None)

    return {
        "summary": merged_summary,
        "risk_level": risk_level,
        "detection_score": detection_score,
        "score_breakdown": {
            "rule_version": RISK_RULE_VERSION,
            "red_flags": red_flags,
            "evidence_warnings": evidence_warnings,
            "extraction_warnings": extraction_warnings,
            "image_detector_high": 0,
            "total_warnings": warnings,
            "stat_adjustments": stat_adjustments,
            "raw_score": raw_detection_score,
        },
        "checks": all_checks,
        "conclusion": merged_conclusion,
        "_merged_from": len(reports),
        "rule_version": RISK_RULE_VERSION,
    }


__all__ = ["RISK_RULE_VERSION", "apply_risk_rules", "merge_chunk_reports"]
