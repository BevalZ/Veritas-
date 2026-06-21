"""Online reference verification provider lookups."""

import json
import urllib.parse

from .http_client import _http_request
from .reference_parsing import (
    _crossref_work_to_match,
    _html_title,
    _html_to_searchable_text,
    _official_page_matches_reference,
    _official_site_search_urls,
    _openalex_work_to_match,
    _pubmed_summary_to_match,
    _score_reference_matches,
    build_reference_query,
)

__all__ = [
    "_reference_get_json_from_namespace",
    "lookup_crossref_reference_from_namespace",
    "lookup_openalex_reference_from_namespace",
    "lookup_pubmed_reference_from_namespace",
    "lookup_official_site_reference_from_namespace",
    "verify_reference_online_from_namespace",
]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _reference_get_json_from_namespace(namespace, url, timeout=10, headers=None):
    # Reference verification fans out across several providers. Keep each source
    # fast-fail so a full bibliography cannot hang on one slow provider.
    http_request = _namespace_value(namespace, "_http_request", _http_request)
    data, _ = http_request(url, "GET", headers=headers or {}, timeout=timeout)
    return json.loads(data.decode("utf-8", errors="replace"))


def lookup_crossref_reference_from_namespace(namespace, ref, timeout=10):
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    get_json = _namespace_value(namespace, "_reference_get_json")
    work_to_match = _namespace_value(namespace, "_crossref_work_to_match", _crossref_work_to_match)
    if not callable(get_json):
        get_json = lambda url, timeout=10, headers=None: _reference_get_json_from_namespace(
            namespace,
            url,
            timeout=timeout,
            headers=headers,
        )
    query = query_for(ref)
    matches = []
    last_error = None
    if query.get("doi"):
        try:
            url = "https://api.crossref.org/works/" + urllib.parse.quote(query["doi"], safe="")
            data = get_json(url, timeout=timeout)
            work = data.get("message") or {}
            if work:
                matches.append(work_to_match(work))
                return matches
        except Exception as e:
            last_error = e
    if query.get("title"):
        try:
            title = urllib.parse.quote(query["title"])
            url = f"https://api.crossref.org/works?query.title={title}&rows=5"
            data = get_json(url, timeout=timeout)
            for work in (data.get("message") or {}).get("items") or []:
                matches.append(work_to_match(work))
        except Exception as e:
            last_error = e
    bibliographic = urllib.parse.quote(query.get("bibliographic") or "")
    if not bibliographic:
        return matches
    try:
        url = f"https://api.crossref.org/works?query.bibliographic={bibliographic}&rows=5"
        data = get_json(url, timeout=timeout)
        for work in (data.get("message") or {}).get("items") or []:
            matches.append(work_to_match(work))
    except Exception as e:
        last_error = e
    if last_error and not matches:
        raise last_error
    return matches


def lookup_openalex_reference_from_namespace(namespace, ref, timeout=10):
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    get_json = _namespace_value(namespace, "_reference_get_json")
    work_to_match = _namespace_value(namespace, "_openalex_work_to_match", _openalex_work_to_match)
    if not callable(get_json):
        get_json = lambda url, timeout=10, headers=None: _reference_get_json_from_namespace(
            namespace,
            url,
            timeout=timeout,
            headers=headers,
        )
    query = query_for(ref)
    matches = []
    last_error = None
    if query.get("doi"):
        try:
            url = "https://api.openalex.org/works/doi:" + urllib.parse.quote(query["doi"], safe="")
            data = get_json(url, timeout=timeout)
            if data:
                matches.append(work_to_match(data))
                return matches
        except Exception as e:
            last_error = e
    if query.get("title"):
        try:
            title = urllib.parse.quote(query["title"])
            url = f"https://api.openalex.org/works?filter=title.search:{title}&per-page=5"
            data = get_json(url, timeout=timeout)
            for work in (data.get("results") or []):
                matches.append(work_to_match(work))
        except Exception as e:
            last_error = e
    search = urllib.parse.quote(query.get("bibliographic") or "")
    if not search:
        return matches
    try:
        url = f"https://api.openalex.org/works?search={search}&per-page=5"
        data = get_json(url, timeout=timeout)
        for work in (data.get("results") or []):
            matches.append(work_to_match(work))
    except Exception as e:
        last_error = e
    if last_error and not matches:
        raise last_error
    return matches


def lookup_pubmed_reference_from_namespace(namespace, ref, timeout=10):
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    get_json = _namespace_value(namespace, "_reference_get_json")
    summary_to_match = _namespace_value(namespace, "_pubmed_summary_to_match", _pubmed_summary_to_match)
    if not callable(get_json):
        get_json = lambda url, timeout=10, headers=None: _reference_get_json_from_namespace(
            namespace,
            url,
            timeout=timeout,
            headers=headers,
        )
    query = query_for(ref)
    term = query.get("doi") or query.get("bibliographic") or ""
    if not term:
        return []
    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&retmode=json&retmax=5&term={urllib.parse.quote(term)}"
    )
    search = get_json(search_url, timeout=timeout)
    ids = ((search.get("esearchresult") or {}).get("idlist") or [])[:5]
    if not ids:
        return []
    summary_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&retmode=json&id={','.join(ids)}"
    )
    summary = get_json(summary_url, timeout=timeout)
    result = summary.get("result") or {}
    return [summary_to_match(uid, result.get(uid) or {}) for uid in ids if result.get(uid)]


def lookup_official_site_reference_from_namespace(namespace, ref, timeout=10):
    """Verify references from DOI landing pages and publisher/official site searches."""
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    http_request = _namespace_value(namespace, "_http_request", _http_request)
    html_to_text = _namespace_value(namespace, "_html_to_searchable_text", _html_to_searchable_text)
    html_title = _namespace_value(namespace, "_html_title", _html_title)
    page_matches = _namespace_value(namespace, "_official_page_matches_reference", _official_page_matches_reference)
    site_urls = _namespace_value(namespace, "_official_site_search_urls", _official_site_search_urls)
    query = query_for(ref)
    matches = []
    if query.get("doi"):
        doi_url = "https://doi.org/" + urllib.parse.quote(query["doi"], safe="/")
        data, _ = http_request(doi_url, "GET", headers={"Accept": "text/html,*/*;q=0.8"}, timeout=timeout)
        page_text = html_to_text(data)
        title = html_title(data) or query.get("title") or query.get("doi")
        if query.get("doi") or page_matches(ref, page_text):
            matches.append({
                "source": "DOI landing page",
                "title": query.get("title") or title,
                "year": query.get("year"),
                "doi": query.get("doi"),
                "authors": [query.get("author")] if query.get("author") else [],
                "container": query.get("container"),
                "url": doi_url,
                "retracted": False,
                "official_site": True,
            })

    for label, url in site_urls(ref):
        data, _ = http_request(url, "GET", headers={"Accept": "text/html,*/*;q=0.8"}, timeout=timeout)
        page_text = html_to_text(data)
        if not page_matches(ref, page_text):
            continue
        matches.append({
            "source": f"Official site: {label}",
            "title": query.get("title") or html_title(data),
            "year": query.get("year"),
            "doi": query.get("doi"),
            "authors": [query.get("author")] if query.get("author") else [],
            "container": query.get("container") or label,
            "url": url,
            "retracted": False,
            "official_site": True,
        })
    return matches


def verify_reference_online_from_namespace(namespace, ref, timeout=10):
    query_for = _namespace_value(namespace, "build_reference_query", build_reference_query)
    score_matches = _namespace_value(namespace, "_score_reference_matches", _score_reference_matches)
    crossref_lookup = _namespace_value(namespace, "lookup_crossref_reference")
    openalex_lookup = _namespace_value(namespace, "lookup_openalex_reference")
    pubmed_lookup = _namespace_value(namespace, "lookup_pubmed_reference")
    official_lookup = _namespace_value(namespace, "lookup_official_site_reference")
    if not callable(crossref_lookup):
        crossref_lookup = lambda item, timeout=10: lookup_crossref_reference_from_namespace(namespace, item, timeout=timeout)
    if not callable(openalex_lookup):
        openalex_lookup = lambda item, timeout=10: lookup_openalex_reference_from_namespace(namespace, item, timeout=timeout)
    if not callable(pubmed_lookup):
        pubmed_lookup = lambda item, timeout=10: lookup_pubmed_reference_from_namespace(namespace, item, timeout=timeout)
    if not callable(official_lookup):
        official_lookup = lambda item, timeout=10: lookup_official_site_reference_from_namespace(namespace, item, timeout=timeout)

    query = query_for(ref)
    source_errors = []
    raw_matches = []
    standard_sources_ok = 0
    for lookup in (crossref_lookup, openalex_lookup, pubmed_lookup):
        try:
            raw_matches.extend(lookup(ref, timeout=timeout))
            standard_sources_ok += 1
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status not in {404, 410}:
                source_errors.append(f"{lookup.__name__.replace('lookup_', '').replace('_reference', '')}: {type(e).__name__}")

    scored = score_matches(ref, raw_matches)
    if standard_sources_ok and (not scored or scored[0].get("match_score", 0) < 0.92):
        try:
            official_matches = official_lookup(ref, timeout=timeout)
            if official_matches:
                raw_matches.extend(official_matches)
                scored = score_matches(ref, raw_matches)
        except Exception as e:
            source_errors.append(f"official_site: {type(e).__name__}")

    best = scored[0] if scored else None
    confidence = float(best.get("match_score", 0.0)) if best else 0.0
    problems = []
    if not scored:
        problems.append("doi_not_found" if query.get("doi") else "no_online_match")
    if source_errors and not scored and not standard_sources_ok:
        problems.append("all_sources_error")
    elif source_errors:
        problems.append("partial_source_error")
    if best:
        problems.extend(best.get("_match_problems") or [])
    problems = list(dict.fromkeys(problems[:8]))

    if confidence >= 0.92:
        status = "verified"
    elif confidence >= 0.68:
        status = "likely"
    elif confidence >= 0.38:
        status = "weak"
    elif source_errors and not scored:
        status = "error"
    else:
        status = "not_found"

    return {
        "online_status": status,
        "confidence": round(confidence, 3),
        "query": query,
        "matched_sources": [{k: v for k, v in match.items() if k != "_match_problems"} for match in scored[:5]],
        "problems": problems,
        "source_errors": source_errors,
    }
