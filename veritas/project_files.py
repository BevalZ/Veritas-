"""Project file discovery and run metadata helpers."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .runtime_metadata import ensure_runtime_meta
from .versions import ADAPTER_VERSION, PROMPT_VERSION, RISK_RULE_VERSION, SCHEMA_VERSION

SUPPORTED_TEXT_FILE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".txt", ".md"}


def find_project_files(root_path: Path) -> Tuple[Dict, List[Path]]:
    """Scan a paper project directory and classify supported input files."""
    supplement_keywords = {"supplement", "supp", "补充材料", "原始数据", "data", "source", "appendix"}
    reference_keywords = {"reference", "references", "bibliography", "参考文献", "参考资料"}
    generated_markers = (
        ".audit.",
        ".limited.",
        ".failed.",
        "audit_report.",
        "reference_audit_full.",
        ".paper_audit.",
        ".mineru.",
        ".mineru_",
    )

    file_categories = {
        "main_paper": None,
        "supplements": [],
        "data_files": [],
        "references": [],
        "other": [],
    }
    all_files = []

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if ".paper_audit_resume" not in d and "__pycache__" not in d]
        dirs.sort()
        for file in sorted(files):
            fpath = Path(root) / file
            ext = fpath.suffix.lower()
            if ext not in SUPPORTED_TEXT_FILE_EXTENSIONS:
                continue
            lower_name = fpath.name.lower()
            if any(marker in lower_name for marker in generated_markers):
                continue

            fname = lower_name
            all_files.append(fpath)

            if ext != ".pdf" and any(keyword in fname for keyword in reference_keywords):
                file_categories["references"].append(fpath)
            elif ext == ".pdf" and (
                file_categories["main_paper"] is None
                or _main_paper_score(fpath) > _main_paper_score(file_categories["main_paper"])
            ):
                file_categories["main_paper"] = fpath
            elif any(keyword in fname for keyword in supplement_keywords):
                file_categories["supplements"].append(fpath)
            elif ext in {".xlsx", ".xlsm", ".csv"}:
                file_categories["data_files"].append(fpath)
            else:
                file_categories["other"].append(fpath)

    pdf_files = [file for file in all_files if file.suffix.lower() == ".pdf"]
    if file_categories["main_paper"] is None and pdf_files:
        file_categories["main_paper"] = max(pdf_files, key=_main_paper_score)

    for pdf in pdf_files:
        if pdf == file_categories["main_paper"]:
            continue
        if pdf not in file_categories["supplements"] and pdf not in file_categories["other"]:
            file_categories["other"].append(pdf)

    return file_categories, all_files


def _main_paper_score(path: Path):
    stem = path.stem.lower()
    score = 0
    try:
        score += min(path.stat().st_size / 1024 / 1024, 20)
    except Exception:
        pass
    if any(token in stem for token in ("article", "paper", "main", "manuscript")):
        score += 12
    if re.search(r"(?:^|[_\-.])s(?:upp)?\d{1,3}(?:$|[_\-.])|supp|supplement|moesm|esm|appendix|附录|补充", stem):
        score -= 25
    if "reference" in stem or "references" in stem:
        score -= 2
    if re.search(r"\b(?:doi|s?10\.|s\d{5})", stem):
        score += 1
    return score


def _is_missing_meta_value(value):
    return value is None or value == "" or value == "N/A"


def optional_dependency_for_extension_from_namespace(namespace, ext: str):
    ext = str(ext or "").lower()
    docx_supported = bool((namespace or {}).get("DOCX_SUPPORTED", False))
    excel_supported = bool((namespace or {}).get("EXCEL_SUPPORTED", False))
    if ext == ".docx" and not docx_supported:
        return "python-docx", "python3 -m pip install python-docx"
    if ext in {".xlsx", ".xlsm"} and not excel_supported:
        return "openpyxl", "python3 -m pip install openpyxl"
    return None, None


def extracted_body_text(file_content: str, file_name: str = "") -> str:
    text = str(file_content or "").strip()
    if file_name:
        text = re.sub(rf"^=+\s*文件:\s*{re.escape(str(file_name))}\s*=+\s*", "", text).strip()
    text = re.sub(r"^\s*=+\s*文件:.*?=+\s*", "", text, count=1).strip()
    return text


def normalize_run_meta(meta, input_path=None, full_text=None):
    """Fill display/report metadata that may be missing from older resume caches."""
    normalized = ensure_runtime_meta(meta)
    normalized.setdefault("prompt_version", PROMPT_VERSION)
    normalized.setdefault("schema_version", SCHEMA_VERSION)
    normalized.setdefault("adapter_version", ADAPTER_VERSION)
    normalized.setdefault("risk_rule_version", RISK_RULE_VERSION)
    if full_text is not None and _is_missing_meta_value(normalized.get("total_chars")):
        normalized["total_chars"] = len(full_text or "")

    if input_path is None:
        return normalized

    try:
        path = Path(input_path)
    except TypeError:
        return normalized
    if not path.exists():
        return normalized

    if path.is_dir():
        normalized.setdefault("input_type", "directory")
        if _is_missing_meta_value(normalized.get("extractor")):
            normalized["extractor"] = "directory_multi_format"
        if _is_missing_meta_value(normalized.get("extraction_method")):
            normalized["extraction_method"] = normalized.get("extractor") or "directory_multi_format"
        need_size = _is_missing_meta_value(normalized.get("size_mb"))
        need_count = _is_missing_meta_value(normalized.get("total_files"))
        if need_size or need_count:
            try:
                _, all_files = find_project_files(path)
                if need_size:
                    normalized["size_mb"] = round(sum(p.stat().st_size for p in all_files if p.exists()) / 1024 / 1024, 2)
                if need_count:
                    normalized["total_files"] = len(all_files)
            except Exception:
                pass
    else:
        if _is_missing_meta_value(normalized.get("size_mb")):
            normalized["size_mb"] = round(path.stat().st_size / 1024 / 1024, 2)
        if _is_missing_meta_value(normalized.get("extraction_method")):
            normalized["extraction_method"] = (
                normalized.get("source")
                or normalized.get("extractor")
                or f"{path.suffix.lower().lstrip('.') or 'file'}_text"
            )

    return normalized


__all__ = [
    "SUPPORTED_TEXT_FILE_EXTENSIONS",
    "optional_dependency_for_extension_from_namespace",
    "extracted_body_text",
    "find_project_files",
    "_main_paper_score",
    "_is_missing_meta_value",
    "normalize_run_meta",
]
