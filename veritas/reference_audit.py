"""Reference plausibility audit orchestration."""

import concurrent.futures

from .limit_utils import _effective_limit
from .reference_parsing import build_reference_query, parse_references, reference_cache_key
from .runtime_metadata import runtime_utc_year
from .text_utils import _brief_text

__all__ = ["audit_references_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _reference_base_issues(ref, current_year):
    ref_issues = []
    year = ref.get("year")
    if not year:
        ref_issues.append("missing_year")
    else:
        try:
            if int(year) > current_year():
                ref_issues.append("future_year")
        except (TypeError, ValueError):
            pass
    if not ref.get("doi"):
        ref_issues.append("missing_doi")
    if not ref.get("has_journal_hint"):
        ref_issues.append("missing_journal_or_source")
    if len(ref.get("text", "")) < 25:
        ref_issues.append("too_short")
    return ref_issues


def _reference_online_skipped_result(ref, query_for):
    return {
        "online_status": "skipped",
        "confidence": 0.0,
        "problems": ["online_limit_reached"],
        "matched_sources": [],
        "query": query_for(ref),
    }


def _reference_online_error_result(ref, error, query_for, brief_text):
    return {
        "online_status": "error",
        "confidence": 0.0,
        "query": query_for(ref),
        "matched_sources": [],
        "problems": ["all_sources_error"],
        "source_errors": [f"verify_reference_online: {type(error).__name__}"],
        "error_message": brief_text(str(error), 240),
    }


def _reference_audit_status(issues, refs, online, effective_online_limit):
    status = "ok"
    if issues:
        status = "needs_review" if len(issues) < max(3, len(refs) // 3) else "weak"
    if online and refs:
        hard_online_issues = [
            item for item in issues
            if any(str(issue).startswith("online_") or issue in {"doi_not_found", "no_online_match"} for issue in item.get("issues", []))
        ]
        if hard_online_issues:
            status = "online_needs_review" if len(hard_online_issues) < max(3, len(refs) // 3) else "online_weak"
        elif effective_online_limit >= len(refs):
            online_statuses = [
                (ref.get("online") or {}).get("online_status")
                for ref in refs
            ]
            if online_statuses and all(item == "verified" for item in online_statuses):
                status = "ok"
            elif online_statuses and all(item in {"verified", "likely"} for item in online_statuses):
                status = "needs_review"
    return status


def audit_references_from_namespace(namespace, references_text, online=False, online_limit=50, timeout=10, cache=None):
    """Reference plausibility check with optional online scholarly database verification."""
    parse = _namespace_value(namespace, "parse_references", parse_references)
    effective_limit = _namespace_value(namespace, "_effective_limit", _effective_limit)
    cache_key_for = _namespace_value(namespace, "reference_cache_key", reference_cache_key)
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    verify_online = _namespace_value(namespace, "verify_reference_online")
    current_year = _namespace_value(namespace, "runtime_utc_year", runtime_utc_year)
    brief_text = _namespace_value(namespace, "_brief_text", _brief_text)

    refs = parse(references_text)
    effective_online_limit = effective_limit(online_limit, len(refs))
    online_checked = 0
    online_cache = cache if isinstance(cache, dict) else {}

    if online:
        fetch_jobs = []
        for idx, ref in enumerate(refs, 1):
            if idx <= effective_online_limit:
                cache_key = cache_key_for(ref)
                online_result = online_cache.get(cache_key)
                if online_result:
                    ref["online"] = online_result
                else:
                    fetch_jobs.append((idx, ref, cache_key))
            else:
                ref["online"] = _reference_online_skipped_result(ref, query_for)

        if fetch_jobs:
            workers = min(4, len(fetch_jobs))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(verify_online, ref, timeout=timeout): (idx, ref, cache_key)
                    for idx, ref, cache_key in fetch_jobs
                }
                for future in concurrent.futures.as_completed(future_map):
                    idx, ref, cache_key = future_map[future]
                    try:
                        online_result = future.result()
                    except Exception as e:
                        online_result = _reference_online_error_result(ref, e, query_for, brief_text)
                    online_cache[cache_key] = online_result
                    ref["online"] = online_result

        online_checked = sum(
            1 for idx, ref in enumerate(refs, 1)
            if idx <= effective_online_limit and (ref.get("online") or {}).get("online_status") != "skipped"
        )

    issues = []
    for idx, ref in enumerate(refs, 1):
        ref_issues = _reference_base_issues(ref, current_year)

        if online and idx <= effective_online_limit:
            cache_key = cache_key_for(ref)
            online_result = ref.get("online") or online_cache.get(cache_key) or {}
            ref["online"] = online_result
            online_status = online_result.get("online_status")
            if online_status in {"not_found", "weak", "error"}:
                ref_issues.append(f"online_{online_status}")
            ref_issues.extend(online_result.get("problems") or [])

        if ref_issues:
            issues.append({"index": idx, "issues": ref_issues, "text": ref.get("text", "")})
    status = _reference_audit_status(issues, refs, online, effective_online_limit)
    return {
        "status": status,
        "reference_count": len(refs),
        "doi_count": sum(1 for r in refs if r.get("doi")),
        "year_count": sum(1 for r in refs if r.get("year")),
        "online_enabled": bool(online),
        "online_checked": online_checked,
        "issues": issues,
        "references": refs[:200],
        "note": (
            "在线真实性校检：优先用DOI精确检索，再用题名/年份在Crossref、OpenAlex和PubMed进行多源核验；"
            "结果为尽力检索证据，不等同于绝对证明。"
            if online else
            "离线格式/可核验性校检：检查DOI、年份、来源字段等基本信息；不代表已联网验证引用真实存在。"
        ),
    }
