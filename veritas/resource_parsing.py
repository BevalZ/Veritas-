"""Resource URL extraction and classification helpers."""

import html
import re
import urllib.parse

from .text_utils import _brief_text

__all__ = [
    "extract_paper_resources",
    "_clean_resource_url",
    "_resource_context",
    "_classify_resource",
]


def extract_paper_resources(text):
    """Extract code repositories and deployed online resources mentioned by the paper text."""
    raw_text = str(text or "")
    resources = []
    seen = set()
    url_pattern = re.compile(r"\b(?:https?|htps)://[^\s<>'\"\]\)）}]+", re.I)
    for match in url_pattern.finditer(raw_text):
        raw_url = _clean_resource_url(match.group(0))
        if not raw_url:
            continue
        start, end = match.span()
        context = _resource_context(raw_text, start, end)
        resource_type = _classify_resource(raw_url, context)
        if resource_type == "other":
            continue
        key = raw_url.lower()
        if key in seen:
            continue
        seen.add(key)
        resources.append({
            "url": raw_url,
            "type": resource_type,
            "context": context,
        })
    return resources


def _clean_resource_url(url):
    url = html.unescape(str(url or "")).strip()
    url = url.replace("\\_", "_")
    url = re.sub(r"[`*_]+$", "", url)
    url = url.rstrip(".,;:，。；：")
    while url.endswith((")", "）", "]", "}")) and url.count("(") < url.count(")"):
        url = url[:-1].rstrip()
    return url


def _resource_context(text, start, end, radius=180):
    snippet = str(text or "")[max(0, start - radius):min(len(text), end + radius)]
    snippet = re.sub(r"\[\[/?(?:BLOCK|FIGURE|TABLE_START|TABLE_END|TABLE_CONTINUATION|EXTRACTION_NOTE)[^\]]*\]\]", " ", snippet, flags=re.I)
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return _brief_text(snippet, 420)


def _classify_resource(url, context=""):
    lowered = (str(url or "") + " " + str(context or "")).lower()
    host = urllib.parse.urlparse(url if not url.lower().startswith("htps://") else "https://" + url[7:]).netloc.lower()
    if any(domain in host for domain in ("github.com", "gitlab.com", "bitbucket.org")):
        return "code_repository"
    if any(domain in host for domain in ("zenodo.org", "figshare.com", "osf.io", "ncbi.nlm.nih.gov", "portal.gdc.cancer.gov")):
        return "data_repository"
    if any(domain in host for domain in (
        "streamlit.app", "huggingface.co", "shinyapps.io", "herokuapp.com",
        "vercel.app", "netlify.app", "github.io",
    )):
        return "deployed_resource"
    if re.search(r"\b(code availability|code available|source code|github|repository|repo)\b", lowered):
        return "code_repository"
    if re.search(r"\b(streamlit|web calculator|web-based calculator|online platform|online predictive|publicly accessible|deployed)\b", lowered):
        return "deployed_resource"
    return "other"
