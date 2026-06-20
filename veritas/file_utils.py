"""Shared filesystem and JSON helpers for audit runtime artifacts."""

import json
import re
from pathlib import Path


def _safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name)).strip(" .") or "paper_audit"


def _json_load(path: Path, default=None):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️ 读取缓存失败 {path}: {e}")
    return default


def _json_save(path: Path, data):
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"⚠️ 写入缓存失败 {path}: {e}")


def _load_merged_json_dicts(*paths: Path):
    merged = {}
    for path in paths:
        data = _json_load(path, {})
        if isinstance(data, dict):
            merged.update(data)
    return merged


__all__ = [
    "_safe_name",
    "_json_load",
    "_json_save",
    "_load_merged_json_dicts",
]
