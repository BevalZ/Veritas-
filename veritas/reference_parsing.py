"""Reference section parsing and query-building helpers."""

import hashlib
import html
import re
import urllib.parse

from .text_utils import _brief_text, _normalize_title, _title_tokens, _token_similarity

__all__ = [
    "REFERENCE_CONTAINER_WORD_RE",
    "REFERENCE_OFFICIAL_SITE_RULES",
    "split_references_from_text",
    "parse_references",
    "_truncate_reference_suffix",
    "_reference_items_from_numbered_lines",
    "_looks_like_reference_table_noise",
    "_clean_reference_text",
    "_normalize_doi",
    "_looks_like_reference_container_part",
    "_looks_like_reference_author_fragment",
    "_name_tokens",
    "_author_similarity",
    "_reference_year",
    "extract_reference_year_hint",
    "extract_reference_author_hint",
    "extract_reference_container_hint",
    "extract_reference_title",
    "build_reference_query",
    "reference_cache_key",
    "_crossref_work_to_match",
    "_openalex_work_to_match",
    "_pubmed_summary_to_match",
    "_html_to_searchable_text",
    "_html_title",
    "_official_page_matches_reference",
    "_official_site_search_urls",
    "_score_reference_match",
    "_score_reference_matches",
]


def split_references_from_text(text):
    """Remove reference sections from main audit text and return parsed tail text."""
    text = str(text or "")
    pattern = re.compile(
        r"(?im)^(?:\[\[BLOCK[^\]]*\]\]\s*)?(?:#+\s*)?(?:references?|bibliography|参考文献|参考资料|works cited)\s*(?:\[\[/BLOCK\]\]\s*)?$"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return text, ""
    start = matches[-1].start()
    main_text = text[:start].rstrip()
    references_text = text[start:].strip()
    return main_text, references_text


def parse_references(references_text):
    text = _clean_reference_text(references_text)
    text = _truncate_reference_suffix(text)
    text = re.sub(r"(?im)^(?:#+\s*)?(?:references?|bibliography|参考文献|参考资料|works cited)\s*$", "", text).strip()
    if not text:
        return []
    raw_items = _reference_items_from_numbered_lines(text)
    if len(raw_items) <= 1:
        raw_items = re.split(r"\n{2,}", text)
    refs = []
    for item in raw_items:
        item = re.sub(r"\s+", " ", item).strip()
        item = re.sub(r"^(?:\[\d+\]|\d+\.|\(\d+\))\s*", "", item)
        item = re.sub(r"^\d+\.\s*", "", item)
        if len(item) < 8:
            continue
        if _looks_like_reference_table_noise(item):
            continue
        doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", item, re.IGNORECASE)
        year = extract_reference_year_hint(item)
        has_journal_hint = bool(re.search(r"\b(?:journal|j\.|proc\.|nature|science|cell|ieee|acm|springer|elsevier|frontiers|plos|bmc|lancet)\b", item, re.IGNORECASE))
        doi = _normalize_doi(doi_match.group(0)) if doi_match else ""
        refs.append({
            "text": item,
            "doi": doi,
            "year": year,
            "has_journal_hint": has_journal_hint,
            "title_hint": extract_reference_title(item),
            "author_hint": extract_reference_author_hint(item),
            "container_hint": extract_reference_container_hint(item),
        })
    return refs


def _truncate_reference_suffix(text):
    """Drop non-reference sections accidentally captured after References."""
    text = str(text or "")
    suffix_heading = re.search(
        r"(?im)^\s*(?:figure\s+legends?|figures?|tables?|supplementary\s+(?:material|information)|acknowledg(?:e)?ments?)\s*$",
        text,
    )
    if suffix_heading:
        return text[:suffix_heading.start()].rstrip()
    return text


def _reference_items_from_numbered_lines(text):
    """Build reference items while tolerating MinerU per-page list numbering."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    items = []
    current = []
    expected_number = 1

    def flush():
        nonlocal current
        if current:
            items.append(" ".join(current).strip())
            current = []

    for line in lines:
        if re.fullmatch(r"(?i)(?:article\s+in\s+press|references?|bibliography|参考文献|参考资料|works cited)", line):
            continue
        bracketed = re.match(r"^\[(\d+)\]\s*(.+)$", line)
        if bracketed:
            visible_number = int(bracketed.group(1))
            body = bracketed.group(2).strip()
        else:
            numbered = re.match(r"^(\d+)\.\s*(.+)$", line)
            if not numbered:
                if current:
                    current.append(line)
                continue
            local_number = int(numbered.group(1))
            rest = numbered.group(2).strip()
            nested = re.match(r"^(\d+)\.?\s*(.+)$", rest)
            if nested:
                visible_number = int(nested.group(1))
                body = nested.group(2).strip()
            else:
                visible_number = local_number
                body = rest

        if not current or visible_number == expected_number:
            flush()
            current = [body]
            expected_number = visible_number + 1
        else:
            current.append(body)
    flush()
    return items


def _looks_like_reference_table_noise(item):
    """Avoid treating extracted tables as reference entries."""
    decoded = html.unescape(str(item or "")).strip()
    lowered = decoded.lower()
    if "[[table_start" in lowered or "[[table_continuation" in lowered:
        return True
    td_count = len(re.findall(r"</?t[dh]\b", lowered))
    tr_count = len(re.findall(r"</?tr\b", lowered))
    if "<table" in lowered and (td_count >= 4 or tr_count >= 2):
        return True
    pipe_cells = sum(1 for line in decoded.splitlines() if line.count("|") >= 3)
    if pipe_cells >= 2 and not re.search(r"\b(?:doi|pmid|arxiv|journal|volume|issue)\b", decoded, re.I):
        return True
    return False


def _clean_reference_text(text):
    text = str(text or "")
    text = re.sub(r"\[\[EXTRACTION_NOTE\]\].*?\[\[/EXTRACTION_NOTE\]\]", "\n", text, flags=re.S)
    text = re.sub(r"\[\[/?(?:BLOCK|FIGURE)[^\]]*\]\]", "\n", text, flags=re.I)
    text = re.sub(r"\[\[TABLE_START[^\]]*\]\]|\[\[TABLE_END\]\]|\[\[TABLE_CONTINUATION[^\]]*\]\]", "\n", text)
    text = re.sub(r"(?m)^===\s*文件:.*?===\s*$", "\n", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_doi(value):
    value = html.unescape(str(value or "")).strip()
    value = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"(?i)^doi\s*[:：]\s*", "", value)
    value = value.strip().rstrip(".,;)]}")
    return value.lower()


REFERENCE_CONTAINER_WORD_RE = re.compile(
    r"\b(?:journal|jclin|proc\.?|proceedings|nature|science|cell|frontiers|plos|bmc|"
    r"lancet|thyroid|oncology|endocrinology|communications?|commun|annals|cancers|"
    r"cancer\s+letters?|cancer\s+lett|mol\s+cancer|jama|esmo)\b",
    re.I,
)


def _looks_like_reference_container_part(part):
    part = str(part or "").strip()
    if not REFERENCE_CONTAINER_WORD_RE.search(part):
        return False
    normalized = _normalize_title(part)
    known_short = {
        "ca cancer jclin",
        "nat commun",
        "mol cancer",
        "cancer lett",
        "cancer letters",
        "jama",
        "the lancet",
        "thyroid",
        "cancers basel",
        "esmo open",
    }
    if normalized in known_short:
        return True
    if len(_title_tokens(part)) > 6:
        return False
    return bool(re.search(
        r"\b(?:vol\.?|volume)\b|\b\d+\s*,|\b\d+\s+\d+|\(\d{4}\)|\b\d{1,5}\s*[-–]\s*\d{1,5}\b",
        part,
        re.I,
    ))


def _looks_like_reference_author_fragment(part):
    part = str(part or "").strip()
    if not part:
        return False
    if re.fullmatch(r"(?:[A-Z]\.?){1,4}", part):
        return True
    if re.search(r"\bet\s+al\b", part, re.I):
        return True
    if re.search(r"(?:^|[\s,&])(?:[A-Z]\.){1,3}(?:,|\s|$)", part):
        return True
    if re.search(r"\b[A-Z][A-Za-z'’-]+,\s*[A-Z](?:\.|$)", part):
        return True
    return False


def _name_tokens(value):
    return {
        token
        for token in re.findall(r"[a-z\u4e00-\u9fff]+", _normalize_title(value))
        if len(token) >= 3
    }


def _author_similarity(query_author, match_authors):
    left = _name_tokens(query_author)
    if not left:
        return 0.0
    right = set()
    for author in match_authors or []:
        right.update(_name_tokens(author))
    if not right:
        return 0.0
    return len(left & right) / max(len(left), 1)


def _reference_year(ref):
    if isinstance(ref, dict):
        value = ref.get("year") or ref.get("publication_year") or ""
    else:
        value = str(ref or "")
    match = re.search(r"\b(19|20)\d{2}\b", str(value))
    return match.group(0) if match else ""


def extract_reference_year_hint(text):
    text = str(text or "")
    parenthetical = re.findall(r"\(((?:19|20)\d{2})\)", text)
    if parenthetical:
        return parenthetical[-1]
    years = re.findall(r"\b((?:19|20)\d{2})\b", text)
    return years[-1] if years else ""


def extract_reference_author_hint(text):
    text = re.sub(r"^(?:\[\d+\]|\d+\.|\(\d+\))\s*", "", str(text or "")).strip()
    before_year = re.split(r"\b(?:19|20)\d{2}\b", text, maxsplit=1)[0]
    before_title = before_year.split(".")[0] if "." in before_year else before_year
    names = re.findall(r"\b[A-Z][A-Za-z'’-]{2,}\b", before_title)
    return " ".join(names[:3])


def extract_reference_container_hint(text):
    text = re.sub(r"^(?:\[\d+\]|\d+\.|\(\d+\))\s*", "", str(text or "")).strip()
    text = re.sub(r"https?://\S+", "", text, flags=re.I)
    parts = [p.strip(" .;:") for p in re.split(r"\.\s+", text) if p.strip(" .;:")]
    for part in parts:
        if _looks_like_reference_author_fragment(part):
            continue
        if len(_title_tokens(part)) > 8:
            continue
        if _looks_like_reference_container_part(part):
            container = re.split(r"\b(?:vol\.?|volume|\d+\s*,|\d+\s+\d|\(\d{4}\))", part, maxsplit=1, flags=re.I)[0]
            return container.strip(" .;:")[:160]
    return ""


def extract_reference_title(text):
    text = re.sub(r"^(?:\[\d+\]|\d+\.|\(\d+\))\s*", "", str(text or "")).strip()
    text = re.sub(r"\bdoi\s*[:：]?\s*10\.\S+", "", text, flags=re.I).strip()
    text = re.sub(r"https?://\S+", "", text, flags=re.I).strip()
    parts = [p.strip(" .;:") for p in re.split(r"\.\s+", text) if p.strip(" .;:")]
    if not parts:
        return _brief_text(text, 160)
    candidates = []
    for part in parts:
        if _looks_like_reference_author_fragment(part):
            continue
        if _looks_like_reference_container_part(part):
            continue
        if len(_title_tokens(part)) >= 2:
            candidates.append(part)
    if candidates:
        return candidates[0][:360]
    return parts[min(1, len(parts) - 1)][:360]


def build_reference_query(ref):
    title = ref.get("title_hint") or extract_reference_title(ref.get("text", ""))
    author = ref.get("author_hint") or extract_reference_author_hint(ref.get("text", ""))
    year = _reference_year(ref)
    doi = _normalize_doi(ref.get("doi", ""))
    container = ref.get("container_hint") or extract_reference_container_hint(ref.get("text", ""))
    query_parts = [p for p in (title, author, year, container) if p]
    bibliographic = " ".join(query_parts) or ref.get("text", "")[:240]
    if not doi and ref.get("text"):
        bibliographic = ref.get("text", "")[:600]
    return {
        "doi": doi,
        "title": title,
        "author": author,
        "container": container,
        "year": year,
        "bibliographic": bibliographic,
    }


def reference_cache_key(ref):
    query = build_reference_query(ref)
    if query.get("doi"):
        return "doi:" + query["doi"]
    key = f"{_normalize_title(query.get('title'))}|{query.get('year', '')}"
    return "title:" + hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _crossref_work_to_match(work):
    title = " ".join(work.get("title") or []).strip()
    year = ""
    for key in ("published-print", "published-online", "published", "created"):
        parts = ((work.get(key) or {}).get("date-parts") or [[]])[0]
        if parts:
            year = str(parts[0])
            break
    authors = []
    for author in work.get("author") or []:
        name = " ".join(p for p in (author.get("given"), author.get("family")) if p)
        if name:
            authors.append(name)
    container = " ".join(work.get("container-title") or work.get("short-container-title") or [])
    return {
        "source": "Crossref",
        "title": title,
        "year": year,
        "doi": _normalize_doi(work.get("DOI", "")),
        "authors": authors[:5],
        "container": container,
        "url": work.get("URL", ""),
        "retracted": bool(work.get("relation", {}).get("is-retracted-by")),
    }


def _openalex_work_to_match(work):
    title = work.get("display_name") or work.get("title") or ""
    authors = []
    for authorship in work.get("authorships") or []:
        name = ((authorship.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    return {
        "source": "OpenAlex",
        "title": title,
        "year": str(work.get("publication_year") or ""),
        "doi": _normalize_doi(work.get("doi", "")),
        "authors": authors[:5],
        "container": source.get("display_name", ""),
        "url": work.get("doi") or work.get("id") or "",
        "retracted": bool(work.get("is_retracted")),
    }


def _pubmed_summary_to_match(uid, item):
    title = item.get("title") or ""
    authors = []
    for author in item.get("authors") or []:
        name = (author.get("name") or "").strip()
        if name:
            authors.append(name)
    pubdate = item.get("pubdate") or ""
    year = _reference_year(pubdate)
    doi = ""
    for article_id in item.get("articleids") or []:
        if str(article_id.get("idtype", "")).lower() == "doi":
            doi = _normalize_doi(article_id.get("value", ""))
            break
    return {
        "source": "PubMed",
        "title": title,
        "year": year,
        "doi": doi,
        "authors": authors[:5],
        "container": item.get("fulljournalname") or item.get("source") or "",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        "retracted": "retracted publication" in " ".join(item.get("pubtype") or []).lower(),
    }


REFERENCE_OFFICIAL_SITE_RULES = [
    (("ca cancer", "international journal of cancer"), "Wiley Online Library", "https://onlinelibrary.wiley.com/action/doSearch?AllField={query}"),
    (("thyroid",), "Mary Ann Liebert", "https://www.liebertpub.com/action/doSearch?AllField={query}"),
    (("nature reviews", "nat commun", "nature communications"), "Nature", "https://www.nature.com/search?q={query}"),
    (("current opinion in oncology", "lww",), "LWW Journals", "https://journals.lww.com/pages/results.aspx?txtKeywords={query}"),
    (("journal of clinical endocrinology", "endocrinology and metabolism"), "Oxford Academic", "https://academic.oup.com/search-results?page=1&q={query}"),
    (("annals of oncology", "esmo open"), "Elsevier ClinicalKey", "https://www.annalsofoncology.org/action/doSearch?AllField={query}"),
    (("lancet",), "The Lancet", "https://www.thelancet.com/action/doSearch?AllField={query}"),
    (("cancers basel", "mdpi",), "MDPI", "https://www.mdpi.com/search?q={query}"),
    (("proceedings of the national academy", "pnas"), "PNAS", "https://www.pnas.org/action/doSearch?AllField={query}"),
    (("mol cancer", "molecular cancer"), "BMC Molecular Cancer", "https://molecular-cancer.biomedcentral.com/search?query={query}"),
    (("jama",), "JAMA Network", "https://jamanetwork.com/searchresults?q={query}"),
    (("endocrine", "hashimoto", "papillary thyroid carcinoma"), "Springer Link", "https://link.springer.com/search?query={query}"),
    (("kolmogorov arnold networks", "arxiv"), "arXiv", "https://arxiv.org/search/?query={query}&searchtype=all&source=header"),
]


def _html_to_searchable_text(content):
    raw = content.decode("utf-8", errors="replace") if isinstance(content, (bytes, bytearray)) else str(content or "")
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _html_title(content):
    raw = content.decode("utf-8", errors="replace") if isinstance(content, (bytes, bytearray)) else str(content or "")
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    if not match:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))).strip()


def _official_page_matches_reference(ref, page_text):
    query = build_reference_query(ref)
    title_tokens = _title_tokens(query.get("title") or "")
    page_tokens = _title_tokens(page_text)
    if not title_tokens or not page_tokens:
        return False
    coverage = len(title_tokens & page_tokens) / max(len(title_tokens), 1)
    year = query.get("year")
    if not year:
        return coverage >= 0.82
    years = {_reference_year(token) for token in re.findall(r"\b(?:19|20)\d{2}\b", page_text)}
    years.discard("")
    year_ok = year in years or any(abs(int(year) - int(item)) <= 1 for item in years)
    return (coverage >= 0.72 and year_ok) or coverage >= 0.9


def _official_site_search_urls(ref):
    query = build_reference_query(ref)
    probe = _normalize_title(" ".join([
        query.get("container", ""),
        query.get("title", ""),
        ref.get("text", ""),
    ]))
    title = query.get("title") or ""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", title)
    search_terms = [title or query.get("bibliographic") or ref.get("text", "")[:180]]
    if len(words) >= 7:
        # OCR can damage the first word of a title; retry with the distinctive
        # title tail before declaring that the publisher site cannot find it.
        search_terms.append(" ".join(words[1:]))
    if len(words) >= 11:
        distinctive = [word for word in words if len(word) >= 4][:12]
        if len(distinctive) >= 4:
            search_terms.append(" ".join(distinctive))
    seen = set()
    urls = []
    for needles, label, template in REFERENCE_OFFICIAL_SITE_RULES:
        if any(needle in probe for needle in needles):
            for term in search_terms:
                search = urllib.parse.quote(term)
                url = template.format(query=search)
                if url not in seen:
                    urls.append((label, url))
                    seen.add(url)
    return urls


def _score_reference_match(ref, match):
    query = build_reference_query(ref)
    problems = []
    score = 0.0
    ref_doi = query.get("doi")
    match_doi = _normalize_doi(match.get("doi", ""))
    title_sim = max(
        _token_similarity(query.get("title") or "", match.get("title", "")),
        _token_similarity(ref.get("text", ""), match.get("title", "")),
    )
    author_sim = _author_similarity(query.get("author"), match.get("authors") or [])
    container_sim = _token_similarity(query.get("container") or "", match.get("container", ""))
    if ref_doi:
        if match_doi and ref_doi == match_doi:
            score += 0.72
        elif match_doi:
            problems.append("doi_mismatch")
            score -= 0.2
        else:
            problems.append("doi_missing_in_source")
        score += min(title_sim, 1.0) * 0.18
        score += min(author_sim, 1.0) * 0.04
    else:
        score += min(title_sim, 1.0) * 0.62
        score += min(author_sim, 1.0) * 0.14
        score += min(container_sim, 1.0) * 0.08
    if title_sim < 0.45 and not ref_doi:
        problems.append("title_low_similarity")
    ref_year = query.get("year")
    match_year = _reference_year(match.get("year", ""))
    if ref_year and match_year:
        if ref_year == match_year:
            score += 0.06 if ref_doi else 0.16
        elif abs(int(ref_year) - int(match_year)) <= 1:
            score += 0.03 if ref_doi else 0.08
            problems.append("year_near_mismatch")
        else:
            problems.append("year_mismatch")
            score -= 0.1
    elif ref_year and not match_year:
        problems.append("year_missing_in_source")
    if (
        not ref_doi
        and match_doi
        and ref_year
        and match_year
        and (ref_year == match_year or abs(int(ref_year) - int(match_year)) <= 1)
        and title_sim >= 0.78
    ):
        score = max(score, 0.93)
    if match.get("source") == "DOI landing page" and ref_doi and ref_doi == match_doi:
        score = max(score, 0.95)
    if match.get("official_site") and title_sim >= 0.82 and (not ref_year or not match_year or abs(int(ref_year) - int(match_year)) <= 1):
        score = max(score, 0.94)
    if match.get("retracted"):
        problems.append("source_marks_retracted")
    return max(0.0, min(1.0, score)), problems


def _score_reference_matches(ref, raw_matches):
    scored = []
    for match in raw_matches:
        score, problems = _score_reference_match(ref, match)
        enriched = dict(match)
        enriched["match_score"] = round(score, 3)
        enriched["_match_problems"] = problems
        scored.append(enriched)
    scored.sort(key=lambda m: m.get("match_score", 0), reverse=True)
    return scored
