"""Fraud-pattern knowledge-base update helpers."""

import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

__all__ = ["update_patterns_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def _extract_pattern_json_array(content, json_module=json, re_module=re):
    json_match = re_module.search(r"\[[\s\S]*\]", content)
    if not json_match:
        return None, "missing_json"
    try:
        return json_module.loads(json_match.group()), None
    except json_module.JSONDecodeError as error:
        return None, error


def update_patterns_from_namespace(namespace, comments_file):
    """Extract fraud patterns from PubPeer comments and update the local KB."""
    path_cls = _namespace_value(namespace, "Path", Path)
    json_module = _namespace_value(namespace, "json", json)
    re_module = _namespace_value(namespace, "re", re)
    urllib_module = _namespace_value(namespace, "urllib")
    urllib_request = getattr(urllib_module, "request", urllib.request)
    patterns_path = path_cls(_namespace_value(namespace, "FRAUD_PATTERNS_PATH", path_cls("fraud_patterns.json")))

    comments_path = path_cls(comments_file)
    if not comments_path.exists():
        print(f"❌ 评论文本文件不存在: {comments_path}")
        return 1

    with open(comments_path, "r", encoding="utf-8") as f:
        comments_text = f.read()

    if len(comments_text.strip()) < 20:
        print("❌ 评论文本内容过少，请提供更完整的PubPeer评论内容")
        return 1

    print(f"📖 已读取评论文本: {len(comments_text)}字符")
    print("🤖 正在用LLM分析评论，提取欺诈模式...")

    extract_prompt = f"""分析以下来自PubPeer的学术评论，提取其中涉及的学术论文造假/可疑手法。

要求：
1. 每个造假手法提取为一个独立的模式条目
2. 按JSON数组格式输出，每个条目包含：id(英文大写下划线), category(分类), name(中文名), description(详细描述), detection_hint(检测提示), risk_level(高/中/低)
3. 只提取确实存在的造假手法，不要臆造
4. 合并相似的造假手法

PubPeer评论内容：
{comments_text}

输出格式：
[
  {{
    "id": "PATTERN_ID",
    "category": "图片与图表/数据与结果/方法论/结构与引用/作者与期刊",
    "name": "手法名称",
    "description": "手法描述",
    "detection_hint": "审查时如何检测此手法",
    "risk_level": "高/中/低"
  }}
]"""

    payload = {
        "model": _namespace_value(namespace, "LLM_MODEL", ""),
        "messages": [
            {"role": "system", "content": "你是一个学术论文打假专家，擅长从PubPeer评论中识别和归纳造假手法。"},
            {"role": "user", "content": extract_prompt},
        ],
        "temperature": 0.3,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_namespace_value(namespace, 'LLM_API_KEY', '')}",
    }

    req = urllib_request.Request(
        _namespace_value(namespace, "LLM_API_URL", ""),
        data=json_module.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )

    try:
        resp = urllib_request.urlopen(req, timeout=60)
        result = json_module.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ LLM调用失败: {e}")
        return 1

    new_patterns, parse_error = _extract_pattern_json_array(content, json_module, re_module)
    if parse_error == "missing_json":
        print("❌ LLM未能输出有效的JSON格式，请重试")
        print(f"原始输出: {content[:500]}")
        return 1
    if parse_error:
        print(f"❌ JSON解析失败: {parse_error}")
        return 1

    if not new_patterns:
        print("⚠️ 未能从评论中提取到新的欺诈模式")
        return 0

    if patterns_path.exists():
        with open(patterns_path, "r", encoding="utf-8") as f:
            kb_data = json_module.load(f)
        existing_ids = {p["id"] for p in kb_data.get("patterns", [])}
    else:
        kb_data = {"schema_version": "1.0", "last_updated": "", "contributors": ["community"], "patterns": []}
        existing_ids = set()

    added = 0
    for pattern in new_patterns:
        if pattern.get("id") and pattern["id"] not in existing_ids:
            kb_data["patterns"].append(pattern)
            existing_ids.add(pattern["id"])
            added += 1
            print(f"  ✅ 新增: [{pattern.get('risk_level','?')}] {pattern.get('name','?')}")
        else:
            print(f"  ⏭️ 跳过已存在: {pattern.get('name','?')} ({pattern.get('id','?')})")

    if added > 0:
        kb_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        with open(patterns_path, "w", encoding="utf-8") as f:
            json_module.dump(kb_data, f, ensure_ascii=False, indent=2)
        print(f"\n🎉 知识库已更新！新增{added}条模式，总计{len(kb_data['patterns'])}条")
    else:
        print("\n⚠️ 无新增模式，知识库未变更")

    return 0
