"""Report action context helpers for follow-up draft generation."""

from pathlib import Path

from .cross_file_consistency import _cross_file_severity_label
from .evidence_rendering import _clean_mineru_table_block
from .reference_parsing import _clean_reference_text
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_text,
    _is_suspicious_check,
)
from .text_utils import _brief_text

__all__ = ["_report_action_context"]


def _report_action_context(report, pdf_path, meta, stat_result):
    meta = meta or {}
    paper_identity = meta.get("paper_identity") or {}
    checks = sorted(report.get("checks", []) if isinstance(report, dict) else [], key=_check_sort_key)
    suspicious = [c for c in checks if _is_suspicious_check(c)]
    selected = suspicious[:10] if suspicious else checks[:8]
    issues = []
    for idx, c in enumerate(selected, 1):
        issues.append({
            "id": f"issue-{idx}",
            "source": "audit",
            "category": c.get("category", ""),
            "item": c.get("item", ""),
            "verdict": c.get("verdict", ""),
            "evidence": _brief_text(_clean_mineru_table_block(_check_source_text(c)), 900),
            "reason": _brief_text(_check_reason(c), 900),
        })
    cross_file_audit = (meta or {}).get("cross_file_consistency_audit") or {}
    cross_file_issues = []
    for idx, finding in enumerate((cross_file_audit.get("findings") or [])[:8], 1):
        cross_file_issue = {
            "id": f"cross-file-{idx}",
            "source": "cross_file_consistency",
            "category": "跨文件一致性审查",
            "item": finding.get("conflict_type", ""),
            "verdict": _cross_file_severity_label(finding.get("severity")),
            "evidence": _brief_text(
                f"{finding.get('claim_source_label')} / {finding.get('claim_file')}: {finding.get('claim_excerpt')} "
                f"|| {finding.get('counter_source_label')} / {finding.get('counter_file')}: {finding.get('counter_excerpt')}",
                900,
            ),
            "reason": _brief_text(finding.get("reason") or finding.get("manual_check"), 900),
        }
        cross_file_issues.append(cross_file_issue)
    issues = cross_file_issues + issues
    evidence_chain_audit = (meta or {}).get("evidence_chain_audit") or {}
    evidence_chain_issues = []
    for idx, cluster in enumerate((evidence_chain_audit.get("clusters") or [])[:10], 1):
        evidence_chain_issues.append({
            "id": cluster.get("id") or f"evidence-cluster-{idx}",
            "source": "evidence_chain_audit",
            "category": "证据链与证据簇审查",
            "item": cluster.get("title", ""),
            "verdict": _cross_file_severity_label(cluster.get("severity")),
            "evidence": _brief_text(cluster.get("summary", ""), 900),
            "reason": _brief_text(
                f"来源: {', '.join(cluster.get('source_types') or [])}；证据数: {cluster.get('evidence_count', 0)}。",
                900,
            ),
            "default_selected": cluster.get("severity") == "strong",
        })
    if evidence_chain_issues:
        issues = evidence_chain_issues + issues
    reference_audit = (meta or {}).get("reference_audit") or {}
    ref_issues = []
    for issue in (reference_audit.get("issues") or [])[:8]:
        ref_issues.append({
            "index": issue.get("index"),
            "issues": issue.get("issues", []),
            "text": _brief_text(_clean_reference_text(issue.get("text", "")), 500),
        })
    image_audit = (meta or {}).get("image_audit") or {}
    image_issues = []
    for img in (image_audit.get("images") or [])[:8]:
        sem = img.get("semantic") or {}
        detector = img.get("detector") or {}
        if img.get("risk") == "local_warning" or sem.get("reasonability") in {"需人工核对", "可疑"} or (detector.get("score") or 0) >= 50:
            image_issues.append({
                "file": img.get("file"),
                "local_issues": img.get("issues", []),
                "semantic": _brief_text(sem.get("summary", ""), 360),
                "detector_score": detector.get("score"),
            })
    resource_audit = (meta or {}).get("resource_audit") or {}
    resource_issues = []
    for issue in (resource_audit.get("issues") or [])[:8]:
        resource_issues.append({
            "index": issue.get("index"),
            "url": issue.get("url"),
            "type": issue.get("type"),
            "status": issue.get("status"),
            "problem": issue.get("problem"),
        })
    return {
        "paper": str(pdf_path),
        "artifact_type": meta.get("artifact_type") or meta.get("report_type") or "complete",
        "limited_reasons": meta.get("limited_reasons") or [],
        "artifact_paths": meta.get("artifact_paths") or {},
        "followups_dir": meta.get("followups_dir") or str((Path((meta.get("artifact_paths") or {}).get("html") or pdf_path).parent / "followups")),
        "paper_identity": {
            "title": _brief_text(paper_identity.get("title", ""), 300),
            "journal": _brief_text(paper_identity.get("journal", ""), 220),
            "authors": [
                _brief_text(author, 120)
                for author in (paper_identity.get("authors") or [])
                if str(author or "").strip()
            ][:8],
            "doi": _brief_text(paper_identity.get("doi", ""), 120),
            "year": _brief_text(paper_identity.get("year", ""), 20),
        },
        "summary": _brief_text(report.get("summary", ""), 1200) if isinstance(report, dict) else "",
        "risk_level": report.get("risk_level", "") if isinstance(report, dict) else "",
        "detection_score": report.get("detection_score", "") if isinstance(report, dict) else "",
        "conclusion": _brief_text(report.get("conclusion", ""), 1200) if isinstance(report, dict) else "",
        "top_issues": issues,
        "cross_file_consistency": {
            "status": cross_file_audit.get("status"),
            "checked_files": cross_file_audit.get("checked_files"),
            "finding_count": cross_file_audit.get("finding_count"),
            "findings": cross_file_issues,
        },
        "evidence_chain_audit": {
            "status": evidence_chain_audit.get("status"),
            "cluster_count": evidence_chain_audit.get("cluster_count"),
            "finding_count": evidence_chain_audit.get("finding_count"),
            "strong_count": evidence_chain_audit.get("strong_count"),
            "clusters": evidence_chain_issues,
        },
        "stat": {
            "number_count": stat_result.get("number_count"),
            "p_value_count": stat_result.get("p_value_count"),
            "p_value_abnormal": stat_result.get("p_value_abnormal"),
            "number_consistency": stat_result.get("number_consistency"),
            "benford_status": stat_result.get("benford_status"),
        },
        "references": {
            "reference_count": reference_audit.get("reference_count"),
            "online_checked": reference_audit.get("online_checked"),
            "issues": ref_issues,
        },
        "resources": {
            "resource_count": resource_audit.get("resource_count"),
            "online_checked": resource_audit.get("online_checked"),
            "issues": resource_issues,
        },
        "images": image_issues,
    }
