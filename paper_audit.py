#!/usr/bin/env python3
"""Paper Audit - 学术论文自动审查工具 [耿同学版]
基于3个开源项目思路开发：
- wooly99/geng-academic-fraud-detector 耿同学六式
- NeoSpecies/AcademicIntegrityHunter 本地统计算法
- jingshouyan/academic-integrity-geng 五维审查体系
输入PDF路径 → MinerU转Markdown → 本地统计检测 + LLM语义分析 → 输出md格式报告
用法: python paper_audit.py <pdf_path> [--mineru] [--max-chars 8000] [--output report.md]
"""
import re, json, time, argparse, urllib.request, zlib, math, collections, os, mimetypes
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# 配置区
# ══════════════════════════════════════════════════════════════
import importlib

# 尝试加载外部配置文件（优先config.py）
try:
    config = importlib.import_module("config")
    LLM_API_KEY = getattr(config, "LLM_API_KEY", "")
    LLM_API_URL = getattr(config, "LLM_API_URL", "https://fufu.iqach.top/v1/chat/completions")
    LLM_MODEL = getattr(config, "LLM_MODEL", "mimo-v2.5-pro")
    MINERU_TOKEN = getattr(config, "MINERU_TOKEN", "")
except ImportError:
    # 未找到config.py使用空值，会自动降级到可用功能
    LLM_API_KEY = ""
    LLM_API_URL = "https://fufu.iqach.top/v1/chat/completions"
    LLM_MODEL = "mimo-v2.5-pro"
    MINERU_TOKEN = ""

MINERU_BASE = "https://mineru.net"

# ══════════════════════════════════════════════════════════════
# 审查体系配置 - LLM System Prompt
# ══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是一个严厉的学术论文审查专家（耿同学标准）。
你需要结合以下维度对输入的论文文本进行审查，输出严格的JSON格式：

## 审查维度
1. 数据与结果自洽性 — 数字前后矛盾、统计量不一致、图表数据不匹配
2. 图片与图表异常 — 描述性分析图片可疑特征（旋转复用、背景一致、拼接痕迹）
3. 方法论严谨性 — 样本量不足、缺乏多重比较校正、实验设计缺陷
4. 结构与引用规范性 — 自引率异常、引用质量差、逻辑谬误
5. 作者与期刊可信度 — 产出异常、利益冲突未披露、同行评审缺失

## 检查项（耿同学六式 + 7类红旗）
- 耿同学六式：图片复用/数据造假/图片拼接/统计异常/产出异常/方法矛盾
- 7类红旗：引用质量差/逻辑谬误/方法论缺陷/可疑结论/同行评审缺失/利益冲突未披露/语言质量差

请按以下JSON格式输出（确保JSON合法，无多余内容）：
{
  "summary": "一句话总评",
  "risk_level": "高/中/低/可疑黑产",
  "detection_score": 0,
  "checks": [
    {
      "category": "数据与结果/图片与图表/方法论/结构与引用/作者与期刊",
      "item": "检查项名称",
      "verdict": "🚩红旗/⚠️疑点/✅通过",
      "evidence": "具体证据，引用原文片段",
      "detail": "详细分析说明"
    }
  ],
  "conclusion": "综合结论与行动建议"
}"""

# ══════════════════════════════════════════════════════════════
# MinerU API 模块 — PDF转Markdown
# ══════════════════════════════════════════════════════════════

def _http_request(url, method="GET", headers=None, data=None, timeout=60):
    """通用HTTP请求封装（纯标准库）"""
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.status


def mineru_precision_extract_by_url(pdf_url, model_version="vlm", language="ch",
                                     poll_interval=10, poll_timeout=600):
    """🎯 Precision API — 通过URL解析PDF（需要Token，≤200MB/200页）

    流程：POST创建任务 → GET轮询结果 → 下载zip中的Markdown
    返回：(markdown_text, meta_dict) 或 (None, error_dict)
    """
    print(f"  🎯 [MinerU Precision] 提交URL任务: {pdf_url[:80]}...")

    # 1. 创建提取任务
    create_url = f"{MINERU_BASE}/api/v4/extract/task"
    payload = json.dumps({"url": pdf_url, "model_version": model_version}).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_TOKEN}"
    }
    try:
        resp_data, status = _http_request(create_url, "POST", headers, payload, timeout=30)
        result = json.loads(resp_data.decode())
    except Exception as e:
        return None, {"error": f"创建任务失败: {e}"}

    if result.get("code") != 0 and not result.get("data", {}).get("batch_id"):
        return None, {"error": f"创建任务返回异常: {result}"}

    batch_id = result.get("data", {}).get("batch_id")
    if not batch_id:
        return None, {"error": f"未获取到batch_id: {result}"}
    print(f"  ✅ 任务已创建: batch_id={batch_id}")

    # 2. 轮询任务状态
    poll_url = f"{MINERU_BASE}/api/v4/extract/task/{batch_id}"
    start = time.time()
    state_labels = {"processing": "处理中", "queued": "排队中"}

    while time.time() - start < poll_timeout:
        try:
            resp_data, _ = _http_request(poll_url, "GET", headers, timeout=30)
            result = json.loads(resp_data.decode())
        except Exception as e:
            print(f"  ⚠️ 轮询异常: {e}")
            time.sleep(poll_interval)
            continue

        task_list = result.get("data", {}).get("task_list", [])
        if not task_list:
            # 单文件模式
            state = result.get("data", {}).get("state", "unknown")
        else:
            state = task_list[0].get("state", "unknown")

        elapsed = int(time.time() - start)

        if state == "done":
            # 获取zip下载链接
            zip_url = task_list[0].get("zip_url") if task_list else result.get("data", {}).get("zip_url")
            if not zip_url:
                return None, {"error": "任务完成但未获取到下载链接"}

            print(f"  ✅ [{elapsed}s] 解析完成，下载Markdown...")
            markdown = _download_zip_and_extract_md(zip_url)
            if markdown:
                meta = {"source": "mineru_precision", "batch_id": batch_id,
                        "model": model_version, "chars": len(markdown)}
                return markdown, meta
            else:
                return None, {"error": "下载或解压zip失败"}

        elif state == "failed":
            err = task_list[0].get("err_msg", "未知") if task_list else "未知"
            return None, {"error": f"任务失败: {err}"}

        label = state_labels.get(state, state)
        print(f"  ⏳ [{elapsed}s] {label}...")
        time.sleep(poll_interval)

    return None, {"error": f"轮询超时({poll_timeout}s), batch_id={batch_id}"}


def mineru_agent_extract_by_file(file_path, language="ch",
                                  poll_interval=5, poll_timeout=300):
    """⚡ Agent API — 上传本地文件解析（无需Token，IP限流≤10MB/20页）

    流程：POST上传文件 → 轮询 → 下载Markdown
    返回：(markdown_text, meta_dict) 或 (None, error_dict)
    """
    file_path = Path(file_path)
    file_size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"  ⚡ [MinerU Agent] 上传文件: {file_path.name} ({file_size_mb:.1f}MB)")

    if file_size_mb > 10:
        print(f"  ⚠️ 文件>{10}MB，Agent API不支持，自动切换Precision API...")
        return mineru_precision_extract_by_file(file_path, language=language)

    # 1. 上传文件到 Agent API
    upload_url = f"{MINERU_BASE}/api/v1/agent/parse/file"

    # 构建 multipart/form-data
    boundary = f"----PaperAudit{int(time.time()*1000)}"
    filename = file_path.name
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/pdf"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body_parts = []
    # language 字段
    body_parts.append(f"--{boundary}\r\n"
                      f"Content-Disposition: form-data; name=\"language\"\r\n\r\n"
                      f"{language}".encode())
    # file 字段
    body_parts.append(f"--{boundary}\r\n"
                      f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                      f"Content-Type: {mime_type}\r\n\r\n".encode())
    body_parts.append(file_bytes)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(body_parts)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    try:
        resp_data, status = _http_request(upload_url, "POST", headers, body, timeout=120)
        result = json.loads(resp_data.decode())
    except Exception as e:
        return None, {"error": f"Agent上传失败: {e}"}

    if result.get("code") != 0 and not result.get("data", {}).get("task_id"):
        return None, {"error": f"Agent上传返回异常: {result}"}

    task_id = result.get("data", {}).get("task_id")
    if not task_id:
        return None, {"error": f"未获取到task_id: {result}"}
    print(f"  ✅ 上传成功: task_id={task_id}")

    # 2. 轮询任务状态
    return _mineru_agent_poll(task_id, poll_interval, poll_timeout)


def mineru_precision_extract_by_file(file_path, model_version="vlm", language="ch",
                                     poll_interval=10, poll_timeout=600):
    """🎯 Precision API — 上传本地文件解析（需要Token，≤200MB/200页）

    先上传文件获取URL，再创建提取任务。适用于大文件。
    """
    file_path = Path(file_path)
    file_size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"  🎯 [MinerU Precision] 上传文件: {file_path.name} ({file_size_mb:.1f}MB)")

    # 方案：通过 Agent API 的 /file 端点获取文件URL，再用 Precision API 处理
    # 更简洁：直接使用 Agent file upload → 拿到文件URL → Precision 创建任务
    # 但实际上 Precision API 需要一个可访问的 URL

    # 退而求其次：如果文件 ≤ 10MB，用 Agent API；否则尝试用 file-urls 端点
    # Precision API 还有一个 /api/v4/file-urls/batch 端点用于上传本地文件
    # 这里我们用最通用的方式：先获取上传凭证，上传文件，再创建任务

    # 1. 获取文件上传凭证
    batch_url = f"{MINERU_BASE}/api/v4/file-urls/batch"
    payload = json.dumps({"file_names": [file_path.name]}).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_TOKEN}"
    }

    try:
        resp_data, _ = _http_request(batch_url, "POST", headers, payload, timeout=30)
        result = json.loads(resp_data.decode())
    except Exception as e:
        return None, {"error": f"获取上传凭证失败: {e}"}

    batch_data = result.get("data", {})
    batch_id = batch_data.get("batch_id")
    file_urls = batch_data.get("file_urls", [])

    if not batch_id or not file_urls:
        return None, {"error": f"上传凭证异常: {result}"}

    upload_info = file_urls[0]
    put_url = upload_info.get("upload_url") or upload_info.get("url")
    file_url = upload_info.get("url") or upload_info.get("put_url")

    # 2. PUT上传文件
    print(f"  📤 上传文件到MinerU存储...")
    with open(file_path, "rb") as f:
        file_data = f.read()

    try:
        _http_request(put_url, "PUT",
                      {"Content-Type": "application/pdf"},
                      file_data, timeout=120)
    except Exception as e:
        return None, {"error": f"PUT上传文件失败: {e}"}

    print(f"  ✅ 文件已上传，创建提取任务...")

    # 3. 创建提取任务
    # 使用已上传文件的URL（若put_url是minio的，file_url就是下载链接）
    # 尝试用 batch_id 提取
    task_url = f"{MINERU_BASE}/api/v4/extract/task"
    task_payload = json.dumps({
        "url": file_url,
        "model_version": model_version
    }).encode()
    task_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_TOKEN}"
    }

    try:
        resp_data, _ = _http_request(task_url, "POST", task_headers, task_payload, timeout=30)
        result = json.loads(resp_data.decode())
    except Exception as e:
        return None, {"error": f"创建提取任务失败: {e}"}

    extract_batch_id = result.get("data", {}).get("batch_id", batch_id)
    print(f"  ✅ 任务已创建: batch_id={extract_batch_id}")

    # 4. 轮询
    poll_url = f"{MINERU_BASE}/api/v4/extract/task/{extract_batch_id}"
    start = time.time()
    state_labels = {"processing": "处理中", "queued": "排队中"}

    while time.time() - start < poll_timeout:
        try:
            resp_data, _ = _http_request(poll_url, "GET", task_headers, timeout=30)
            result = json.loads(resp_data.decode())
        except Exception as e:
            print(f"  ⚠️ 轮询异常: {e}")
            time.sleep(poll_interval)
            continue

        task_list = result.get("data", {}).get("task_list", [])
        state = task_list[0].get("state", "unknown") if task_list else result.get("data", {}).get("state", "unknown")
        elapsed = int(time.time() - start)

        if state == "done":
            zip_url = task_list[0].get("zip_url") if task_list else result.get("data", {}).get("zip_url")
            if zip_url:
                print(f"  ✅ [{elapsed}s] 解析完成，下载Markdown...")
                markdown = _download_zip_and_extract_md(zip_url)
                if markdown:
                    return markdown, {"source": "mineru_precision_file", "batch_id": extract_batch_id,
                                      "model": model_version, "chars": len(markdown)}
            return None, {"error": "完成但未获取到下载链接"}

        elif state == "failed":
            err = task_list[0].get("err_msg", "未知") if task_list else "未知"
            return None, {"error": f"任务失败: {err}"}

        label = state_labels.get(state, state)
        print(f"  ⏳ [{elapsed}s] {label}...")
        time.sleep(poll_interval)

    return None, {"error": f"轮询超时({poll_timeout}s)"}


def _mineru_agent_poll(task_id, poll_interval=5, poll_timeout=300):
    """轮询Agent API任务状态"""
    poll_url = f"{MINERU_BASE}/api/v1/agent/parse/{task_id}"
    start = time.time()
    state_labels = {"processing": "处理中", "queued": "排队中"}

    while time.time() - start < poll_timeout:
        try:
            resp_data, _ = _http_request(poll_url, "GET", timeout=30)
            result = json.loads(resp_data.decode())
        except Exception as e:
            print(f"  ⚠️ 轮询异常: {e}")
            time.sleep(poll_interval)
            continue

        data = result.get("data", {})
        state = data.get("state", "unknown")
        elapsed = int(time.time() - start)

        if state == "done":
            markdown_url = data.get("markdown_url")
            if markdown_url:
                print(f"  ✅ [{elapsed}s] 解析完成，下载Markdown...")
                try:
                    md_data, _ = _http_request(markdown_url, "GET", timeout=30)
                    markdown = md_data.decode("utf-8", errors="ignore")
                    return markdown, {"source": "mineru_agent", "task_id": task_id,
                                      "chars": len(markdown)}
                except Exception as e:
                    return None, {"error": f"下载Markdown失败: {e}"}
            return None, {"error": "完成但未获取到markdown_url"}

        elif state == "failed":
            err = data.get("err_msg", "未知错误")
            return None, {"error": f"Agent任务失败: {err}"}

        label = state_labels.get(state, state)
        print(f"  ⏳ [{elapsed}s] {label}...")
        time.sleep(poll_interval)

    return None, {"error": f"轮询超时({poll_timeout}s), task_id={task_id}"}


def _download_zip_and_extract_md(zip_url):
    """下载zip并提取Markdown文件（纯标准库实现）"""
    try:
        zip_data, _ = _http_request(zip_url, "GET", timeout=60)
    except Exception as e:
        print(f"  ❌ 下载zip失败: {e}")
        return None

    # 用 zipfile 从内存解析
    import zipfile, io
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # 找到 .md 文件
            md_files = [n for n in zf.namelist() if n.endswith(".md")]
            if not md_files:
                # 降级：找 .txt 或其他文本
                text_files = [n for n in zf.namelist() if n.endswith((".txt", ".mdown", ".markdown"))]
                md_files = text_files
            if not md_files:
                print(f"  ⚠️ zip中未找到Markdown文件: {zf.namelist()[:10]}")
                # 尝试任何非图片文件
                for n in zf.namelist():
                    if not any(n.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".html"]):
                        try:
                            content = zf.read(n).decode("utf-8", errors="ignore")
                            if len(content) > 100:
                                return content
                        except:
                            continue
                return None

            # 读取最大的 .md 文件
            best = None
            best_len = 0
            for md_file in md_files:
                content = zf.read(md_file).decode("utf-8", errors="ignore")
                if len(content) > best_len:
                    best = content
                    best_len = len(content)
            return best
    except zipfile.BadZipFile:
        # 不是zip？尝试直接作为文本
        try:
            return zip_data.decode("utf-8", errors="ignore")
        except:
            return None


def mineru_extract(file_path, language="ch"):
    """MinerU统一入口：自动选择API路径

    - 本地文件 ≤10MB → Agent API（免Token，快速）
    - 本地文件 >10MB → Precision API（需Token，功能强）
    - URL → Precision API
    返回：(markdown_text, meta_dict) 或 (None, error_dict)
    """
    file_path = Path(file_path)
    file_size_mb = file_path.stat().st_size / 1024 / 1024

    if file_size_mb <= 10:
        return mineru_agent_extract_by_file(file_path, language=language)
    else:
        return mineru_precision_extract_by_file(file_path, language=language)


# ══════════════════════════════════════════════════════════════
# 本地统计检测模块
# ══════════════════════════════════════════════════════════════

def benford_analysis(numbers):
    """Benford定律分析：识别异常数字分布（伪造数据首位数字偏离Benford分布）"""
    if len(numbers) < 100:
        return None, "样本不足(需≥100)"
    digits = [str(abs(int(n)))[0] for n in numbers if abs(int(n)) >= 1]
    if not digits:
        return None, "无有效数字"
    counts = collections.Counter(digits)
    total = len(digits)
    expected = {str(d): math.log10(1 + 1/d) * total for d in range(1, 10)}
    deviations = {}
    for d in range(1, 10):
        d_str = str(d)
        actual = counts.get(d_str, 0)
        exp = expected[d_str]
        deviation = abs(actual - exp) / exp
        deviations[d_str] = deviation
    avg_deviation = sum(deviations.values()) / 9
    return avg_deviation, "高偏差⚠️" if avg_deviation > 0.3 else "正常✅"


def extract_all_numbers(text):
    """提取文本中所有数字（排除年份、页码等噪声）"""
    exclude = {2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027,
               1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    nums = []
    for match in re.finditer(r'\b(\d+\.?\d*)\b', text):
        try:
            n = float(match.group(1))
            if n not in exclude and n > 0:
                nums.append(n)
        except:
            pass
    return nums


def local_stat_check(text):
    """本地统计检测，无需LLM

    包含：Benford定律分析、p值异常检测、标准差异常、数字自洽性
    """
    result = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "p_value_details": [],
        "sd_count": 0,
        "sd_abnormal": 0,
        "number_count": 0,
        "number_consistency": None,
    }
    # 提取数字
    nums = extract_all_numbers(text)
    result["number_count"] = len(nums)
    # Benford分析
    if nums:
        dev, status = benford_analysis(nums)
        result["benford_deviation"] = dev
        result["benford_status"] = status
    # p值检测
    p_matches = re.findall(r'p\s*[=<]\s*(\d+\.?\d*)', text, re.IGNORECASE)
    result["p_value_count"] = len(p_matches)
    for p in p_matches:
        try:
            pv = float(p)
            if pv > 0.05:
                result["p_value_abnormal"] += 1
                result["p_value_details"].append(f"p={'<='+p if pv<=0.001 else '='+p}")
        except:
            pass
    # 标准差异常
    sd_matches = re.findall(r'(?:std|sd|标准差|SE|SEM)\s*[=:≈]\s*(\d+\.?\d*)', text, re.IGNORECASE)
    result["sd_count"] = len(sd_matches)
    # 数字自洽性检查：提取"n=XX"样本量，检查是否有矛盾
    n_matches = re.findall(r'(?:n|N|sample|样本)\s*[=:]\s*(\d+)', text, re.IGNORECASE)
    if len(set(n_matches)) > 1:
        result["number_consistency"] = f"检测到不同样本量: {set(n_matches)}"
    return result


# ══════════════════════════════════════════════════════════════
# PDF原始提取模块（MinerU不可用时的降级方案）
# ══════════════════════════════════════════════════════════════

def extract_pdf_text(filepath, max_chars=8000):
    """从PDF文件中提取文本（纯标准库实现，MinerU的降级方案）"""
    with open(filepath, "rb") as f:
        raw = f.read()
    parts = []
    for s in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL):
        try:
            dec = zlib.decompress(s)
            for x in re.findall(rb"\((.*?)\)\s*Tj", dec):
                d = x.decode("latin-1", errors="ignore")
                if len(d.strip()) > 1:
                    parts.append(d)
            for bt in re.findall(rb"BT(.*?)ET", dec, re.DOTALL):
                for x in re.findall(rb"\((.*?)\)", bt):
                    d = x.decode("latin-1", errors="ignore")
                    if len(d.strip()) > 1:
                        parts.append(d)
        except:
            pass
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    meta = {"size_mb": round(len(raw) / 1024 / 1024, 2), "total_chars": len(text),
            "extraction_method": "raw_pdf_stream"}
    return text[:max_chars], meta, raw


# ══════════════════════════════════════════════════════════════
# LLM调用模块
# ══════════════════════════════════════════════════════════════

def smart_chunk_text(text, chunk_size=8000, overlap=1000):
    """智能分块：按段落边界切割，保留重叠区确保上下文连贯

    返回: [(chunk_text, chunk_index, total_chunks), ...]
    """
    if len(text) <= chunk_size:
        return [(text, 0, 1)]

    # 按双换行分段
    paragraphs = re.split(r'\n{2,}', text)
    # 合并过短的段落
    merged_paras = []
    buf = ""
    for p in paragraphs:
        if buf and len(buf) + len(p) + 2 > chunk_size * 0.3:
            merged_paras.append(buf)
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p
    if buf:
        merged_paras.append(buf)

    # 按chunk_size组装块
    chunks = []
    current = ""
    for para in merged_paras:
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current)
            # 保留overlap：从当前块尾部取overlap长度作为下一块开头
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current)

    total = len(chunks)
    return [(c, i, total) for i, c in enumerate(chunks)]


def call_llm(text, max_retries=3, chunk_info=None):
    """调用Mimo API进行语义审查

    chunk_info: (chunk_index, total_chunks) 分块信息，None表示全文
    """
    # 构建用户消息
    if chunk_info and chunk_info[1] > 1:
        idx, total = chunk_info
        user_msg = (
            f"审查以下论文文本（第{idx+1}/{total}段，请重点关注本段内容，"
            f"同时注意与其他段落的逻辑连贯性）：\n\n{text}"
        )
    else:
        user_msg = f"审查以下论文文本：\n\n{text}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        LLM_API_URL, data=data,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8")
            result = json.loads(raw)
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < max_retries:
                time.sleep(3 * (attempt + 1))
            else:
                raise RuntimeError(f"API调用失败({attempt+1}次): {str(e)[:100]}...")


def merge_chunk_reports(reports, stat_result=None):
    """合并多块审查结果：去重、合并检查项、重新评估风险等级

    reports: [parse_report返回的dict, ...]
    """
    if len(reports) == 1:
        return reports[0]

    # 1. 收集所有检查项，按 (category, item) 去重
    seen_keys = set()
    all_checks = []
    for i, r in enumerate(reports):
        if r.get("parse_error"):
            continue
        for c in r.get("checks", []):
            key = (c.get("category", ""), c.get("item", ""))
            if key not in seen_keys:
                seen_keys.add(key)
                c["_source_chunk"] = i + 1
                all_checks.append(c)
            else:
                # 合并：如果已有同key项，补充来源信息
                for existing in all_checks:
                    ekey = (existing.get("category", ""), existing.get("item", ""))
                    if ekey == key:
                        # 保留更严重的判定
                        severity = {"🚩红旗": 3, "⚠️疑点": 2, "✅通过": 1}
                        old_s = severity.get(existing.get("verdict", ""), 0)
                        new_s = severity.get(c.get("verdict", ""), 0)
                        if new_s > old_s:
                            existing["verdict"] = c["verdict"]
                            existing["evidence"] = c.get("evidence", existing.get("evidence", ""))
                            existing["detail"] = c.get("detail", existing.get("detail", ""))
                        # 补充证据
                        if c.get("evidence") and c["evidence"] not in existing.get("evidence", ""):
                            existing["evidence"] = (existing.get("evidence", "") + 
                                                     f" [第{c.get('_source_chunk', i+1)}段补充: {c['evidence']}]")
                        break

    # 2. 统计红旗/疑点数量
    red_flags = sum(1 for c in all_checks if "红旗" in c.get("verdict", ""))
    warnings = sum(1 for c in all_checks if "疑点" in c.get("verdict", ""))

    # 3. 重新评估风险等级
    if red_flags >= 3:
        risk_level = "高"
    elif red_flags >= 1 or warnings >= 3:
        risk_level = "中"
    elif warnings >= 1:
        risk_level = "低"
    else:
        risk_level = "低"

    # 结合统计结果调整
    if stat_result:
        if stat_result.get("benford_deviation") and stat_result["benford_deviation"] > 0.3:
            risk_level = "高" if risk_level == "中" else risk_level
        if stat_result.get("p_value_abnormal", 0) > 2:
            risk_level = max(risk_level, "中", key=["低", "中", "高", "可疑黑产"].index)

    # 4. 计算打假得分
    detection_score = red_flags * 30 + warnings * 10
    if stat_result and stat_result.get("benford_deviation"):
        detection_score += int(stat_result["benford_deviation"] * 50)

    # 5. 综合所有summary
    summaries = [r.get("summary", "") for r in reports if not r.get("parse_error")]
    merged_summary = " | ".join(s for s in summaries if s)[:200]
    if len(summaries) > 1:
        merged_summary = f"[合并{len(reports)}段审查] {merged_summary}"

    # 6. 综合conclusion
    conclusions = [r.get("conclusion", "") for r in reports if not r.get("parse_error") and r.get("conclusion")]
    merged_conclusion = "\n\n".join(conclusions) if conclusions else ""

    # 清理临时字段
    for c in all_checks:
        c.pop("_source_chunk", None)

    return {
        "summary": merged_summary,
        "risk_level": risk_level,
        "detection_score": detection_score,
        "checks": all_checks,
        "conclusion": merged_conclusion,
        "_merged_from": len(reports),
    }


# ══════════════════════════════════════════════════════════════
# 报告解析与格式化
# ══════════════════════════════════════════════════════════════

def parse_report(content):
    """解析LLM返回的JSON报告，容错处理"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"raw_output": content, "parse_error": True}


def format_report(report, pdf_path, meta, stat_result):
    """将审查结果格式化为Markdown报告"""
    risk_icons = {"高": "🔴", "中": "🟡", "低": "🟢", "可疑黑产": "⚫️"}
    lines = [
        f"# 📄 学术论文审查报告 [耿同学标准]",
        f"",
        f"**文件**: `{pdf_path}`",
        f"**文件大小**: {meta.get('size_mb', 'N/A')} MB",
        f"**提取字符数**: {meta.get('total_chars', meta.get('chars', 'N/A'))}",
        f"**提取方式**: {meta.get('extraction_method', meta.get('source', 'N/A'))}",
    ]
    # 显示分块信息（如果是分块审查）
    if meta.get("chunk_count") and meta["chunk_count"] > 1:
        lines.append(f"**审查方式**: 分块审查 | {meta['chunk_count']}块 | 单块上限{meta['chunk_size']}字符 | 重叠{meta['overlap']}字符")
    lines.append(f"**审查时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    lines.extend([
        f"",
        f"## 📊 本地统计检测结果",
        f"| 检测项 | 结果 | 状态 |",
        f"|--------|------|------|",
        f"| Benford分布偏差 | {round(stat_result['benford_deviation'],3) if stat_result['benford_deviation'] else '样本不足'} | {stat_result['benford_status'] or 'N/A'} |",
        f"| p值数量/异常 | {stat_result['p_value_count']} / {stat_result['p_value_abnormal']}个>0.05 | {'⚠️异常' if stat_result['p_value_abnormal'] else '✅正常'} |",
        f"| 标准差提及 | {stat_result['sd_count']}处 | N/A |",
    ])
    lines.append(f"| 提取数字数 | {stat_result['number_count']} | - |")

    if stat_result.get("number_consistency"):
        lines.append(f"| 数字自洽性 | {stat_result['number_consistency']} | ⚠️矛盾 |")

    lines.append("")

    if report.get("parse_error"):
        lines.append("## ⚠️ LLM报告解析失败（原始输出）")
        lines.append(f"```\n{report['raw_output']}\n```")
        return "\n".join(lines)

    lines.append(f"## 总评: {report.get('summary', 'N/A')}")
    risk = report.get('risk_level', '未知')
    lines.append(f"**风险等级**: {risk_icons.get(risk, '⚪')} {risk}")
    lines.append(f"**打假得分**: {report.get('detection_score', 0)} (越高越可疑)")
    lines.append("")

    checks = report.get("checks", [])
    if checks:
        lines.append("## 🔍 逐项检查")
        lines.append("")
        lines.append("| # | 分类 | 检查项 | 判定 |")
        lines.append("|---|------|--------|------|")
        for i, c in enumerate(checks, 1):
            lines.append(f"| {i} | {c.get('category', 'N/A')} | {c.get('item', 'N/A')} | {c.get('verdict', 'N/A')} |")
        lines.append("")

        lines.append("## 📋 详细分析")
        lines.append("")
        for i, c in enumerate(checks, 1):
            lines.append(f"### {i}. {c.get('category', 'N/A')} - {c.get('item', 'N/A')} — {c.get('verdict', 'N/A')}")
            if c.get("evidence"):
                lines.append(f"> **证据**: {c['evidence']}")
            if c.get("detail"):
                lines.append(f"\n{c['detail']}")
            lines.append("")

    if report.get("conclusion"):
        lines.append("## 📝 综合结论")
        lines.append(f"\n{report['conclusion']}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="学术论文自动审查工具（耿同学标准 + MinerU）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # MinerU提取 + 完整审查（推荐）
  python paper_audit.py paper.pdf --mineru

  # 仅原始PDF文本提取 + 审查
  python paper_audit.py paper.pdf

  # 指定输出路径
  python paper_audit.py paper.pdf --mineru -o report.md --json
""")
    parser.add_argument("pdf_path", help="待审查的PDF文件路径")
    parser.add_argument("--mineru", action="store_true",
                        help="使用MinerU API将PDF转为Markdown再审查（推荐，质量更高）")
    parser.add_argument("--mineru-model", default="vlm",
                        choices=["pipeline", "vlm", "MinerU-HTML"],
                        help="MinerU模型版本（默认vlm，仅Precision API生效）")
    parser.add_argument("--mineru-lang", default="ch",
                        help="MinerU OCR语言（默认ch=中英，en=英文，japan=日文）")
    parser.add_argument("--no-mineru", action="store_true",
                        help="强制使用原始PDF文本提取，禁用MinerU")
    parser.add_argument("--max-chars", type=int, default=12000,
                        help="提取文本最大字符数（默认12000）")
    parser.add_argument("--output", "-o", help="输出报告文件路径（默认输出到同目录）")
    parser.add_argument("--json", action="store_true", help="同时保存原始JSON结果")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return 1

    # ─── 阶段1：文本提取（保留全文，不再截断） ───
    full_text = None
    meta = {}
    raw_pdf = None
    use_mineru = args.mineru and not args.no_mineru

    if use_mineru:
        print(f"📡 [MinerU] 正在将PDF转为Markdown: {pdf_path.name}")
        md_text, md_meta = mineru_extract(pdf_path, language=args.mineru_lang)
        if md_text:
            full_text = md_text  # 保留全文
            meta = {
                "size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2),
                "total_chars": len(md_text),
                "chars_sent": len(md_text),
                "extraction_method": f"mineru_{md_meta.get('source', 'unknown')}",
            }
            if md_meta.get("batch_id"):
                meta["mineru_batch_id"] = md_meta["batch_id"]
            if md_meta.get("task_id"):
                meta["mineru_task_id"] = md_meta["task_id"]
            print(f"✅ MinerU提取完成: {len(md_text)} 字符（全文保留）")
        else:
            err = md_meta.get("error", "未知错误") if md_meta else "未知错误"
            print(f"❌ MinerU提取失败: {err}")
            print(f"⚠️ 降级使用原始PDF文本提取...")
            use_mineru = False

    if not use_mineru or full_text is None:
        print(f"📖 正在提取PDF文本: {pdf_path}")
        # extract_pdf_text的max_chars参数传大值以获取全文
        full_text, meta, raw_pdf = extract_pdf_text(str(pdf_path), max_chars=999999)
        if not full_text:
            print("❌ 未能从PDF中提取到文本（可能是扫描件或加密PDF）")
            print("💡 建议: 使用 --mineru 参数通过MinerU API提取（支持OCR）")
            return 1
        print(f"✅ 提取完成: {meta['total_chars']} 字符（全文保留）")

    # ─── 阶段2：本地统计检测（使用全文，统计不截断） ───
    print(f"🔢 正在执行本地统计检测...")
    stat_result = local_stat_check(full_text)
    benford_str = f"{round(stat_result['benford_deviation'],3)}" if stat_result['benford_deviation'] else 'N/A'
    print(f"✅ 统计检测完成: Benford偏差={benford_str}, p值异常={stat_result['p_value_abnormal']}, 数字数={stat_result['number_count']}")

    # ─── 阶段3：智能分块 + LLM语义审查（冗余机制） ───
    chunk_size = args.max_chars  # 复用max_chars作为单块上限
    overlap = min(1000, chunk_size // 8)  # 重叠区约12.5%

    chunks = smart_chunk_text(full_text, chunk_size=chunk_size, overlap=overlap)
    total_chunks = len(chunks)

    if total_chunks == 1:
        # 短论文：直接全文审查
        print(f"🔍 论文长度({len(full_text)}字符)在单块范围内，直接审查...")
        try:
            raw_content = call_llm(full_text)
            report = parse_report(raw_content)
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            report = {"parse_error": True, "raw_output": str(e)}
    else:
        # 长论文：分块审查 + 合并
        print(f"🔍 论文较长({len(full_text)}字符)，分为{total_chunks}块(每块≤{chunk_size}字符，重叠{overlap}字符)进行审查...")
        chunk_reports = []
        for chunk_text, chunk_idx, _ in chunks:
            print(f"  📝 审查第{chunk_idx+1}/{total_chunks}块({len(chunk_text)}字符)...")
            try:
                raw_content = call_llm(chunk_text, chunk_info=(chunk_idx, total_chunks))
                chunk_report = parse_report(raw_content)
                chunk_reports.append(chunk_report)
                # 简要反馈
                if not chunk_report.get("parse_error"):
                    risk = chunk_report.get("risk_level", "未知")
                    print(f"     → 第{chunk_idx+1}块风险: {risk}")
                else:
                    print(f"     → 第{chunk_idx+1}块解析异常")
            except Exception as e:
                print(f"  ⚠️ 第{chunk_idx+1}块LLM调用失败: {e}")
                chunk_reports.append({"parse_error": True, "raw_output": str(e)})

        # 合并所有块的审查结果
        print(f"🔗 正在合并{len(chunk_reports)}块审查结果...")
        report = merge_chunk_reports(chunk_reports, stat_result)
        if report.get("_merged_from"):
            print(f"✅ 合并完成: 来自{report['_merged_from']}块，共{len(report.get('checks', []))}个检查项")
            # 更新meta
            meta["chunk_count"] = total_chunks
            meta["chunk_size"] = chunk_size
            meta["overlap"] = overlap

    # ─── 阶段4：生成报告 ───
    md_report = format_report(report, str(pdf_path), meta, stat_result)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = pdf_path.with_suffix(".audit.md")

    output_path.write_text(md_report, encoding="utf-8")
    print(f"✅ 审查报告已保存: {output_path}")

    if args.json:
        json_path = pdf_path.with_suffix(".audit.json")
        json_path.write_text(
            json.dumps({"llm_report": report, "stat_result": stat_result, "meta": meta},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"✅ 原始JSON已保存: {json_path}")

    # 打印摘要
    if not report.get("parse_error"):
        risk = report.get("risk_level", "未知")
        print(f"\n📊 风险等级: {risk} | 总评: {report.get('summary', 'N/A')}")

    return 0


if __name__ == "__main__":
    exit(main())
