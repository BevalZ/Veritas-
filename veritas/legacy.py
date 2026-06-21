#!/usr/bin/env python3
"""Paper Audit - 学术论文自动审查工具 [耿同学版]
基于3个开源项目思路开发：
- wooly99/geng-academic-fraud-detector 耿同学六式
- NeoSpecies/AcademicIntegrityHunter 本地统计算法
- jingshouyan/academic-integrity-geng 五维审查体系
输入论文文件或目录 → 文本提取 → 本地统计检测 + LLM语义分析 → 输出md/html格式报告
用法: python paper_audit.py <paper_path> [--mineru] [--max-chars 8000] [--output report.md]
"""
import re, json, time, argparse, urllib.request, urllib.parse, math, collections, os, mimetypes, fnmatch, csv, platform, webbrowser, subprocess, sys, requests, hashlib, io, concurrent.futures, threading, datetime
from pathlib import Path
from typing import Tuple, Dict, List, Any, Callable

from .adapter_types import (
    AdapterResult,
    AuditAdapters,
    ImageDetectorAdapter,
    ImageSemanticAdapter,
    MinerUAdapter,
    ReferenceLookupAdapter,
    TextLLMAdapter,
)
from .artifacts import (
    _artifact_base_from_output,
    _failed_artifact_options,
    apply_audit_artifact_type,
    audit_artifact_paths,
    audit_limited_reasons,
    coverage_blocking_failure,
    explicit_output_path_from_args,
    failed_audit_artifact_paths,
)
from .failed_diagnostics import (
    adapter_failure_to_audit_failure,
    failed_audit_payload,
    format_failed_audit_html,
    format_failed_audit_markdown,
    preflight_failure_to_audit_failure,
    save_failed_audit_diagnostics,
)
from .external_timeout import _ExternalCapabilityTimeout, _run_with_alarm_timeout
from .fake_adapters import (
    FakeImageDetectorAdapter,
    FakeImageSemanticAdapter,
    FakeMinerUAdapter,
    FakeReferenceLookupAdapter,
    FakeScenarioMixin,
    FakeTextLLMAdapter,
    fake_audit_adapters,
)
from .file_utils import _json_load, _json_save, _load_merged_json_dicts, _safe_name
from .followups import (
    _followup_language_instruction,
    _followup_tone_instruction,
    _normalize_custom_concerns,
    _normalize_followup_issues,
    _split_author_text,
    _followup_draft_filename,
    _followup_output_dir,
    build_followup_generation_context,
    build_followup_prompt,
    generate_and_save_followup_draft_from_namespace,
    generate_followup_draft_from_namespace,
    load_existing_followups,
    normalize_article_identity,
    normalize_followup_language,
    normalize_followup_tone,
    save_followup_artifacts_from_namespace,
)
from .html_utils import _html_escape, _json_for_script_tag
from .http_client import _http_request
from .image_audit_builder import build_image_audit_from_namespace
from .image_cache import _image_file_fingerprint_from_namespace, _image_semantic_cache_key_from_namespace
from .image_collection import (
    _dedupe_paths,
    _extract_images_from_mineru_zip_from_namespace,
    _image_output_dir,
    _latest_mineru_zips,
    collect_image_files_from_namespace,
    collect_mineru_image_files_from_namespace,
    extract_images_from_pdf,
)
from .image_detector_provider import call_imagedetector_from_namespace, _call_imagedetector_unbounded_from_namespace
from .image_semantic_provider import (
    _call_glm_image_semantics_unbounded_from_namespace,
    call_glm_image_semantics_from_namespace,
)
from .image_local_analysis import analyze_image_reasonability_from_namespace
from .image_payloads import _image_to_data_url, _prepare_detector_upload_file
from .image_reporting import (
    _image_detector_display,
    _image_semantic_display,
    format_image_audit_html as _format_image_audit_html,
    format_image_audit_markdown as _format_image_audit_markdown,
    save_image_review_manifest as _save_image_review_manifest,
)
from .image_results import (
    _detector_timeout_result,
    _extract_json_object,
    _glm_error_result,
    _glm_timeout_result,
    _normalize_detector_result,
    _normalize_glm_image_result,
)
from .image_selection import (
    _flush_image_cache,
    _image_audit_sort_key,
    _image_detector_priority_key,
    _image_semantic_priority_key,
)
from .limit_utils import _effective_limit
from .local_analysis import benford_analysis, extract_all_numbers, local_stat_check, smart_chunk_text
from .config import (
    CapabilityConfig,
    RuntimeConfig,
    apply_runtime_config_to_namespace,
    default_runtime_config_from_namespace,
    load_runtime_config_from_namespace,
)
from .desktop_gui import (
    DESKTOP_GUI_ARTIFACT_LABELS,
    DESKTOP_GUI_CONFIG_CAPABILITIES,
    DESKTOP_GUI_CONFIG_DEPENDENCIES,
    DESKTOP_GUI_FOLLOWUP_LABELS,
    DESKTOP_GUI_LLM_CONFIG_FIELDS,
    DESKTOP_GUI_STAGE_LABELS,
    _desktop_gui_preflight_status_label,
    _desktop_gui_report_type_label,
    _desktop_gui_risk_label,
    _desktop_gui_stage_label,
    _desktop_gui_status_label,
    desktop_gui_artifact_preview,
    desktop_gui_checked_config_snapshot_from_namespace,
    desktop_gui_config_file_path,
    desktop_gui_config_snapshot,
    desktop_gui_followup_context_from_namespace,
    desktop_gui_generate_followup_draft_from_namespace,
    desktop_gui_progress_from_log_line,
    desktop_gui_run_summary,
    desktop_gui_start_run,
    desktop_gui_write_llm_config as _desktop_gui_write_llm_config,
    open_desktop_path,
)
from .evidence_rendering import (
    _clean_mineru_table_block,
    _escaped_html_table_fragment_to_html,
    _evidence_contains_table,
    _is_markdown_table_separator,
    _looks_like_markdown_table,
    _markdown_table_to_html,
    _parse_html_table_rows,
    _plain_table_summary_text,
    _render_data_table_html,
    _render_unmarked_evidence_html,
    _split_markdown_table_row,
    render_evidence_html,
    render_evidence_summary_html,
)
from .runtime_metadata import ensure_runtime_meta, runtime_metadata, runtime_utc_year
from . import run_logging as _run_logging
from .run_logging import (
    _allow_llm_cache_read,
    detect_pdf_input,
    get_output_base,
    get_resume_dir,
    progress_bar,
    resume_event,
    run_cache_use_manifest,
    run_extraction_route,
    run_input_manifest,
    run_scope_flags_from_args,
    save_mineru_artifacts,
    setup_run_logging,
)
from . import risk_rules as _risk_rules
from .markdown_utils import _md_escape_cell
from .text_utils import _brief_text, _normalize_title, _text_fingerprint, _title_tokens, _token_similarity
from .text_extraction import extract_pdf_text
from .models import (
    AuditFailure,
    AuditReportModel,
    CoverageModel,
    EvidenceFinding,
    ImageAuditModel,
    ReferenceAuditModel,
    RunMetadataModel,
)
from .mineru_text import (
    _extract_mineru_structured_text,
    _flatten_mineru_items,
    _format_mineru_content_list,
    _format_mineru_table_block,
    _mineru_block_text,
    _mineru_block_type,
    _mineru_content_text,
    _normalize_markdown_table,
    _normalize_mineru_table_text,
    _table_rows_to_markdown,
)
from .paper_identity import extract_paper_identity
from .pattern_updates import update_patterns_from_namespace
from .preflight import _chat_completions_endpoint, preflight_mineru_from_namespace, preflight_text_llm_from_namespace
from .preflight_types import PreflightResult, run_preflight_once
from .project_files import (
    SUPPORTED_TEXT_FILE_EXTENSIONS,
    extracted_body_text,
    _is_missing_meta_value,
    _main_paper_score,
    find_project_files,
    normalize_run_meta,
    optional_dependency_for_extension_from_namespace,
)
from .production_adapters import (
    ProductionImageDetectorAdapter,
    ProductionImageSemanticAdapter,
    ProductionMinerUAdapter,
    ProductionReferenceLookupAdapter,
    ProductionTextLLMAdapter,
    default_audit_adapters,
)
from .reference_parsing import (
    REFERENCE_CONTAINER_WORD_RE,
    REFERENCE_OFFICIAL_SITE_RULES,
    _author_similarity,
    _clean_reference_text,
    _crossref_work_to_match,
    _html_title,
    _html_to_searchable_text,
    _looks_like_reference_author_fragment,
    _looks_like_reference_container_part,
    _looks_like_reference_table_noise,
    _name_tokens,
    _normalize_doi,
    _official_page_matches_reference,
    _official_site_search_urls,
    _openalex_work_to_match,
    _pubmed_summary_to_match,
    _reference_items_from_numbered_lines,
    _reference_year,
    _score_reference_match,
    _score_reference_matches,
    _truncate_reference_suffix,
    build_reference_query,
    extract_reference_author_hint,
    extract_reference_container_hint,
    extract_reference_title,
    extract_reference_year_hint,
    parse_references,
    reference_cache_key,
    split_references_from_text,
)
from .reference_audit import audit_references_from_namespace
from .reference_online import (
    _reference_get_json_from_namespace,
    lookup_crossref_reference_from_namespace,
    lookup_official_site_reference_from_namespace,
    lookup_openalex_reference_from_namespace,
    lookup_pubmed_reference_from_namespace,
    verify_reference_online_from_namespace,
)
from .reference_reporting import (
    REFERENCE_ISSUE_LABELS,
    _reference_display_title,
    _reference_issue_text,
    _reference_online_summary,
    _reference_query_text,
    _reference_text_html,
    format_reference_audit_html,
    format_reference_audit_markdown,
)
from .resource_availability import audit_resources_from_namespace, verify_resource_availability_from_namespace
from .resource_parsing import _classify_resource, _clean_resource_url, _resource_context, extract_paper_resources
from .resource_reporting import (
    RESOURCE_STATUS_LABELS,
    _resource_status_text,
    _resource_type_text,
    format_resource_audit_html,
    format_resource_audit_markdown,
)
from .run_types import RunRequest, RunResult
from .report_schema import LLM_REQUIRED_FINDING_FIELDS, normalize_llm_report_schema, parse_report
from .report_checks import (
    _check_reason,
    _check_sort_key,
    _check_source_tags,
    _check_source_text,
    _check_suspicion_score,
    _check_verdict_class,
    _is_suspicious_check,
    _merged_group_html,
    _merged_group_summary_text,
    _sanitize_reason_text,
)
from .report_html_fragments import build_html_report_body_from_namespace, build_html_report_context_from_namespace, build_html_status_fragments_from_namespace
from .report_html_sections import format_html_check_sections_from_namespace
from .report_markdown import format_report_from_namespace
from .report_action_context import _report_action_context
from .report_action_panel import format_web_action_panel_html, report_action_service_url
from .report_action_service import (
    _read_json_request_body,
    _report_action_entrypoint,
    ensure_report_action_service_from_namespace,
    open_html_artifact,
    report_action_api_response_from_namespace,
    report_action_service_health,
    serve_report_actions_from_namespace,
)
from .review_overview import (
    build_audit_action_items,
    build_review_overview,
    format_audit_action_summary_html,
    format_audit_action_summary_markdown,
    format_review_overview_html,
    format_review_overview_markdown,
)
from .retry_commands import _shell_quote, default_retry_command, retry_command_from_args
from .risk_rule_helpers import (
    _CHECK_STOPWORDS,
    _append_unique_evidence,
    _brief_check_list,
    _build_merged_conclusion,
    _build_merged_summary,
    _check_label_for_summary,
    _check_member_summary,
    _check_merge_key,
    _check_severity,
    _check_similarity,
    _check_text_blob,
    _check_text_for_scoring,
    _downgrade_extraction_red_flags,
    _downgrade_unverified_future_publication_checks,
    _extract_years_from_check,
    _is_future_publication_check,
    _is_extraction_limited_check,
    _max_risk,
    _merge_check_into,
    _normalize_check_terms,
    _risk_index,
    _same_or_similar_check,
    _should_downgrade_extraction_red_flag,
    _soften_extraction_red_flag_language,
    _soften_nonfinal_red_flag_language,
)
from .versions import ADAPTER_VERSION, PROMPT_VERSION, RISK_RULE_VERSION, SCHEMA_VERSION
from .zhuque import ZHUQUE_URL, copy_to_clipboard_from_namespace, launch_zhuque_ai_detect_from_namespace
from .web_runner_paths import (
    _web_runner_common_search_roots,
    _web_runner_is_basename_only_input,
    resolve_web_runner_input_path,
)
from .web_runner import (
    _web_runner_capability_status,
    _web_runner_history_path,
    _web_runner_input_parts,
    _web_runner_now,
    _web_runner_output_base,
    _web_runner_report_summary_from_payload,
    _web_runner_run_id,
    _web_runner_safe_run,
    _web_runner_timestamp,
    dropped_local_path_from_uri_text,
    pick_local_path,
    web_runner_config_status_from_namespace,
    web_runner_cors_headers,
    web_runner_default_output_stem_from_namespace,
    web_runner_start_command_from_namespace,
)
from .workspace import (
    create_run_workspace,
    record_run_workspace_artifacts,
    record_run_workspace_json,
    run_workspace_path,
)

_risk_rules.runtime_utc_year = lambda: runtime_utc_year()
apply_risk_rules = _risk_rules.apply_risk_rules
merge_chunk_reports = _risk_rules.merge_chunk_reports

# Windows/重定向控制台默认GBK时，emoji/中文符号可能触发UnicodeEncodeError；统一兜底为UTF-8。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# LLM运行参数：由CLI覆盖。默认保守，避免一次请求无限阻塞。
LLM_TIMEOUT = 45
LLM_RETRIES = 1
EXTRACT_CACHE_VERSION = 7
MIN_IMAGE_BYTES = 5000
IMAGE_SEMANTIC_CACHE_VERSION = 3


# 可选依赖：处理Word/Excel/Supplement文件
try:
    from docx import Document
    DOCX_SUPPORTED = True
except ImportError:
    DOCX_SUPPORTED = False
try:
    from openpyxl import load_workbook
    EXCEL_SUPPORTED = True
except ImportError:
    EXCEL_SUPPORTED = False

# ══════════════════════════════════════════════════════════════
# 配置区
# ══════════════════════════════════════════════════════════════
import importlib

LLM_API_KEY = ""
LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"
MINERU_TOKEN = ""
MINERU_BASE = "https://mineru.net"
GLM_API_KEY = ""
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_VISION_MODEL = "glm-4.6v-flash"

def default_runtime_config() -> RuntimeConfig:
    return default_runtime_config_from_namespace(globals())


def load_runtime_config(config_module_name: str = "config", env=os.environ, verbose: bool = True) -> RuntimeConfig:
    """Load config.py and environment variables explicitly for a CLI run."""
    return load_runtime_config_from_namespace(globals(), config_module_name=config_module_name, env=env, verbose=verbose)


def apply_runtime_config(runtime_config: RuntimeConfig):
    """Apply explicit runtime config to the legacy module globals used by current code."""
    return apply_runtime_config_to_namespace(runtime_config, globals())


def preflight_mineru(timeout=10) -> PreflightResult:
    return preflight_mineru_from_namespace(globals(), timeout=timeout)


def preflight_text_llm(timeout=10) -> PreflightResult:
    return preflight_text_llm_from_namespace(globals(), timeout=timeout)


def run_adapter_e2e_audit(
    input_path: Path,
    adapters: AuditAdapters,
    output_dir: Path = None,
    text: str = "Fake audit text with n=20 and p=0.04.",
    references_text: str = "",
    image_paths: List[str] = None,
) -> Dict[str, Any]:
    """Deterministic adapter-driven audit harness for end-to-end tests."""
    input_path = Path(input_path)
    output_dir = Path(output_dir or (input_path if input_path.is_dir() else input_path.parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = input_path.name if input_path.is_dir() else input_path.stem
    workspace = create_run_workspace(input_path, output_dir, output_stem)
    completed_stages = ["init"]
    image_paths = list(image_paths or [])
    retry_command = default_retry_command(input_path)

    def fail(capability: str, result: AdapterResult):
        failure = adapter_failure_to_audit_failure(capability, result, retry_command, completed_stages)
        md_path, json_path = save_failed_audit_diagnostics(failure, input_path)
        record_run_workspace_artifacts(workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
        return {
            "outcome": "failed",
            "capability": capability,
            "md_path": md_path,
            "json_path": json_path,
            "workspace": workspace,
        }

    if input_path.suffix.lower() == ".pdf":
        mineru_preflight = adapters.mineru.preflight()
        if not mineru_preflight.ok:
            return fail("mineru", mineru_preflight)
        mineru_result = adapters.mineru.extract(input_path, output_dir=output_dir)
        if not mineru_result.ok:
            return fail("mineru", mineru_result)
        value = mineru_result.value or {}
        text = value.get("text", text) if isinstance(value, dict) else text
        completed_stages.append("mineru_extract")

    if references_text:
        reference_result = adapters.reference_lookup.audit(references_text, online=True)
        if not reference_result.ok:
            return fail("reference_lookup", reference_result)
        completed_stages.append("reference_lookup")

    if image_paths:
        for image_path in image_paths:
            semantic_result = adapters.image_semantic.analyze(image_path)
            if semantic_result.status == "failure":
                return fail("image_semantic", semantic_result)
            detector_result = adapters.image_detector.detect(image_path)
            if detector_result.status == "failure":
                return fail("image_detector", detector_result)
        completed_stages.append("image_audit")

    llm_preflight = adapters.text_llm.preflight()
    if not llm_preflight.ok:
        return fail("text_llm", llm_preflight)
    llm_result = adapters.text_llm.review(text, chunk_info=(0, 1))
    if not llm_result.ok:
        return fail("text_llm", llm_result)
    completed_stages.append("text_llm_review")

    report = parse_report(llm_result.value)
    if report.get("parse_error"):
        return fail("text_llm", AdapterResult.failure("schema_error", "LLM returned invalid report schema", {"raw": llm_result.value}))

    stat_result = local_stat_check(text)
    image_audit = {"image_count": len(image_paths), "images": []}
    report = apply_risk_rules(report, stat_result=stat_result, image_audit=image_audit)
    meta = apply_audit_artifact_type({
        "artifact_type": "complete",
        "total_chars": len(text),
        "extraction_method": "fake_adapter",
        "reference_audit": {"reference_count": 1 if references_text else 0},
        "resource_audit": {"resource_count": 0, "resources": [], "issues": []},
        "image_audit": image_audit,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "risk_rule_version": RISK_RULE_VERSION,
    }, [])
    md_path, html_path, json_path = audit_artifact_paths(input_path, artifact_type="complete")
    md_path.write_text(format_report(report, str(input_path), meta, stat_result), encoding="utf-8")
    html_path.write_text(format_html_report(report, str(input_path), meta, stat_result), encoding="utf-8")
    json_path.write_text(
        json.dumps({"report_type": "complete", "llm_report": report, "stat_result": stat_result, "meta": meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    record_run_workspace_artifacts(workspace, "complete", [md_path, html_path, json_path], meta={"completed_stages": completed_stages})
    return {
        "outcome": "complete",
        "md_path": md_path,
        "html_path": html_path,
        "json_path": json_path,
        "workspace": workspace,
    }


# ─── 欺诈模式知识库加载 ───
FRAUD_PATTERNS_PATH = Path(__file__).resolve().parent.parent / "fraud_patterns.json"
FRAUD_PATTERNS = []
PATTERN_HINTS = ""
if FRAUD_PATTERNS_PATH.exists():
    try:
        with open(FRAUD_PATTERNS_PATH, "r", encoding="utf-8") as f:
            pattern_data = json.load(f)
            FRAUD_PATTERNS = pattern_data.get("patterns", [])
        print(f"✅ 加载欺诈模式知识库成功，共{len(FRAUD_PATTERNS)}条检测模式")
        # 构建提示词片段
        PATTERN_HINTS = "\n## 最新欺诈模式知识库（社区贡献+PubPeer案例汇总）\n"
        for idx, p in enumerate(FRAUD_PATTERNS, 1):
            PATTERN_HINTS += f"{idx}. [{p['risk_level']}风险] {p['name']}：{p['detection_hint']}\n"
    except Exception as e:
        print(f"⚠️ 知识库加载失败: {e}，使用默认检测规则")

# ══════════════════════════════════════════════════════════════
# 审查体系配置 - LLM System Prompt
# ══════════════════════════════════════════════════════════════
SYSTEM_PROMPT_TPL = """你是一个严厉的学术论文审查专家（耿同学标准）。
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

## OCR/表格噪声约束
- 输入中可能包含由MinerU/OCR生成的结构化标记，如[[TABLE_START]]、[[TABLE_END]]、[[FIGURE]]、[[EXTRACTION_NOTE]]。
- 不得仅因Markdown表格错位、列名断裂、OCR漏字、分页续表、表格被分块或图片转写不清晰判定为🚩红旗。
- 表格相关红旗必须基于明确学术证据：同一指标跨正文/表格矛盾、样本量/分组不自洽、p值/置信区间/均值标准差逻辑冲突、图表结论与正文明确冲突。
- 对提取不清晰但无明确学术矛盾的内容，应判为⚠️疑点或✅通过，并在detail中写“需人工核对原PDF/表格”，不要写成造假结论。

请按以下JSON格式输出（确保JSON合法，无多余内容）：
{{
  "summary": "一句话总评",
  "risk_level": "高/中/低/严重证据冲突",
  "detection_score": 0,
  "checks": [
    {{
      "category": "数据与结果/图片与图表/方法论/结构与引用/作者与期刊",
      "item": "检查项名称",
      "verdict": "🚩红旗/⚠️疑点/✅通过",
      "source": "证据来源位置，例如正文段落/表格/图片/参考文献编号；没有则写'未定位'",
      "source_text": "必须填写：论文原文中的直接摘录；若无直接证据写'未找到直接原文证据'",
      "evidence": "必须填写：具体证据，引用原文片段并说明所在章节/表图/段落线索",
      "reason": "必须填写：为什么该证据支持此判定，说明可疑逻辑链",
      "recommendation": "必须填写：建议人工复核或后续处理动作",
      "confidence": 0.0,
      "detail": "详细分析说明：包含影响范围、需人工复核的点、若为通过也说明依据"
    }}
  ],
  "conclusion": "综合结论与行动建议"
}}
{pattern_hints}
"""

# 动态构建系统提示词
SYSTEM_PROMPT = SYSTEM_PROMPT_TPL.format(pattern_hints=PATTERN_HINTS)

# ══════════════════════════════════════════════════════════════
# MinerU API 模块 — PDF转Markdown
# ══════════════════════════════════════════════════════════════

def mineru_precision_extract_by_url(pdf_url, model_version="vlm", language="ch",
                                     poll_interval=10, poll_timeout=600, output_dir=None):
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
            markdown = _download_zip_and_extract_md(zip_url, output_dir=output_dir, source_name="url_input", batch_id=batch_id)
            if markdown:
                meta = {"source": "mineru_precision", "batch_id": batch_id,
                        "zip_url": zip_url, "zip_saved_dir": str(output_dir) if output_dir else str(_run_logging._RUN_OUTPUT_DIR) if _run_logging._RUN_OUTPUT_DIR else None,
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


def mineru_extract_file(file_path, model_version="vlm", language="ch",
                        poll_interval=10, poll_timeout=600, output_dir=None):
    """🎯 MinerU v4 本地文件解析（需要Token，≤200MB/200页）

    流程：POST /api/v4/file-urls/batch → PUT上传至OSS → 轮询任务结果 → 下载zip提取Markdown
    返回：(markdown_text, meta_dict) 或 (None, error_dict)
    """
    file_path = Path(file_path)
    file_size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"  🎯 [MinerU v4] 上传文件: {file_path.name} ({file_size_mb:.1f}MB)")

    if not MINERU_TOKEN:
        return None, {"error": "MINERU_TOKEN未配置，无法使用MinerU API"}

    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_TOKEN}"
    }

    # 1. 获取上传URL
    try:
        batch_payload = json.dumps({
            "enable_formula": True,
            "language": language,
            "layout_model": "doclayout_yolo",
            "enable_table": True,
            "files": [{"name": file_path.name, "is_ocr": True}]
        }).encode()
        resp_data, _ = _http_request(
            f"{MINERU_BASE}/api/v4/file-urls/batch", "POST",
            auth_headers, batch_payload, timeout=30
        )
        result = json.loads(resp_data.decode())
    except Exception as e:
        return None, {"error": f"获取上传URL失败: {e}"}

    if result.get("code") != 0:
        return None, {"error": f"file-urls/batch返回异常: {result}"}

    batch_id = result["data"]["batch_id"]
    file_urls = result["data"]["file_urls"]
    if not file_urls:
        return None, {"error": "未获取到上传URL"}

    upload_url = file_urls[0]
    print(f"  ✅ 获取上传URL成功: batch_id={batch_id}")

    # 2. 上传文件至OSS（注意：预签名URL不能带Authorization header，也不带Content-Type以免签名不匹配）
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        resp = requests.put(upload_url, data=file_data, timeout=120)
        resp.raise_for_status()
        print(f"  ✅ 文件已上传至OSS ({file_size_mb:.1f}MB)")
    except Exception as e:
        return None, {"error": f"上传文件到OSS失败: {e}"}

    # 3. 轮询批量解析结果（file-urls/batch 上传后，用 batch_id 查询 extract-results/batch）
    # 经验验证：/api/v4/extract/task/{batch_id} 会返回 task not found，batch_id 应查批量结果接口。
    poll_url = f"{MINERU_BASE}/api/v4/extract-results/batch/{batch_id}"
    start = time.time()
    state_labels = {"processing": "处理中", "queued": "排队中", "pending": "等待中"}

    while time.time() - start < poll_timeout:
        try:
            resp_data, _ = _http_request(poll_url, "GET", auth_headers, timeout=30)
            result = json.loads(resp_data.decode())
        except Exception as e:
            print(f"  ⚠️ 轮询异常: {e}")
            time.sleep(poll_interval)
            continue

        elapsed = int(time.time() - start)
        if result.get("code") != 0:
            print(f"  ⚠️ [{elapsed}s] 查询结果异常: code={result.get('code')} msg={result.get('msg')}")
            time.sleep(poll_interval)
            continue

        data = result.get("data", {}) or {}
        extract_results = data.get("extract_result") or data.get("task_list") or []
        task = extract_results[0] if extract_results else data
        state = task.get("state", "unknown")

        if state == "done":
            zip_url = task.get("full_zip_url") or data.get("full_zip_url")
            if not zip_url:
                return None, {"error": "任务完成但未获取到下载链接", "batch_id": batch_id,
                              "result": result}

            print(f"  ✅ [{elapsed}s] 解析完成，下载Markdown...")
            markdown = _download_zip_and_extract_md(zip_url, output_dir=output_dir, source_name=file_path.name, batch_id=batch_id)
            if markdown:
                return markdown, {"source": "mineru_v4", "batch_id": batch_id,
                                  "zip_url": zip_url, "model": model_version,
                                  "zip_saved_dir": str(output_dir) if output_dir else str(_run_logging._RUN_OUTPUT_DIR) if _run_logging._RUN_OUTPUT_DIR else None,
                                  "chars": len(markdown)}
            return None, {"error": "下载或解压zip失败", "batch_id": batch_id,
                          "zip_url": zip_url}

        elif state == "failed":
            err = task.get("err_msg") or data.get("err_msg") or "未知错误"
            return None, {"error": f"任务失败: {err}", "batch_id": batch_id,
                          "result": result}

        label = state_labels.get(state, state)
        print(f"  ⏳ [{elapsed}s] {label}...")
        time.sleep(poll_interval)

    return None, {"error": f"轮询超时({poll_timeout}s), batch_id={batch_id}",
                  "poll_url": poll_url}


def _download_zip_and_extract_md(zip_url, output_dir=None, source_name=None, batch_id=None):
    """下载zip、按输入同目录保存，并优先提取MinerU结构化文本。"""
    zip_data = None
    last_err = None
    for attempt in range(3):
        try:
            if attempt:
                print(f"  ↻ MinerU zip下载重试 {attempt}/2...")
            zip_data, _ = _http_request(zip_url, "GET", timeout=180)
            if output_dir or _run_logging._RUN_OUTPUT_DIR:
                save_mineru_artifacts(zip_url, zip_data, source_name or "mineru", output_dir=output_dir, batch_id=batch_id)
            break
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    if zip_data is None:
        print(f"  ❌ 下载zip失败: {last_err}")
        return None

    # 用 zipfile 从内存解析
    import zipfile, io
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            structured = _extract_mineru_structured_text(zf)
            if structured:
                return structured

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


def mineru_extract(file_path, language="ch", output_dir=None):
    """MinerU统一入口：使用v4 API
    
    本地文件：上传至OSS → 创建任务 → 轮询结果
    URL：直接提交v4/extract/task
    返回：(markdown_text, meta_dict) 或 (None, error_dict)
    """
    file_path = Path(file_path)
    if file_path.exists():
        return mineru_extract_file(file_path, language=language, output_dir=output_dir)
    else:
        # 当作URL处理
        return mineru_precision_extract_by_url(str(file_path), language=language, output_dir=output_dir)


def extract_text_from_file(file_path: Path, max_chars_per_file=None, use_mineru=False, mineru_lang="ch", output_dir=None) -> str:
    """从任意支持的文件类型中提取文本

    max_chars_per_file=None 表示不截断。目录级分析默认应先完整提取每个文件，
    再由后续 smart_chunk_text 做全目录分块/合并审查，避免“目录里只分析到一个文件/每文件只取开头”。
    """
    ext = file_path.suffix.lower()
    header = f"=== 文件: {file_path.name} ==="
    text = f"\n\n{header}"
    limit = max_chars_per_file if max_chars_per_file is not None else 999999999
    
    try:
        if ext == ".pdf":
            if use_mineru:
                print(f"  ⚙️  使用MinerU API提取PDF全文内容...")
                md, meta = mineru_extract(file_path, language=mineru_lang, output_dir=output_dir)
                if md:
                    text += "\n" + md
                else:
                    err = meta.get("error", "未知错误") if isinstance(meta, dict) else "未知错误"
                    print(f"  ⚠️  MinerU提取失败: {err}，降级为本地PDF提取")
                    pdf_text, _, _ = extract_pdf_text(file_path, max_chars=limit)
                    text += "\n" + pdf_text
            else:
                pdf_text, _, _ = extract_pdf_text(file_path, max_chars=limit)
                text += "\n" + pdf_text
        elif ext == ".docx" and DOCX_SUPPORTED:
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += "\n" + para.text
            for table in doc.tables:
                for row in table.rows:
                    text += "\n" + " | ".join([cell.text for cell in row.cells])
        elif ext in {".xlsx", ".xlsm"} and EXCEL_SUPPORTED:
            wb = load_workbook(file_path, read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                text += f"\n[工作表: {sheet_name}]"
                sheet = wb[sheet_name]
                for i, row in enumerate(sheet.iter_rows(values_only=True)):
                    if max_chars_per_file is not None and i > 1000:
                        text += "\n[数据过多，已截断]"
                        break
                    row_str = " | ".join([str(v) for v in row if v is not None])
                    if row_str.strip():
                        text += "\n" + row_str
        elif ext == ".csv":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if max_chars_per_file is not None and i > 1000:
                        text += "\n[数据过多，已截断]"
                        break
                    text += "\n" + " | ".join(row)
        elif ext in {".txt", ".md"}:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text += "\n" + f.read(limit)
    except Exception as e:
        text += f"\n[文件解析失败: {str(e)}]"
    
    if max_chars_per_file is not None and len(text) > max_chars_per_file + len(header) + 4:
        return text[:max_chars_per_file + len(header) + 4] + "\n[文本过长已截断]"
    return text


def optional_dependency_for_extension(ext: str):
    return optional_dependency_for_extension_from_namespace(globals(), ext)


# ══════════════════════════════════════════════════════════════
# LLM调用模块
# ══════════════════════════════════════════════════════════════

def call_llm(text, max_retries=None, chunk_info=None, timeout=None):
    """调用OpenAI兼容API进行语义审查。

    改进点：
    - timeout/max_retries可由CLI控制，便于不稳定网关降级；
    - 每次失败打印尝试编号，日志更容易判断是否卡死；
    - 去除重复payload构建，减少维护歧义。
    """
    if max_retries is None:
        max_retries = int(globals().get("LLM_RETRIES", 1))
    if timeout is None:
        timeout = int(globals().get("LLM_TIMEOUT", 45))

    if chunk_info and chunk_info[1] > 1:
        idx, total = chunk_info
        user_msg = (
            f"审查以下论文文本（第{idx+1}/{total}段，请重点关注本段内容，"
            f"同时注意与其他段落的逻辑连贯性）。"
            "只返回一个合法JSON对象；checks最多2条；每个字符串字段不超过120字；"
            "source_text/source/evidence必须短摘录，不能展开长篇推理：\n\n"
            f"{text}"
        )
    else:
        user_msg = (
            "审查以下论文文本。只返回一个合法JSON对象；checks最多3条；"
            "每个字符串字段不超过120字；source_text/source/evidence必须短摘录：\n\n"
            f"{text}"
        )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    _BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            if attempt:
                print(f"     ↻ API重试 {attempt}/{max_retries}（timeout={timeout}s）")
            resp = requests.post(
                _chat_completions_endpoint(LLM_API_URL), json=payload,
                headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json", "User-Agent": _BROWSER_UA},
                timeout=timeout
            )
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                print(f"     ⚠️ API尝试 {attempt+1}/{max_retries+1} 失败: {str(e)[:160]}")
                time.sleep(3 * (attempt + 1))
            else:
                raise RuntimeError(f"API调用失败({attempt+1}次, timeout={timeout}s): {str(last_err)[:180]}...")


def call_llm_messages(messages, temperature=0.2, timeout=None, max_tokens=1800):
    if timeout is None:
        timeout = int(globals().get("LLM_TIMEOUT", 60))
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY未配置")
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    _BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    resp = requests.post(
        _chat_completions_endpoint(LLM_API_URL),
        json=payload,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": _BROWSER_UA,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]


def save_followup_artifacts(kind, context, language, text):
    return save_followup_artifacts_from_namespace(globals(), kind, context, language, text)


def generate_and_save_followup_draft(
    kind,
    context,
    language="zh",
    identity=None,
    selected_issues=None,
    custom_concerns=None,
    tone="conservative",
    disclaimer_confirmed=False,
    timeout=None,
):
    return generate_and_save_followup_draft_from_namespace(
        globals(),
        kind,
        context,
        language=language,
        identity=identity,
        selected_issues=selected_issues,
        custom_concerns=custom_concerns,
        tone=tone,
        disclaimer_confirmed=disclaimer_confirmed,
        timeout=timeout,
    )


def generate_followup_draft(kind, context, language="zh", tone=None, timeout=None):
    return generate_followup_draft_from_namespace(globals(), kind, context, language=language, tone=tone, timeout=timeout)


def ensure_report_action_service(host="127.0.0.1", port=8765, log_path: Path = None, startup_timeout=2.0):
    return ensure_report_action_service_from_namespace(globals(), host=host, port=port, log_path=log_path, startup_timeout=startup_timeout)


def _report_action_api_response(route, payload):
    return report_action_api_response_from_namespace(globals(), route, payload)


def serve_report_actions(host="127.0.0.1", port=8765):
    return serve_report_actions_from_namespace(globals(), host=host, port=port)


def web_runner_default_output_stem(input_path, timestamp=None):
    return web_runner_default_output_stem_from_namespace(globals(), input_path, timestamp=timestamp)


def web_runner_config_status():
    return web_runner_config_status_from_namespace(globals())


class WebRunnerState:
    """State boundary for the local browser runner."""

    def __init__(self, history_path=None):
        self.history_path = _web_runner_history_path(history_path)
        self.lock = threading.Lock()
        self.runs = {}
        self.active_run_id = None
        self._load_history()

    def _load_history(self):
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
            items = payload.get("runs") if isinstance(payload, dict) else payload
            if isinstance(items, list):
                self.runs = {str(item.get("id")): dict(item) for item in items if item.get("id")}
                for run in self.runs.values():
                    if run.get("status") == "running":
                        run["status"] = "failed"
                        run["finished_at"] = run.get("finished_at") or _web_runner_now()
                        run["message"] = "上次本地服务退出时该任务仍在运行。"
        except FileNotFoundError:
            self.runs = {}
        except Exception:
            self.runs = {}

    def _save_history(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        items = [_web_runner_safe_run(run) for run in self.runs.values()]
        items.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        tmp_path = self.history_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps({"runs": items[:100]}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.history_path)

    def list_runs(self):
        with self.lock:
            items = [_web_runner_safe_run(run) for run in self.runs.values()]
        items.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        return items[:100]

    def get_run(self, run_id):
        with self.lock:
            run = self.runs.get(str(run_id))
            return _web_runner_safe_run(run) if run else None

    def _append_log(self, run_id, text):
        if text is None:
            return
        line = str(text).rstrip("\n")
        with self.lock:
            run = self.runs.get(run_id)
            if not run:
                return
            logs = run.setdefault("logs", [])
            logs.append(line)
            if len(logs) > 2000:
                del logs[: len(logs) - 2000]
            run["log_count"] = len(logs)

    def logs_since(self, run_id, offset=0):
        with self.lock:
            run = self.runs.get(str(run_id))
            if not run:
                return None
            logs = list(run.get("logs") or [])
        start = max(0, int(offset or 0))
        return {"ok": True, "run_id": str(run_id), "offset": len(logs), "lines": logs[start:]}

    def start_run(self, input_path, output=None, fresh=False):
        prepared = web_runner_start_command_from_namespace(globals(), input_path, output=output, fresh=fresh)
        if not prepared.get("ok"):
            return prepared["response"], prepared["status"]
        resolved_input = prepared["input_path"]
        output_text = prepared["output"]
        command = prepared["command"]

        with self.lock:
            if self.active_run_id:
                active = self.runs.get(self.active_run_id) or {}
                if active.get("status") == "running":
                    return {"ok": False, "error": "busy", "active_run": _web_runner_safe_run(active)}, 409
                self.active_run_id = None
            run_id = _web_runner_run_id(resolved_input)
            run = {
                "id": run_id,
                "input_path": resolved_input,
                "output": output_text,
                "fresh": bool(fresh),
                "command": command,
                "started_at": _web_runner_now(),
                "finished_at": None,
                "status": "running",
                "message": "审查运行中",
                "logs": [],
                "log_count": 0,
                "artifacts": {},
                "report_type": "",
            }
            self.runs[run_id] = run
            self.active_run_id = run_id
            self._save_history()

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            with self.lock:
                run = self.runs[run_id]
                run["status"] = "failed"
                run["finished_at"] = _web_runner_now()
                run["message"] = f"{type(e).__name__}: {_brief_text(str(e), 240)}"
                self.active_run_id = None
                self._save_history()
            return {"ok": False, "error": "start_failed", "run": self.get_run(run_id)}, 500

        with self.lock:
            run = self.runs[run_id]
            run["_process"] = process
            run["pid"] = getattr(process, "pid", None)
            self._save_history()

        thread = threading.Thread(target=self._watch_process, args=(run_id, process), daemon=True)
        thread.start()
        return {"ok": True, "run": self.get_run(run_id)}, 200

    def _watch_process(self, run_id, process):
        try:
            stdout = getattr(process, "stdout", None)
            if stdout is not None:
                for line in stdout:
                    self._append_log(run_id, line)
            returncode = process.wait()
        except Exception as e:
            self._append_log(run_id, f"[web-runner] {type(e).__name__}: {_brief_text(str(e), 240)}")
            returncode = getattr(process, "returncode", 1)
        self._finish_run(run_id, returncode)

    def _finish_run(self, run_id, returncode):
        with self.lock:
            run = self.runs.get(run_id)
            if not run:
                return
            canceled = bool(run.get("_cancel_requested"))
            run["returncode"] = returncode
            run["finished_at"] = _web_runner_now()
            if canceled:
                run["status"] = "canceled"
                run["message"] = "已取消。本输入的断点续作缓存会在下次重新运行时继续复用。"
            elif int(returncode or 0) == 0:
                run["status"] = "succeeded"
                run["message"] = "审查完成"
            else:
                run["status"] = "failed"
                run["message"] = f"审查失败，退出码 {returncode}"
            run.pop("_process", None)
            if self.active_run_id == run_id:
                self.active_run_id = None
        self.discover_artifacts(run_id)

    def cancel_run(self, run_id):
        with self.lock:
            run = self.runs.get(str(run_id))
            if not run:
                return {"ok": False, "error": "not_found"}, 404
            process = run.get("_process")
            if run.get("status") != "running" or process is None:
                return {"ok": True, "run": _web_runner_safe_run(run)}, 200
            run["_cancel_requested"] = True
            run["message"] = "正在取消"
            self._save_history()
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except TypeError:
                process.wait()
            except subprocess.TimeoutExpired:
                process.kill()
        except Exception as e:
            self._append_log(str(run_id), f"[web-runner] 取消失败: {type(e).__name__}: {_brief_text(str(e), 240)}")
        return {"ok": True, "run": self.get_run(run_id)}, 200

    def _artifact_candidates(self, run):
        input_path = Path(run.get("input_path") or "")
        output_base = _web_runner_output_base(run.get("output"))
        candidates = []
        for report_type in ("complete", "limited"):
            md_path, html_path, json_path = audit_artifact_paths(input_path, report_type, output_path=output_base)
            candidates.append((report_type, {"markdown": md_path, "html": html_path, "json": json_path}))
        if output_base:
            failed_paths = failed_audit_artifact_paths(input_path, output_dir=output_base.parent, output_stem=output_base.name)
        else:
            failed_paths = failed_audit_artifact_paths(input_path)
        candidates.append(("failed", {"markdown": failed_paths[0], "html": failed_paths[1], "json": failed_paths[2]}))
        return candidates

    def discover_artifacts(self, run_id):
        with self.lock:
            run = self.runs.get(str(run_id))
            if not run:
                return None
            run_copy = dict(run)
        discovered = {}
        report_type = ""
        summary = {}
        for candidate_type, paths in self._artifact_candidates(run_copy):
            existing = {kind: str(Path(path).resolve()) for kind, path in paths.items() if path and Path(path).exists()}
            if existing:
                discovered.update(existing)
                report_type = candidate_type
                json_path = existing.get("json")
                if json_path:
                    try:
                        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
                        summary = _web_runner_report_summary_from_payload(payload, candidate_type)
                    except Exception:
                        summary = {}
                break
        folder = None
        if discovered:
            first_path = Path(next(iter(discovered.values())))
            folder = str(first_path.parent.resolve())
        elif run_copy.get("output"):
            base = _web_runner_output_base(run_copy.get("output"))
            if base:
                folder = str(base.parent.resolve())
        else:
            input_path = Path(run_copy.get("input_path") or "")
            if input_path:
                folder = str((input_path if input_path.is_dir() else input_path.parent).resolve())
        if folder:
            discovered["folder"] = folder
        with self.lock:
            run = self.runs.get(str(run_id))
            if run:
                run["artifacts"] = discovered
                run["report_type"] = report_type
                run["summary"] = summary
                self._save_history()
                return _web_runner_safe_run(run)
        return None

    def artifact_target(self, run_id, kind):
        if kind not in {"html", "markdown", "json", "folder"}:
            return None, "unknown_artifact"
        with self.lock:
            run = self.runs.get(str(run_id))
            if not run:
                return None, "not_found"
            artifacts = dict(run.get("artifacts") or {})
        if kind not in artifacts:
            self.discover_artifacts(run_id)
            with self.lock:
                run = self.runs.get(str(run_id)) or {}
                artifacts = dict(run.get("artifacts") or {})
        raw_path = artifacts.get(kind)
        if not raw_path:
            return None, "not_recorded"
        path = Path(raw_path)
        if kind != "folder" and not path.exists():
            return None, "missing"
        return path, ""


def desktop_gui_write_llm_config(api_key, api_url, model, config_path=None):
    return _desktop_gui_write_llm_config(
        api_key,
        api_url,
        model,
        config_path=config_path,
        default_api_url=LLM_API_URL,
        default_model=LLM_MODEL,
    )


def desktop_gui_checked_config_snapshot(llm_preflight_runner=None, mineru_preflight_runner=None, timeout=6):
    return desktop_gui_checked_config_snapshot_from_namespace(
        globals(),
        llm_preflight_runner=llm_preflight_runner,
        mineru_preflight_runner=mineru_preflight_runner,
        timeout=timeout,
    )


def desktop_gui_followup_context(run):
    return desktop_gui_followup_context_from_namespace(globals(), run)


def desktop_gui_generate_followup_draft(kind, run, language="zh", tone="conservative", timeout=None):
    return desktop_gui_generate_followup_draft_from_namespace(
        globals(),
        kind,
        run,
        language=language,
        tone=tone,
        timeout=timeout,
    )


def create_desktop_root(tk_module):
    try:
        from tkinterdnd2 import TkinterDnD

        return TkinterDnD.Tk()
    except Exception:
        return tk_module.Tk()


class DesktopGuiApp:
    """Native tkinter shell around the same local run state used by Web Runner."""

    def __init__(self, root, state=None, tk_module=None, ttk_module=None, filedialog_module=None, messagebox_module=None, opener=None):
        self.root = root
        self.state = state or WebRunnerState()
        self.tk = tk_module
        self.ttk = ttk_module
        self.filedialog = filedialog_module
        self.messagebox = messagebox_module
        self.opener = opener or open_desktop_path
        self.active_run_id = None
        self.last_run = None
        self.log_offset = 0
        self._config_refresh_serial = 0
        self.artifact_paths = {}
        self.auto_opened_run_ids = set()
        self.config_path = desktop_gui_config_file_path()
        self._build()
        self.refresh_config()
        self.refresh_runs()

    def _build(self):
        tk = self.tk
        ttk = self.ttk
        self.root.title("Veritas Report Studio")
        self.root.geometry("1220x760")
        self.root.minsize(1040, 640)
        self._configure_style()

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.input_display_var = tk.StringVar(value="拖入论文或项目目录")
        self.output_display_var = tk.StringVar(value="选择报告目录")
        self.fresh_var = tk.BooleanVar(value=False)
        self.auto_open_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="待命")
        self.report_type_var = tk.StringVar(value="待生成")
        self.risk_var = tk.StringVar(value="待评估")
        self.summary_var = tk.StringVar(value="选择材料后开始分析。")
        self.stage_var = tk.StringVar(value="待命")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.log_title_var = tk.StringVar(value="运行日志")
        self.config_summary_var = tk.StringVar(value="状态")
        self.config_row_vars = []

        main = ttk.Frame(self.root, padding=14, style="App.TFrame")
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, width=330, padding=(16, 14), style="Sidebar.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_propagate(False)
        right = ttk.Frame(main, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self.drag_drop_available = self._enable_drag_drop_package()

        ttk.Label(left, text="Veritas", style="Brand.TLabel").pack(anchor=tk.W, pady=(0, 16))

        input_card = ttk.Frame(left, padding=12, style="SidebarCard.TFrame")
        input_card.pack(fill=tk.X, pady=(0, 10))
        input_pick = ttk.Button(input_card, textvariable=self.input_display_var, command=self.choose_file, style="Picker.TButton")
        input_pick.pack(fill=tk.X)
        self._register_drop_target(input_card, self._handle_input_drop)
        self._register_drop_target(input_pick, self._handle_input_drop)

        output_card = ttk.Frame(left, padding=12, style="SidebarCard.TFrame")
        output_card.pack(fill=tk.X, pady=(0, 10))
        output_pick = ttk.Button(output_card, textvariable=self.output_display_var, command=self.choose_output_directory, style="Picker.TButton")
        output_pick.pack(fill=tk.X, pady=(0, 8))
        output_buttons = ttk.Frame(output_card, style="SidebarCard.TFrame")
        output_buttons.pack(fill=tk.X)
        ttk.Button(output_buttons, text="更改", command=self.choose_output_directory, style="Secondary.TButton").pack(side=tk.LEFT)
        ttk.Button(output_buttons, text="清空", command=self.clear_output, style="Ghost.TButton").pack(side=tk.LEFT, padx=(8, 0))
        self._register_drop_target(output_card, self._handle_output_drop)
        self._register_drop_target(output_pick, self._handle_output_drop)

        options_card = ttk.Frame(left, padding=12, style="SidebarCard.TFrame")
        options_card.pack(fill=tk.X, pady=(0, 12))
        self._sidebar_checkbutton(options_card, "重新开始", self.fresh_var).pack(side=tk.LEFT)
        self._sidebar_checkbutton(options_card, "完成后打开报告", self.auto_open_var).pack(side=tk.LEFT, padx=(12, 0))

        action_buttons = ttk.Frame(left, style="Sidebar.TFrame")
        action_buttons.pack(fill=tk.X, pady=(0, 12))
        self.start_button = ttk.Button(action_buttons, text="开始分析", command=self.start_run, style="Primary.TButton")
        self.start_button.pack(fill=tk.X, pady=(0, 6))
        self.cancel_button = ttk.Button(action_buttons, text="停止任务", command=self.cancel_run, state=tk.DISABLED, style="Danger.TButton")
        self.cancel_button.pack(fill=tk.X, pady=(0, 6))
        self.retry_button = ttk.Button(action_buttons, text="重新运行", command=self.retry_run, state=tk.DISABLED, style="Secondary.TButton")
        self.retry_button.pack(fill=tk.X)

        config_card = ttk.Frame(left, padding=10, style="Config.TFrame")
        config_card.pack(fill=tk.BOTH, expand=True)
        config_head = ttk.Frame(config_card, style="Config.TFrame")
        config_head.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(config_head, text="能力", style="ConfigSection.TLabel").pack(side=tk.LEFT)
        ttk.Label(config_head, textvariable=self.config_summary_var, style="ConfigSummary.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(config_head, text="刷新", command=self.refresh_config, style="Tiny.TButton").pack(side=tk.RIGHT)
        ttk.Button(config_head, text="LLM 设置", command=self.open_llm_settings, style="Tiny.TButton").pack(side=tk.RIGHT, padx=(0, 6))
        self.config_rows_frame = ttk.Frame(config_card, style="Config.TFrame")
        self.config_rows_frame.pack(fill=tk.X)
        for index in range(len(DESKTOP_GUI_CONFIG_CAPABILITIES) + len(DESKTOP_GUI_CONFIG_DEPENDENCIES)):
            row = ttk.Frame(self.config_rows_frame, padding=(6, 4), style="ConfigChip.TFrame")
            row.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6 if index % 2 == 0 else 0), pady=(0, 4))
            self.config_rows_frame.columnconfigure(index % 2, weight=1)
            name_var = tk.StringVar()
            status_var = tk.StringVar()
            ttk.Label(row, textvariable=name_var, style="ConfigName.TLabel").pack(side=tk.LEFT)
            status_label = ttk.Label(row, textvariable=status_var, style="ConfigOk.TLabel")
            status_label.pack(side=tk.RIGHT)
            self.config_row_vars.append((name_var, status_var, status_label))

        report = ttk.Frame(right, padding=14, style="ReportCard.TFrame")
        report.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        report.columnconfigure(0, weight=1)
        metrics = ttk.Frame(report, style="ReportCard.TFrame")
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.columnconfigure(0, weight=1)
        metrics.columnconfigure(1, weight=1)
        metrics.columnconfigure(2, weight=1)
        status_card = ttk.Frame(metrics, padding=10, style="Metric.TFrame")
        status_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        type_card = ttk.Frame(metrics, padding=10, style="Metric.TFrame")
        type_card.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        risk_card = ttk.Frame(metrics, padding=10, style="Metric.TFrame")
        risk_card.grid(row=0, column=2, sticky="ew")
        ttk.Label(status_card, text="状态", style="MetricLabel.TLabel").pack(side=tk.LEFT)
        ttk.Label(status_card, textvariable=self.status_var, style="MetricValue.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(type_card, text="产物", style="MetricLabel.TLabel").pack(side=tk.LEFT)
        ttk.Label(type_card, textvariable=self.report_type_var, style="MetricValue.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(risk_card, text="信号", style="MetricLabel.TLabel").pack(side=tk.LEFT)
        ttk.Label(risk_card, textvariable=self.risk_var, style="MetricValue.TLabel").pack(side=tk.LEFT, padx=(8, 0))

        summary_row = ttk.Frame(report, style="ReportCard.TFrame")
        summary_row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        summary_row.columnconfigure(1, weight=1)
        ttk.Label(summary_row, text="摘要", style="CardTitle.TLabel").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(summary_row, textvariable=self.summary_var, wraplength=760, style="Summary.TLabel").grid(row=0, column=1, sticky="ew")
        progress_row = ttk.Frame(report, style="ReportCard.TFrame")
        progress_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        progress_row.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress_row, variable=self.progress_var, maximum=100, mode="determinate", style="Audit.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_row, textvariable=self.stage_var, style="Stage.TLabel").grid(row=0, column=1, sticky=tk.E, padx=(12, 0))

        artifact_frame = ttk.Frame(report, style="ReportCard.TFrame")
        artifact_frame.grid(row=3, column=0, sticky=tk.W, pady=(12, 0))
        self.artifact_buttons = {}
        for kind, label in DESKTOP_GUI_ARTIFACT_LABELS.items():
            button = ttk.Button(artifact_frame, text=label, command=lambda k=kind: self.open_artifact(k), state=tk.DISABLED, style="Artifact.TButton")
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.artifact_buttons[kind] = button
        self.followup_buttons = {}
        for kind, label in DESKTOP_GUI_FOLLOWUP_LABELS.items():
            button = ttk.Button(artifact_frame, text=label, command=lambda k=kind: self.generate_followup(k), state=tk.DISABLED, style="Artifact.TButton")
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.followup_buttons[kind] = button

        log_frame = ttk.Frame(right, padding=12, style="LogCard.TFrame")
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        ttk.Label(log_frame, textvariable=self.log_title_var, style="LogTitle.TLabel").grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=28, wrap=tk.WORD, bd=0, relief=tk.FLAT)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        self.log_text.configure(
            bg="#101317",
            fg="#d9e0ea",
            insertbackground="#d9e0ea",
            selectbackground="#30445f",
            font=("SF Mono", 10),
            padx=12,
            pady=12,
        )
        self._set_log_editable(False)

    def _configure_style(self):
        ttk = self.ttk
        try:
            ttk.Style().theme_use("clam")
        except Exception:
            pass
        style = ttk.Style()
        colors = {
            "app": "#f0f2f6",
            "sidebar": "#f8f9fb",
            "sidebar_card": "#ffffff",
            "config": "#ffffff",
            "text": "#111827",
            "muted": "#7b8190",
            "card": "#ffffff",
            "metric": "#f7f8fc",
            "accent": "#0071e3",
            "accent_dark": "#005bb5",
            "danger": "#ff453a",
            "danger_dark": "#d92d25",
            "log": "#101317",
        }
        self.root.configure(bg=colors["app"])
        style.configure("App.TFrame", background=colors["app"])
        style.configure("Sidebar.TFrame", background=colors["sidebar"])
        style.configure("SidebarCard.TFrame", background=colors["sidebar_card"], relief="flat", borderwidth=0)
        style.configure("Config.TFrame", background=colors["config"], relief="flat", borderwidth=0)
        style.configure("ConfigChip.TFrame", background="#f8f9fc", relief="flat", borderwidth=0)
        style.configure("ReportCard.TFrame", background=colors["card"], relief="flat", borderwidth=0)
        style.configure("Metric.TFrame", background=colors["metric"], relief="flat")
        style.configure("LogCard.TFrame", background=colors["log"], relief="flat")
        style.configure("CloseDot.TLabel", background=colors["sidebar"], foreground="#ff5f57", font=("Avenir Next", 12, "bold"))
        style.configure("MinDot.TLabel", background=colors["sidebar"], foreground="#ffbd2e", font=("Avenir Next", 12, "bold"))
        style.configure("ZoomDot.TLabel", background=colors["sidebar"], foreground="#28c840", font=("Avenir Next", 12, "bold"))
        style.configure("Brand.TLabel", background=colors["sidebar"], foreground=colors["text"], font=("Avenir Next", 23, "bold"))
        style.configure("BrandSub.TLabel", background=colors["sidebar"], foreground=colors["accent"], font=("Avenir Next", 13, "bold"))
        style.configure("SidebarHint.TLabel", background=colors["sidebar"], foreground=colors["muted"], font=("Avenir Next", 10))
        style.configure("SidebarSection.TLabel", background=colors["sidebar_card"], foreground=colors["muted"], font=("Avenir Next", 8, "bold"))
        style.configure("ConfigSection.TLabel", background=colors["config"], foreground=colors["muted"], font=("Avenir Next", 8, "bold"))
        style.configure("ConfigSummary.TLabel", background=colors["config"], foreground=colors["text"], font=("Avenir Next", 8, "bold"))
        style.configure("ConfigName.TLabel", background="#f8f9fc", foreground=colors["text"], font=("Avenir Next", 8))
        style.configure("ConfigOk.TLabel", background="#f8f9fc", foreground="#2e7d32", font=("Avenir Next", 8, "bold"))
        style.configure("ConfigWarn.TLabel", background="#f8f9fc", foreground="#b45309", font=("Avenir Next", 8, "bold"))
        style.configure("PageTitle.TLabel", background=colors["app"], foreground=colors["text"], font=("Avenir Next", 25, "bold"))
        style.configure("PageSub.TLabel", background=colors["app"], foreground=colors["muted"], font=("Avenir Next", 10))
        style.configure("StatusPill.TLabel", background="#eaf2ff", foreground="#0f5fb8", font=("Avenir Next", 10, "bold"), padding=(12, 6))
        style.configure("CardTitle.TLabel", background=colors["card"], foreground=colors["text"], font=("Avenir Next", 12, "bold"))
        style.configure("Summary.TLabel", background=colors["card"], foreground="#33363d", font=("Avenir Next", 11))
        style.configure("MetricLabel.TLabel", background=colors["metric"], foreground=colors["muted"], font=("Avenir Next", 8, "bold"))
        style.configure("MetricValue.TLabel", background=colors["metric"], foreground=colors["text"], font=("Avenir Next", 14, "bold"))
        style.configure("Stage.TLabel", background=colors["card"], foreground=colors["muted"], font=("Avenir Next", 10, "bold"))
        style.configure("Audit.Horizontal.TProgressbar", troughcolor="#e6e8ed", background=colors["accent"], bordercolor="#e6e8ed", lightcolor=colors["accent"], darkcolor=colors["accent"], thickness=9)
        style.configure("LogTitle.TLabel", background=colors["log"], foreground="#f5f5f7", font=("Avenir Next", 12, "bold"))
        style.configure("Sidebar.TCheckbutton", background=colors["sidebar_card"], foreground=colors["text"], font=("Avenir Next", 9))
        style.map("Sidebar.TCheckbutton", background=[("active", colors["sidebar_card"])], foreground=[("active", colors["text"])])
        style.configure("Path.TEntry", fieldbackground="#ffffff", foreground=colors["text"], padding=6)
        style.configure("Picker.TButton", background="#f8f9fc", foreground="#252b36", font=("Avenir Next", 10, "bold"), padding=(10, 16), borderwidth=0)
        style.map("Picker.TButton", background=[("active", "#eef6ff"), ("disabled", "#e4e5e8")], foreground=[("disabled", "#8c8c91")])
        style.configure("Primary.TButton", background=colors["accent"], foreground="#ffffff", font=("Avenir Next", 11, "bold"), padding=(12, 9), borderwidth=0)
        style.map("Primary.TButton", background=[("active", colors["accent_dark"]), ("disabled", "#8a9a93")])
        style.configure("Secondary.TButton", background="#f8f9fc", foreground=colors["text"], font=("Avenir Next", 9, "bold"), padding=(10, 7), borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#e9eef7"), ("disabled", "#d6d7d9")], foreground=[("disabled", "#8c8c91")])
        style.configure("Ghost.TButton", background=colors["sidebar_card"], foreground=colors["accent"], font=("Avenir Next", 9, "bold"), padding=(9, 7), borderwidth=0)
        style.map("Ghost.TButton", background=[("active", "#edf4ff"), ("disabled", "#d6d7d9")])
        style.configure("Tiny.TButton", background="#f8f9fc", foreground=colors["accent"], font=("Avenir Next", 8, "bold"), padding=(6, 3), borderwidth=0)
        style.map("Tiny.TButton", background=[("active", "#edf4ff"), ("disabled", "#d6d7d9")])
        style.configure("Danger.TButton", background=colors["danger"], foreground="#ffffff", font=("Avenir Next", 9, "bold"), padding=(10, 7), borderwidth=0)
        style.map("Danger.TButton", background=[("active", colors["danger_dark"]), ("disabled", "#d6d7d9")])
        style.configure("Artifact.TButton", background="#eef6ff", foreground="#1f4f7a", font=("Avenir Next", 9, "bold"), padding=(10, 7), borderwidth=0)
        style.map("Artifact.TButton", background=[("active", "#e6f0ff"), ("disabled", "#e4e5e8")], foreground=[("disabled", "#8c8c91")])

    def _sidebar_checkbutton(self, parent, text, variable):
        tk = self.tk
        button = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            indicatoron=False,
            onvalue=True,
            offvalue=False,
            bg="#f3f6fb",
            activebackground="#eaf2ff",
            fg="#111827",
            activeforeground="#111827",
            selectcolor="#0071e3",
            font=("Avenir Next", 9, "bold"),
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            overrelief=tk.FLAT,
            padx=12,
            pady=7,
        )

        def sync(*_args):
            selected = bool(variable.get())
            button.configure(
                bg="#0071e3" if selected else "#f3f6fb",
                activebackground="#005bb5" if selected else "#eaf2ff",
                fg="#ffffff" if selected else "#111827",
                activeforeground="#ffffff" if selected else "#111827",
            )

        try:
            trace_id = variable.trace_add("write", sync)
            button._veritas_trace_id = trace_id
        except Exception:
            pass
        sync()
        return button

    def _render_config_snapshot(self, snapshot):
        if hasattr(self, "config_summary_var"):
            self.config_summary_var.set(snapshot.get("summary") or "不可用")
        rows = snapshot.get("rows") or []
        for index, row_vars in enumerate(getattr(self, "config_row_vars", [])):
            name_var, status_var, status_label = row_vars
            row = rows[index] if index < len(rows) else None
            if not row:
                name_var.set("")
                status_var.set("")
                status_label.configure(style="ConfigOk.TLabel")
                continue
            name_var.set(row["label"])
            status_var.set(row["status"])
            status_label.configure(style="ConfigOk.TLabel" if row.get("ok") else "ConfigWarn.TLabel")

    def _current_llm_config(self):
        return load_runtime_config(verbose=False).text_llm

    def _save_llm_settings(self, window, api_key_var, api_url_var, model_var):
        api_key = api_key_var.get().strip()
        api_url = api_url_var.get().strip()
        model = model_var.get().strip()
        if not api_key or not api_url or not model:
            self.messagebox.showerror("配置不完整", "请填写 API Key、API URL 和模型名称。")
            return
        try:
            path = desktop_gui_write_llm_config(api_key, api_url, model, config_path=getattr(self, "config_path", None))
            runtime_config = load_runtime_config(verbose=False)
            apply_runtime_config(runtime_config)
            self.refresh_config()
            window.destroy()
            self.messagebox.showinfo("已保存", f"LLM 设置已保存到 {path}。")
        except Exception as e:
            self.messagebox.showerror("保存失败", f"{type(e).__name__}: {_brief_text(str(e), 240)}")

    def open_llm_settings(self):
        tk = self.tk
        ttk = self.ttk
        try:
            llm = self._current_llm_config()
        except Exception:
            llm = CapabilityConfig("text_llm", api_url=LLM_API_URL, model=LLM_MODEL)
        window = tk.Toplevel(self.root)
        window.title("LLM 设置")
        window.transient(self.root)
        try:
            window.resizable(False, False)
        except Exception:
            pass
        frame = ttk.Frame(window, padding=18, style="App.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="文本 LLM", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        api_key_var = tk.StringVar(value=llm.api_key or "")
        api_url_var = tk.StringVar(value=llm.api_url or LLM_API_URL)
        model_var = tk.StringVar(value=llm.model or LLM_MODEL)

        fields = [
            ("API Key", api_key_var, "*"),
            ("API URL", api_url_var, ""),
            ("模型", model_var, ""),
        ]
        for row_index, (label, variable, show) in enumerate(fields, start=1):
            ttk.Label(frame, text=label, style="MetricLabel.TLabel").grid(row=row_index, column=0, sticky=tk.W, pady=(0, 8), padx=(0, 10))
            entry = ttk.Entry(frame, textvariable=variable, width=46, show=show)
            entry.grid(row=row_index, column=1, sticky="ew", pady=(0, 8))
            if row_index == 1:
                entry.focus_set()
        buttons = ttk.Frame(frame, style="App.TFrame")
        buttons.grid(row=4, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(buttons, text="取消", command=window.destroy, style="Secondary.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="保存",
            command=lambda: self._save_llm_settings(window, api_key_var, api_url_var, model_var),
            style="Primary.TButton",
        ).pack(side=tk.LEFT)

    def _set_log_editable(self, editable):
        try:
            self.log_text.configure(state=self.tk.NORMAL if editable else self.tk.DISABLED)
        except Exception:
            pass

    def _reset_progress(self, label="待命"):
        if hasattr(self, "progress_var"):
            self.progress_var.set(0.0)
        if hasattr(self, "stage_var"):
            self.stage_var.set(label)

    def _update_progress_from_line(self, line):
        progress = desktop_gui_progress_from_log_line(line)
        if not progress:
            return False
        if hasattr(self, "progress_var"):
            self.progress_var.set(progress["percent"])
        if hasattr(self, "stage_var"):
            self.stage_var.set(progress["label"])
        return True

    def _clear_log_text(self):
        if hasattr(self, "log_title_var"):
            self.log_title_var.set("运行日志")
        self._set_log_editable(True)
        self.log_text.delete("1.0", self.tk.END)
        self._set_log_editable(False)

    def _replace_log_text(self, title, content):
        if hasattr(self, "log_title_var"):
            self.log_title_var.set(title)
        self._set_log_editable(True)
        try:
            self.log_text.delete("1.0", self.tk.END)
            self.log_text.insert(self.tk.END, str(content or ""))
            self.log_text.see("1.0")
        finally:
            self._set_log_editable(False)

    def _render_artifact_in_log(self, kind, path):
        label = DESKTOP_GUI_ARTIFACT_LABELS.get(kind, kind)
        content = desktop_gui_artifact_preview(path, kind)
        self._replace_log_text(f"报告预览 · {label}", content)

    def _display_path_text(self, raw_path, placeholder):
        text = str(raw_path or "").strip()
        if not text:
            return placeholder
        try:
            path = Path(text).expanduser()
            if path.name == "audit_report":
                path = path.parent
            label = str(path)
        except Exception:
            label = text
        if len(label) <= 36:
            return label
        return "..." + label[-33:]

    def _set_input_path(self, path):
        path_text = str(Path(path).expanduser())
        self.input_var.set(path_text)
        if hasattr(self, "input_display_var"):
            self.input_display_var.set(self._display_path_text(path_text, "拖入论文或项目目录"))

    def _set_output_path(self, output_stem):
        output_text = str(output_stem or "").strip()
        self.output_var.set(output_text)
        if hasattr(self, "output_display_var"):
            self.output_display_var.set(self._display_path_text(output_text, "选择报告目录"))

    def clear_output(self):
        self._set_output_path("")

    def _enable_drag_drop_package(self):
        try:
            self.root.tk.call("package", "require", "tkdnd")
            return True
        except Exception:
            return False

    def _register_drop_target(self, widget, handler):
        if not getattr(self, "drag_drop_available", False):
            return
        try:
            self.root.tk.call("tkdnd::drop_target", "register", widget._w, "DND_Files")
            callback = widget.register(lambda data: handler(data))
            self.root.tk.call("bind", widget._w, "<<Drop>>", f"{callback} %D")
        except Exception:
            pass

    def _path_from_drop_data(self, data):
        raw = str(data or "").strip()
        if not raw:
            return ""
        try:
            items = self.root.tk.splitlist(raw)
        except Exception:
            items = [raw]
        if not items:
            return ""
        item = str(items[0]).strip().strip("{}")
        if item.lower().startswith("file://"):
            return dropped_local_path_from_uri_text(item)
        return item

    def _handle_input_drop(self, data):
        path = self._path_from_drop_data(data)
        if path:
            self._set_input_path(path)

    def _handle_output_drop(self, data):
        path = self._path_from_drop_data(data)
        if not path:
            return
        dropped = Path(path).expanduser()
        output_dir = dropped.parent if dropped.is_file() else dropped
        self._set_output_path(output_dir / "audit_report")

    def choose_file(self):
        selected = self.filedialog.askopenfilename(title="选择材料文件")
        if selected:
            self._set_input_path(selected)

    def choose_directory(self):
        selected = self.filedialog.askdirectory(title="选择材料目录", mustexist=True)
        if selected:
            self._set_input_path(selected)

    def choose_output_directory(self):
        selected = self.filedialog.askdirectory(title="选择报告目录", mustexist=False)
        if selected:
            self._set_output_path(Path(selected).expanduser() / "audit_report")

    def refresh_config(self):
        self._config_refresh_serial = getattr(self, "_config_refresh_serial", 0) + 1
        serial = self._config_refresh_serial
        try:
            config = web_runner_config_status()
            self._render_config_snapshot(desktop_gui_config_snapshot(config, preflight_results={"text_llm": {"status": "检测中", "ok": False}}))
        except Exception as e:
            self._render_config_snapshot({"summary": f"{type(e).__name__}: {_brief_text(str(e), 120)}", "rows": []})
            return

        def worker():
            try:
                snapshot = desktop_gui_checked_config_snapshot()
            except Exception as e:
                snapshot = {"summary": f"{type(e).__name__}: {_brief_text(str(e), 120)}", "rows": []}

            def apply_snapshot():
                if serial == getattr(self, "_config_refresh_serial", 0):
                    self._render_config_snapshot(snapshot)

            try:
                self.root.after(0, apply_snapshot)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def refresh_runs(self):
        runs = self.state.list_runs()
        running = next((run for run in runs if run.get("status") == "running"), None)
        if running and not self.active_run_id:
            self.active_run_id = running.get("id")
            self.log_offset = 0
            self._clear_log_text()
            self.poll_run()
            return
        if runs and not self.active_run_id:
            latest = runs[0]
            self.last_run = latest
            self.log_offset = 0
            self._clear_log_text()
            self._reset_progress()
            self.render_run(latest)
            self._append_logs_since(latest.get("id"))
            self.retry_button.configure(state=self.tk.NORMAL if latest.get("input_path") else self.tk.DISABLED)

    def start_run(self):
        input_path = self.input_var.get().strip()
        if not input_path:
            self.messagebox.showerror("缺少材料", "请选择文件或项目目录。")
            return
        result, status = desktop_gui_start_run(self.state, input_path, self.output_var.get(), self.fresh_var.get())
        run = result.get("run") if isinstance(result, dict) else None
        if status != 200 or not run:
            message = result.get("message") or result.get("error") or "启动失败"
            self.status_var.set(message)
            self.messagebox.showerror("启动失败", message)
            return
        self.active_run_id = run.get("id")
        self.last_run = run
        self.log_offset = 0
        self.start_button.configure(state=self.tk.DISABLED)
        self.cancel_button.configure(state=self.tk.NORMAL)
        self.retry_button.configure(state=self.tk.DISABLED)
        self._clear_log_text()
        self._reset_progress("启动中")
        self.render_run(run)
        self.poll_run()

    def cancel_run(self):
        if not self.active_run_id:
            return
        self.state.cancel_run(self.active_run_id)
        self.poll_run()

    def retry_run(self):
        run = self.last_run or {}
        input_path = run.get("input_path") or self.input_var.get()
        if not input_path:
            return
        self.input_var.set(input_path)
        if hasattr(self, "input_display_var"):
            self.input_display_var.set(self._display_path_text(input_path, "拖入论文或项目目录"))
        self._set_output_path(run.get("output") or self.output_var.get())
        self.fresh_var.set(bool(run.get("fresh")))
        self.start_run()

    def poll_run(self):
        if not self.active_run_id:
            return
        self._append_logs_since(self.active_run_id)
        run = self.state.get_run(self.active_run_id)
        if run:
            self.render_run(run)
            if run.get("status") != "running":
                refreshed = self.state.discover_artifacts(self.active_run_id) if self.active_run_id else None
                if refreshed:
                    run = refreshed
                    self.render_run(run)
                self._append_logs_since(run.get("id"))
                self._maybe_auto_open_completed_report(run)
                self.active_run_id = None
                self.start_button.configure(state=self.tk.NORMAL)
                self.cancel_button.configure(state=self.tk.DISABLED)
                self.retry_button.configure(state=self.tk.NORMAL if run.get("input_path") else self.tk.DISABLED)
                return
        self.root.after(1000, self.poll_run)

    def _append_logs_since(self, run_id):
        if not run_id:
            return
        logs = self.state.logs_since(run_id, self.log_offset)
        if not logs:
            return
        self.log_offset = logs.get("offset", self.log_offset)
        lines = logs.get("lines") or []
        if not lines:
            return
        self._set_log_editable(True)
        try:
            for line in lines:
                self._update_progress_from_line(line)
                self.log_text.insert(self.tk.END, str(line) + "\n")
            self.log_text.see(self.tk.END)
        finally:
            self._set_log_editable(False)

    def render_run(self, run):
        self.last_run = run or self.last_run
        view = desktop_gui_run_summary(run)
        self.status_var.set(view["status_label"])
        self.report_type_var.set(view["report_type_label"])
        self.risk_var.set(view["risk_label"])
        self.summary_var.set(view["summary"] or "完成后显示摘要。")
        if run and run.get("status") == "succeeded" and hasattr(self, "progress_var"):
            self.progress_var.set(100.0)
            self.stage_var.set("已完成")
        elif run and run.get("status") in {"failed", "canceled"} and hasattr(self, "stage_var"):
            if not self.stage_var.get() or self.stage_var.get() == "待命":
                self.stage_var.set(view["status_label"])
        self.artifact_paths = view["artifacts"]
        for kind, button in self.artifact_buttons.items():
            button.configure(state=self.tk.NORMAL if kind in self.artifact_paths else self.tk.DISABLED)
        followup_enabled = bool(run and run.get("status") == "succeeded" and self.artifact_paths.get("json"))
        for button in getattr(self, "followup_buttons", {}).values():
            button.configure(state=self.tk.NORMAL if followup_enabled else self.tk.DISABLED)

    def open_artifact(self, kind):
        path = self.artifact_paths.get(kind)
        if not path:
            return
        try:
            if kind in {"html", "markdown", "json"}:
                self._render_artifact_in_log(kind, path)
            else:
                self.opener(path)
        except Exception as e:
            self.messagebox.showerror("打开失败", f"{type(e).__name__}: {_brief_text(str(e), 240)}")

    def _current_followup_run(self):
        run = dict(self.last_run or {})
        artifacts = dict(run.get("artifacts") or {})
        artifacts.update(getattr(self, "artifact_paths", {}) or {})
        run["artifacts"] = artifacts
        return run

    def _set_followup_buttons_state(self, state):
        for button in getattr(self, "followup_buttons", {}).values():
            button.configure(state=state)

    def generate_followup(self, kind):
        label = DESKTOP_GUI_FOLLOWUP_LABELS.get(kind, kind)
        run = self._current_followup_run()
        try:
            desktop_gui_followup_context(run)
        except Exception as e:
            self.messagebox.showerror("无法生成草稿", f"{type(e).__name__}: {_brief_text(str(e), 240)}")
            return
        self._set_followup_buttons_state(self.tk.DISABLED)
        if hasattr(self, "stage_var"):
            self.stage_var.set(f"{label} 生成中")

        def worker():
            try:
                result = desktop_gui_generate_followup_draft(kind, run)
                error = None
            except Exception as e:
                result = None
                error = e

            def apply_result():
                self._set_followup_buttons_state(self.tk.NORMAL)
                if error is not None:
                    if hasattr(self, "stage_var"):
                        self.stage_var.set("草稿生成失败")
                    self.messagebox.showerror("生成失败", f"{type(error).__name__}: {_brief_text(str(error), 240)}")
                    return
                self._replace_log_text(f"草稿 · {label}", result.get("text") or "")
                if hasattr(self, "stage_var"):
                    self.stage_var.set("草稿已生成")
                draft_path = (result.get("paths") or {}).get("draft_path")
                if self.messagebox:
                    self.messagebox.showinfo("已生成", f"草稿已保存: {draft_path}")

            try:
                self.root.after(0, apply_result)
            except Exception:
                apply_result()

        threading.Thread(target=worker, daemon=True).start()

    def _maybe_auto_open_completed_report(self, run):
        if not run or run.get("status") != "succeeded" or not self.auto_open_var.get():
            return
        run_id = str(run.get("id") or "")
        html_path = (run.get("artifacts") or {}).get("html")
        if not run_id or not html_path or run_id in self.auto_opened_run_ids:
            return
        self.auto_opened_run_ids.add(run_id)
        try:
            self._render_artifact_in_log("html", html_path)
        except Exception as e:
            self.messagebox.showerror("打开失败", f"{type(e).__name__}: {_brief_text(str(e), 240)}")


def run_desktop_gui(history_path=None):
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as e:
        print(f"无法启动桌面 GUI：tkinter 不可用: {type(e).__name__}: {_brief_text(str(e), 240)}")
        return 1
    try:
        root = create_desktop_root(tk)
        DesktopGuiApp(root, state=WebRunnerState(history_path=history_path), tk_module=tk, ttk_module=ttk, filedialog_module=filedialog, messagebox_module=messagebox)
        root.mainloop()
        return 0
    except Exception as e:
        print(f"无法启动桌面 GUI：{type(e).__name__}: {_brief_text(str(e), 240)}")
        return 1


def gui_main():
    apply_runtime_config(load_runtime_config())
    return run_desktop_gui()


def render_web_runner_page():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Veritas Web Runner</title>
<style>
:root { color-scheme: light; --bg:#f5f5f3; --panel:#ffffff; --line:#d8d8d3; --text:#191919; --muted:#6a6a64; --accent:#155e75; --danger:#b42318; --ok:#237a4b; --warn:#9a5b00; --soft:#f0f7f8; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif; font-size:14px; letter-spacing:0; }
header { height:54px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; border-bottom:1px solid var(--line); background:#fff; }
h1 { font-size:18px; margin:0; font-weight:750; }
main { display:grid; grid-template-columns:minmax(360px, 520px) minmax(420px, 1fr); gap:16px; padding:16px; max-width:1440px; margin:0 auto; }
section { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
h2 { font-size:14px; margin:0 0 12px; font-weight:750; }
label { display:block; color:var(--muted); font-size:12px; margin:10px 0 5px; }
input[type="text"] { width:100%; min-height:38px; border:1px solid var(--line); border-radius:6px; padding:8px 10px; font:inherit; background:#fff; color:var(--text); }
input[readonly] { background:#f7f7f5; color:#2f2f2c; cursor:default; }
.drop-zone { border:1px dashed var(--line); border-radius:8px; padding:10px; background:#fbfbfa; transition:border-color .12s ease, background .12s ease; }
.drop-zone.dragover { border-color:var(--accent); background:#edf7f8; }
.drop-zone input[type="text"] { margin-top:5px; }
.drop-hint { min-height:18px; margin-top:6px; }
.path-row { display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:8px; align-items:end; }
.path-row.output { grid-template-columns:minmax(0,1fr) auto; margin-top:5px; }
.row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.actions { margin-top:12px; display:flex; gap:8px; }
button, .linkbtn { min-height:36px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--text); padding:7px 12px; font:inherit; font-weight:650; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
button.danger { border-color:#e3aaa5; color:var(--danger); }
button:disabled { opacity:.55; cursor:not-allowed; }
.status { display:inline-flex; min-height:26px; align-items:center; padding:3px 8px; border-radius:999px; border:1px solid var(--line); color:var(--muted); font-size:12px; }
.status.succeeded { color:var(--ok); border-color:#9bc7ad; }
.status.failed, .status.canceled { color:var(--danger); border-color:#e3aaa5; }
.hero-strip { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-bottom:12px; }
.step { border:1px solid var(--line); border-radius:6px; padding:8px; background:#fbfbfa; min-height:58px; }
.step span { display:block; color:var(--muted); font-size:12px; }
.step strong { display:block; margin-top:3px; font-size:13px; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.cell { border:1px solid var(--line); border-radius:6px; padding:8px; min-height:54px; overflow-wrap:anywhere; }
.cell span { display:block; color:var(--muted); font-size:12px; }
.cell strong { display:block; margin-top:3px; font-size:13px; }
#log { height:430px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#161616; color:#f4f4f0; border-radius:6px; padding:12px; font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.run { border-top:1px solid var(--line); padding:10px 0; }
.run:first-child { border-top:0; padding-top:0; }
.run-title { display:flex; justify-content:space-between; gap:8px; align-items:center; }
.run path, code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.muted { color:var(--muted); font-size:12px; overflow-wrap:anywhere; }
.links { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
.check { display:flex; align-items:center; gap:7px; margin-top:10px; color:var(--text); }
.current-card { border:1px solid var(--line); border-radius:6px; padding:9px; margin-bottom:10px; min-height:58px; }
.current-card span { display:block; color:var(--muted); font-size:12px; }
.current-card strong { display:block; margin-top:3px; overflow-wrap:anywhere; }
.current-actions { display:flex; gap:6px; flex-wrap:wrap; margin:8px 0 10px; min-height:36px; }
.report-panel { border:1px solid var(--line); border-radius:8px; padding:10px; margin:0 0 10px; background:var(--soft); }
.report-panel.failed, .report-panel.canceled { background:#fff7f6; }
.report-panel.succeeded, .report-panel.complete, .report-panel.limited { background:#f3faf6; }
.report-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
.report-head h3 { margin:0; font-size:14px; }
.report-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.report-cell { border:1px solid rgba(0,0,0,.08); border-radius:6px; padding:8px; background:rgba(255,255,255,.72); overflow-wrap:anywhere; }
.report-cell span { display:block; color:var(--muted); font-size:12px; }
.report-cell strong { display:block; margin-top:3px; font-size:13px; }
.report-summary { margin:8px 0 0; color:#2f2f2c; line-height:1.55; overflow-wrap:anywhere; }
.feedback { min-height:34px; border:1px solid var(--line); border-radius:6px; padding:8px; margin-bottom:10px; background:#fbfbfa; color:#2f2f2c; overflow-wrap:anywhere; }
.feedback.failed { border-color:#e3aaa5; color:var(--danger); background:#fff7f6; }
.feedback.succeeded { border-color:#9bc7ad; color:var(--ok); background:#f3faf6; }
@media (max-width:900px) { main { grid-template-columns:1fr; padding:10px; } header { padding:0 12px; } #log { height:320px; } .hero-strip, .report-grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header><h1>Veritas Web Runner</h1><span id="topStatus" class="status">local</span></header>
<main>
  <div>
    <section>
      <h2>审查任务</h2>
      <div class="hero-strip" aria-label="workflow">
        <div class="step"><span>1. 输入</span><strong>选择论文文件或项目目录</strong></div>
        <div class="step"><span>2. 审查</span><strong>本地启动正式 CLI 流程</strong></div>
        <div class="step"><span>3. 输出</span><strong>直接打开生成报告</strong></div>
      </div>
      <div id="inputDropZone" class="drop-zone">
        <label for="inputPath">输入路径 / 拖拽区域</label>
        <div class="path-row">
          <input id="inputPath" type="text" autocomplete="off" readonly placeholder="/path/to/paper-or-folder">
          <button id="pickFileBtn" type="button">文件</button>
          <button id="pickDirectoryBtn" type="button">目录</button>
        </div>
        <div id="dropHint" class="muted drop-hint">拖拽文件或目录到这里</div>
      </div>
      <label for="outputPath">输出路径</label>
      <div class="path-row output">
        <input id="outputPath" type="text" autocomplete="off" readonly placeholder="">
        <button id="pickOutputBtn" type="button">输出</button>
      </div>
      <label class="check"><input id="fresh" type="checkbox"> 从头重跑</label>
      <div class="actions">
        <button id="startBtn" class="primary">Start</button>
        <button id="cancelBtn" class="danger" disabled>Cancel</button>
      </div>
    </section>
    <section style="margin-top:16px">
      <h2>配置状态</h2>
      <div id="config" class="grid"></div>
    </section>
  </div>
  <div>
    <section>
      <div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">当前运行</h2><span id="runStatus" class="status">idle</span></div>
      <div id="currentRun" class="current-card"><span>输入</span><strong>No active run</strong></div>
      <div id="currentOutput" class="current-card"><span>输出</span><strong></strong></div>
      <div id="runFeedback" class="feedback">选择输入后点击 Start，生成的报告会在这里显示。</div>
      <div id="reportPanel" class="report-panel">
        <div class="report-head"><h3>报告输出</h3><span id="reportState" class="status">pending</span></div>
        <div class="report-grid">
          <div class="report-cell"><span>报告类型</span><strong id="reportType">待生成</strong></div>
          <div class="report-cell"><span>风险级别</span><strong id="reportRisk">待生成</strong></div>
          <div class="report-cell"><span>输出目录</span><strong id="reportFolder">待生成</strong></div>
        </div>
        <p id="reportSummary" class="report-summary">报告生成后会显示摘要和打开入口。</p>
        <div id="currentActions" class="current-actions"></div>
      </div>
      <div id="log" aria-label="live log"></div>
    </section>
    <section style="margin-top:16px">
      <h2>最近运行</h2>
      <div id="runs"></div>
    </section>
  </div>
</main>
<script>
const $ = (id) => document.getElementById(id);
let activeRunId = null;
let logOffset = 0;
let timer = null;
let selectedInputKind = '';
let lastRun = null;
async function api(path, options={}) {
  const res = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}
function setStatus(text, cls='') {
  const el = $('runStatus');
  el.className = 'status ' + cls;
  el.textContent = text;
}
function setFeedback(text, cls='') {
  const el = $('runFeedback');
  if (!el) return;
  el.className = 'feedback ' + cls;
  el.textContent = text || '选择输入后点击 Start，生成的报告会在这里显示。';
}
function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function pathSeparator(path) {
  return String(path || '').includes('\\\\') ? '\\\\' : '/';
}
function trimPath(path) {
  return String(path || '').trim().replace(/[\\\\/]+$/, '');
}
function pathBaseName(path) {
  const cleaned = trimPath(path);
  const sep = pathSeparator(cleaned);
  return cleaned.split(sep).filter(Boolean).pop() || 'audit_project';
}
function pathParent(path) {
  const cleaned = trimPath(path);
  const sep = pathSeparator(cleaned);
  const parts = cleaned.split(sep);
  parts.pop();
  const parent = parts.join(sep);
  if (parent) return parent;
  return cleaned.startsWith(sep) ? sep : '.';
}
function joinPath(...parts) {
  const filtered = parts.map(p => String(p || '')).filter(Boolean);
  const sep = filtered.some(p => p.includes('\\\\')) ? '\\\\' : '/';
  const joined = filtered.join(sep);
  return sep === '\\\\' ? joined.replace(/\\\\{2,}/g, '\\\\') : joined.replace(/\\/{2,}/g, '/');
}
function stripExtension(name) {
  const dot = String(name || '').lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}
function safeProjectName(name) {
  return String(name || 'audit_project').replace(/[<>:"/\\\\|?*\\x00-\\x1f]+/g, '_').replace(/[ .]+$/g, '') || 'audit_project';
}
function timestampForOutput(date = new Date()) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}
function defaultOutputStemForInput(inputPath, kind = selectedInputKind, date = new Date()) {
  const cleaned = trimPath(inputPath);
  if (!cleaned) return '';
  const base = pathBaseName(cleaned);
  const project = safeProjectName(kind === 'directory' ? base : stripExtension(base));
  return joinPath(pathParent(cleaned), `${project}_${timestampForOutput(date)}`, 'audit_report');
}
function localPathFromFileUri(rawUri) {
  const uri = String(rawUri || '').trim();
  if (!uri.toLowerCase().startsWith('file://')) return '';
  try {
    const parsed = new URL(uri);
    if (parsed.protocol !== 'file:') return '';
    return decodeURIComponent(parsed.pathname || '').replace(/^\\/([A-Za-z]:\\/)/, '$1');
  } catch (_e) {
    return decodeURIComponent(uri.replace(/^file:\\/\\//i, ''));
  }
}
function droppedPathFromUriText(text) {
  const lines = String(text || '').split(/\\r?\\n/).map(line => line.trim()).filter(Boolean);
  for (const line of lines) {
    if (line.startsWith('#')) continue;
    const path = localPathFromFileUri(line);
    if (path) return path;
  }
  return '';
}
function droppedPathFromTransferText(dataTransfer) {
  if (!dataTransfer || !dataTransfer.getData) return '';
  for (const type of ['text/uri-list', 'text/plain']) {
    const path = droppedPathFromUriText(dataTransfer.getData(type));
    if (path) return path;
  }
  return '';
}
function setSelectedInputPath(path, kind = '') {
  selectedInputKind = kind;
  $('inputPath').value = path;
  $('dropHint').textContent = path;
  $('outputPath').value = defaultOutputStemForInput(path, kind);
  $('outputPath').dataset.userSelected = '';
  $('inputPath').dispatchEvent(new Event('change', {bubbles: true}));
}
function droppedPathInfoFromDataTransfer(dataTransfer) {
  const uriPath = droppedPathFromTransferText(dataTransfer);
  if (uriPath) return {path: uriPath, kind: 'file'};
  const items = Array.from((dataTransfer && dataTransfer.items) || []);
  for (const item of items) {
    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
    if (entry) {
      const entryPath = entry.fullPath && entry.fullPath !== '/' ? entry.fullPath.replace(/^\\//, '') : entry.name;
      if (entryPath) return {path: entryPath, kind: entry.isDirectory ? 'directory' : 'file'};
    }
  }
  const files = Array.from((dataTransfer && dataTransfer.files) || []);
  if (!files.length) return {path: '', kind: ''};
  const file = files[0];
  return {path: file.path || file.webkitRelativePath || file.name || '', kind: 'file'};
}
function droppedPathFromDataTransfer(dataTransfer) {
  return droppedPathInfoFromDataTransfer(dataTransfer).path;
}
function applyDroppedPath(dataTransfer) {
  const info = droppedPathInfoFromDataTransfer(dataTransfer);
  if (!info.path) return false;
  setSelectedInputPath(info.path, info.kind);
  return true;
}
function dragHasFiles(event) {
  const types = Array.from((event.dataTransfer && event.dataTransfer.types) || []);
  return types.includes('Files');
}
async function chooseLocalPath(mode) {
  try {
    const data = await api('/api/pick-path', {method:'POST', body: JSON.stringify({mode})});
    if (mode === 'input_file') setSelectedInputPath(data.path, 'file');
    if (mode === 'input_directory') setSelectedInputPath(data.path, 'directory');
    if (mode === 'output_directory') {
      $('outputPath').value = joinPath(data.path, 'audit_report');
      $('outputPath').dataset.userSelected = 'true';
    }
  } catch (e) {
    setStatus(e.error || 'picker failed', 'failed');
    setFeedback(e.message || e.error || JSON.stringify(e), 'failed');
    renderReportPanel({status: 'failed', message: e.message || e.error || JSON.stringify(e)});
  }
}
function artifactLinks(run) {
  const arts = run.artifacts || {};
  return ['html','markdown','json','folder'].filter(k => arts[k]).map(k => `<a class="linkbtn" target="_blank" href="/artifact/${encodeURIComponent(run.id)}/${k}">${k}</a>`).join('');
}
function currentArtifactActions(run) {
  const links = artifactLinks(run);
  const retry = run && run.input_path && ['failed', 'canceled'].includes(run.status || '') ? '<button id="retryRunBtn" type="button">Retry</button>' : '';
  return `${links}${retry}`;
}
function reportLabel(reportType, status) {
  const value = reportType || status || '';
  const labels = {
    complete: '完整审查',
    limited: '范围受限审查',
    failed: '失败诊断',
    succeeded: '审查完成',
    running: '审查中',
    canceled: '已取消'
  };
  return labels[value] || value || '待生成';
}
function reportFolderForRun(run) {
  const arts = (run && run.artifacts) || {};
  if (arts.folder) return arts.folder;
  if (run && run.output) return pathParent(run.output);
  return '待生成';
}
function reportSummaryFallback(run) {
  const status = (run && run.status) || '';
  if (status === 'running') return '审查正在运行，日志会持续刷新。';
  if (status === 'succeeded') return '审查完成，报告入口已在下方列出。';
  if (status === 'failed') return (run && run.message) || '审查失败，请查看日志和失败诊断产物。';
  if (status === 'canceled') return (run && run.message) || '运行已取消，可在需要时重试。';
  return '报告生成后会显示摘要和打开入口。';
}
function safePanelClass(value) {
  const allowed = ['complete', 'limited', 'failed', 'succeeded', 'running', 'canceled'];
  return allowed.includes(value || '') ? value : '';
}
function renderReportPanel(run) {
  const active = run || {};
  const summary = active.summary || {};
  const reportType = summary.report_type || active.report_type || '';
  const status = active.status || '';
  const panelClass = safePanelClass(reportType) || safePanelClass(status);
  $('reportPanel').className = `report-panel ${panelClass}`;
  $('reportState').className = `status ${panelClass}`;
  $('reportState').textContent = reportLabel(reportType, status);
  $('reportType').textContent = reportLabel(reportType, status);
  $('reportRisk').textContent = summary.risk_level || (reportType || status ? '未标注' : '待生成');
  $('reportFolder').textContent = reportFolderForRun(active);
  $('reportSummary').textContent = summary.summary || reportSummaryFallback(active);
  $('currentActions').innerHTML = currentArtifactActions(active);
  const retry = $('retryRunBtn');
  if (retry) retry.addEventListener('click', () => retryRun(active));
}
function renderCurrentRun(run) {
  lastRun = run || lastRun;
  const active = run || {};
  const input = active.input_path || $('inputPath').value || 'No active run';
  const output = active.output || $('outputPath').value || '';
  $('currentRun').innerHTML = `<span>输入</span><strong>${escapeHtml(input)}</strong>`;
  $('currentOutput').innerHTML = `<span>输出</span><strong>${escapeHtml(output)}</strong>`;
  renderReportPanel(active);
  setFeedback(active.message || '', active.status || '');
}
function renderRun(run) {
  const summary = run.summary || {};
  const reportType = summary.report_type || run.report_type || run.status || '';
  const summaryLine = summary.summary ? `<div class="muted">${escapeHtml(summary.summary)}</div>` : '';
  const risk = summary.risk_level ? `<span class="status">${escapeHtml(summary.risk_level)}</span>` : '';
  return `<div class="run"><div class="run-title"><strong>${escapeHtml(reportLabel(reportType, run.status))}</strong><span class="status ${escapeHtml(run.status || '')}">${escapeHtml(run.status || '')}</span></div><div class="muted">${escapeHtml(run.input_path || '')}</div><div class="muted">${escapeHtml(run.started_at || '')}</div>${summaryLine}<div class="links">${risk}${artifactLinks(run)}</div></div>`;
}
async function startRunWithPayload(payload) {
  $('log').textContent = '';
  logOffset = 0;
  try {
    const data = await api('/api/runs', {method:'POST', body: JSON.stringify(payload)});
    activeRunId = data.run.id;
    lastRun = data.run;
    $('cancelBtn').disabled = false;
    setStatus('running');
    renderCurrentRun(data.run);
    if (!timer) timer = setInterval(pollLogs, 1200);
    pollLogs();
    refreshRuns();
  } catch (e) {
    setStatus(e.error || 'start failed', 'failed');
    setFeedback(e.message || e.error || JSON.stringify(e), 'failed');
    renderReportPanel({status: 'failed', message: e.message || e.error || JSON.stringify(e)});
  }
}
function startPayloadFromForm() {
  const payload = {input_path: $('inputPath').value, fresh: $('fresh').checked};
  if ($('outputPath').dataset.userSelected === 'true' && $('outputPath').value) {
    payload.output = $('outputPath').value;
  }
  return payload;
}
function retryRun(run) {
  if (!run || !run.input_path) return;
  if (activeRunId) return;
  $('inputPath').value = run.input_path || '';
  $('outputPath').value = run.output || '';
  $('fresh').checked = !!run.fresh;
  startRunWithPayload({input_path: run.input_path, output: run.output, fresh: !!run.fresh});
}
async function refreshRuns() {
  const data = await api('/api/runs');
  $('runs').innerHTML = (data.runs || []).map(renderRun).join('') || '<div class="muted">No runs yet</div>';
  const active = (data.runs || []).find(r => r.status === 'running');
  if (active && !activeRunId) {
    activeRunId = active.id; logOffset = 0; pollLogs();
  }
}
async function refreshConfig() {
  const data = await api('/api/config');
  const caps = data.capabilities || {};
  $('config').innerHTML = Object.keys(caps).map(k => `<div class="cell"><span>${k}</span><strong>${caps[k].ok ? 'ready' : 'needs config'}</strong><div class="muted">${(caps[k].missing || []).join(', ')}</div></div>`).join('') +
    `<div class="cell"><span>python-docx</span><strong>${data.optional_dependencies.python_docx ? 'available' : 'missing'}</strong></div><div class="cell"><span>openpyxl</span><strong>${data.optional_dependencies.openpyxl ? 'available' : 'missing'}</strong></div>`;
}
async function pollLogs() {
  if (!activeRunId) return;
  try {
    const data = await api(`/api/runs/${encodeURIComponent(activeRunId)}/logs?offset=${logOffset}`);
    logOffset = data.offset;
    if (data.lines && data.lines.length) {
      $('log').textContent += data.lines.join('\\n') + '\\n';
      $('log').scrollTop = $('log').scrollHeight;
    }
    const runData = await api(`/api/runs/${encodeURIComponent(activeRunId)}`);
    const run = runData.run;
    renderCurrentRun(run);
    setStatus(run.status || 'unknown', run.status || '');
    $('cancelBtn').disabled = run.status !== 'running';
    if (run.status !== 'running') {
      activeRunId = null;
      clearInterval(timer);
      timer = null;
      refreshRuns();
    }
  } catch (e) {
    setStatus(e.error || 'error', 'failed');
  }
}
$('startBtn').addEventListener('click', async () => {
  if (!$('outputPath').value && $('inputPath').value) {
    $('outputPath').value = defaultOutputStemForInput($('inputPath').value);
  }
  await startRunWithPayload(startPayloadFromForm());
});
$('pickFileBtn').addEventListener('click', () => chooseLocalPath('input_file'));
$('pickDirectoryBtn').addEventListener('click', () => chooseLocalPath('input_directory'));
$('pickOutputBtn').addEventListener('click', () => chooseLocalPath('output_directory'));
$('cancelBtn').addEventListener('click', async () => {
  if (!activeRunId) return;
  await api(`/api/runs/${encodeURIComponent(activeRunId)}/cancel`, {method:'POST', body:'{}'});
  pollLogs();
});
const dropZone = $('inputDropZone');
['dragenter', 'dragover'].forEach(name => dropZone.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
  event.stopPropagation();
  dropZone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach(name => dropZone.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
  event.stopPropagation();
  dropZone.classList.remove('dragover');
  if (name === 'drop') applyDroppedPath(event.dataTransfer);
}));
['dragover', 'drop'].forEach(name => document.addEventListener(name, (event) => {
  if (!dragHasFiles(event)) return;
  event.preventDefault();
}));
refreshConfig();
renderCurrentRun(null);
refreshRuns();
</script>
</body>
</html>"""


def serve_web_runner(host="127.0.0.1", port=8765, open_browser=True, history_path=None):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    state = WebRunnerState(history_path=history_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "VeritasWebRunner/1.0"

        def _send_bytes(self, data, content_type="application/octet-stream", status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for key, value in web_runner_cors_headers().items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(data, "application/json; charset=utf-8", status=status)

        def _route(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query)
            return path, query

        def do_OPTIONS(self):
            self._send_json({"ok": True})

        def do_GET(self):
            path, query = self._route()
            if path == "/":
                self._send_bytes(render_web_runner_page().encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/health":
                self._send_json({"ok": True, "model": LLM_MODEL, "web_runner": True})
                return
            if path == "/api/config":
                self._send_json(web_runner_config_status())
                return
            if path == "/api/runs":
                self._send_json({"ok": True, "runs": state.list_runs()})
                return
            match = re.match(r"^/api/runs/([^/]+)$", path)
            if match:
                run = state.get_run(urllib.parse.unquote(match.group(1)))
                self._send_json({"ok": bool(run), "run": run} if run else {"ok": False, "error": "not_found"}, 200 if run else 404)
                return
            match = re.match(r"^/api/runs/([^/]+)/logs$", path)
            if match:
                payload = state.logs_since(urllib.parse.unquote(match.group(1)), (query.get("offset") or ["0"])[0])
                self._send_json(payload if payload else {"ok": False, "error": "not_found"}, 200 if payload else 404)
                return
            match = re.match(r"^/api/runs/([^/]+)/artifacts$", path)
            if match:
                run = state.discover_artifacts(urllib.parse.unquote(match.group(1)))
                self._send_json({"ok": bool(run), "run": run, "artifacts": (run or {}).get("artifacts", {})}, 200 if run else 404)
                return
            match = re.match(r"^/artifact/([^/]+)/([^/]+)$", path)
            if match:
                run_id = urllib.parse.unquote(match.group(1))
                kind = urllib.parse.unquote(match.group(2))
                target, error = state.artifact_target(run_id, kind)
                if error:
                    self._send_json({"ok": False, "error": error}, 404)
                    return
                if kind == "folder":
                    payload = json.dumps({"ok": True, "path": str(target)}, ensure_ascii=False, indent=2).encode("utf-8")
                    self._send_bytes(payload, "application/json; charset=utf-8")
                    return
                content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                self._send_bytes(Path(target).read_bytes(), content_type)
                return
            self._send_json({"ok": False, "error": "not_found"}, 404)

        def do_POST(self):
            path, _query = self._route()
            if path in {"/generate", "/followups"}:
                try:
                    payload = _read_json_request_body(self)
                    self._send_json(_report_action_api_response(path, payload))
                except ValueError as e:
                    status = 413 if str(e) == "request_too_large" else 400
                    self._send_json({"ok": False, "error": str(e)}, status)
                except Exception as e:
                    self._send_json({"ok": False, "error": f"{type(e).__name__}: {_brief_text(str(e), 300)}"}, 500)
                return
            if path == "/api/runs":
                try:
                    payload = _read_json_request_body(self, max_bytes=20_000)
                    response, status = state.start_run(payload.get("input_path"), output=payload.get("output"), fresh=bool(payload.get("fresh")))
                    self._send_json(response, status)
                except Exception as e:
                    self._send_json({"ok": False, "error": f"{type(e).__name__}: {_brief_text(str(e), 300)}"}, 500)
                return
            if path == "/api/pick-path":
                try:
                    payload = _read_json_request_body(self, max_bytes=20_000)
                    response = pick_local_path(payload.get("mode"))
                    self._send_json(response, 200 if response.get("ok") else 400)
                except Exception as e:
                    self._send_json({"ok": False, "error": f"{type(e).__name__}: {_brief_text(str(e), 300)}"}, 500)
                return
            match = re.match(r"^/api/runs/([^/]+)/cancel$", path)
            if match:
                response, status = state.cancel_run(urllib.parse.unquote(match.group(1)))
                self._send_json(response, status)
                return
            self._send_json({"ok": False, "error": "not_found"}, 404)

        def log_message(self, fmt, *args):
            print(f"[web-runner] {self.address_string()} {fmt % args}")

    try:
        httpd = ThreadingHTTPServer((host, int(port)), Handler)
    except OSError as e:
        print(f"无法启动Web Runner: {e}")
        print(f"端口 {port} 可能已被占用；请改用 --web-port <port>。")
        return 1
    url = f"http://{host}:{int(port)}"
    print(f"Veritas Web Runner 已启动: {url}")
    print("仅监听 127.0.0.1。按 Ctrl+C 停止。")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"自动打开浏览器失败: {e}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb Runner 已停止")
    finally:
        httpd.server_close()
    return 0


# ══════════════════════════════════════════════════════════════
# 报告解析与格式化
# ══════════════════════════════════════════════════════════════

def audit_references(references_text, online=False, online_limit=50, timeout=10, cache=None):
    return audit_references_from_namespace(
        globals(),
        references_text,
        online=online,
        online_limit=online_limit,
        timeout=timeout,
        cache=cache,
    )

def _reference_get_json(url, timeout=10, headers=None):
    return _reference_get_json_from_namespace(globals(), url, timeout=timeout, headers=headers)


def lookup_crossref_reference(ref, timeout=10):
    return lookup_crossref_reference_from_namespace(globals(), ref, timeout=timeout)


def lookup_openalex_reference(ref, timeout=10):
    return lookup_openalex_reference_from_namespace(globals(), ref, timeout=timeout)


def lookup_pubmed_reference(ref, timeout=10):
    return lookup_pubmed_reference_from_namespace(globals(), ref, timeout=timeout)


def lookup_official_site_reference(ref, timeout=10):
    return lookup_official_site_reference_from_namespace(globals(), ref, timeout=timeout)

def verify_reference_online(ref, timeout=10):
    return verify_reference_online_from_namespace(globals(), ref, timeout=timeout)


def verify_resource_availability(resource, timeout=10):
    return verify_resource_availability_from_namespace(globals(), resource, timeout=timeout)


def audit_resources(text, online=True, timeout=10, cache=None):
    return audit_resources_from_namespace(globals(), text, online=online, timeout=timeout, cache=cache)


from .cross_file_consistency import (
    _cross_file_context_match,
    _cross_file_figure_table_findings,
    _cross_file_finding,
    _cross_file_group_findings,
    _cross_file_is_noisy,
    _cross_file_sample_findings,
    _cross_file_segment_text,
    _cross_file_severity_label,
    _cross_file_shared_terms,
    _cross_file_source_label,
    _cross_file_source_rank,
    _cross_file_terms,
    _extract_cross_file_group_labels,
    _extract_cross_file_sample_records,
    _extract_supplementary_refs,
    _normalize_group_label,
    build_cross_file_consistency_audit,
    format_cross_file_consistency_html,
    format_cross_file_consistency_markdown,
)
from .evidence_chain import (
    _build_claim_chain_findings,
    _build_evidence_clusters,
    _cluster_severity,
    _evidence_claim_keywords,
    _evidence_item,
    _evidence_items_from_chain_findings,
    _evidence_items_from_cross_file,
    _evidence_items_from_image,
    _evidence_items_from_llm_report,
    _evidence_items_from_reference,
    _evidence_items_from_resource,
    _evidence_items_from_stat,
    _evidence_keys_from_text,
    _evidence_section_name,
    _evidence_segment_has_strong_claim,
    _extract_evidence_refs,
    _extract_evidence_sections,
    _extract_section_group_records,
    _extract_section_sample_records,
    _results_support_claim,
    build_evidence_chain_audit,
    format_evidence_chain_audit_html,
    format_evidence_chain_audit_markdown,
)


def format_report(report, pdf_path, meta, stat_result):
    return format_report_from_namespace(globals(), report, pdf_path, meta, stat_result)


def format_html_report(report, pdf_path, meta, stat_result):
    """将审查结果格式化为紧凑、可审阅的HTML报告"""
    context = build_html_report_context_from_namespace(globals(), report, pdf_path, meta, stat_result)
    risk_color = context["risk_color"]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>学术论文审查报告</title>
<style>
  :root {{
    --bg: #f7f3ec;
    --paper: #fffdf8;
    --surface: #fffaf1;
    --surface2: #f3eadc;
    --text: #2b241d;
    --text-muted: #7b7065;
    --accent: #c15f3c;
    --accent2: #2f6f73;
    --border: #e4d8c8;
    --red: #b42318;
    --yellow: #b7791f;
    --green: #2f7d50;
    --shadow: 0 22px 70px rgba(61, 45, 31, 0.10);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
    background: #f6f6f6;
    color: var(--text);
    line-height: 1.6;
    padding: 28px 20px;
  }}
  .container {{ max-width: 1120px; margin: 0 auto; }}
  .header {{
    background: rgba(255,253,248,0.86);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 36px;
    margin-bottom: 28px;
    text-align: center;
    box-shadow: none;
  }}
  .header h1 {{ font-size: 32px; margin-bottom: 18px; letter-spacing: 0; }}
  .risk-badge {{
    display: inline-block;
    font-size: 22px;
    font-weight: 700;
    padding: 8px 24px;
    border-radius: 999px;
    color: #fff;
    background: {risk_color};
    margin: 8px 0;
  }}
  .artifact-badge {{
    display: inline-block;
    border-radius: 6px;
    padding: 7px 10px;
    color: #fff;
    font-weight: 800;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 24px;
    text-align: left;
    margin-top: 16px;
    font-size: 14px;
    color: var(--text-muted);
  }}
  .meta-grid strong {{ color: var(--text); }}
  .section {{
    background: rgba(255,253,248,0.88);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 22px;
    box-shadow: 0 10px 34px rgba(61, 45, 31, 0.06);
  }}
  .section h2 {{
    font-size: 20px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--surface2); color: var(--text-muted); font-weight: 650; text-transform: uppercase; font-size: 12px; }}
  tr:hover {{ background: rgba(193,95,60,0.05); }}
  .status-ok {{ color: var(--green); font-weight: 600; }}
  .status-warn {{ color: var(--yellow); font-weight: 600; }}
  .verdict-red {{ color: var(--red); font-weight: 700; }}
  .verdict-yellow {{ color: var(--yellow); font-weight: 700; }}
  .verdict-green {{ color: var(--green); font-weight: 700; }}
  .detail-card {{
    background: var(--surface2);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 4px solid var(--accent);
  }}
  .detail-card[open] {{ background: #f8efe2; }}
  .detail-header {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .detail-summary {{ cursor: pointer; list-style: none; }}
  .detail-summary::-webkit-details-marker {{ display: none; }}
  .detail-summary::after {{
    content: "展开详情";
    margin-left: auto;
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
  }}
  .detail-card[open] .detail-summary::after {{ content: "收起详情"; }}
  .section-hint {{ color: var(--text-muted); margin: -6px 0 14px; font-size: 14px; }}
  .evidence-summary {{ border-left: 4px solid var(--red); }}
  .suspicion-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .suspicion-card {{
    background: #fff8ed;
    border: 1px solid var(--border);
    border-left: 4px solid var(--red);
    border-radius: 8px;
    padding: 12px 14px;
  }}
  .suspicion-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 44px minmax(76px, 120px) minmax(180px, 1fr) auto;
    gap: 8px 12px;
    align-items: center;
  }}
  .suspicion-summary::-webkit-details-marker {{ display: none; }}
  .suspicion-summary::after {{
    content: "展开详情";
    grid-column: 4;
    grid-row: 2;
    justify-self: end;
    color: var(--accent);
    font-size: 12px;
    font-weight: 700;
  }}
  .suspicion-card[open] .suspicion-summary::after {{ content: "收起详情"; }}
  .suspicion-rank {{
    background: rgba(248,113,113,0.16);
    color: var(--red);
    border-radius: 999px;
    padding: 4px 8px;
    text-align: center;
    font-weight: 800;
    font-size: 13px;
  }}
  .suspicion-title {{
    font-weight: 700;
    color: var(--text);
    overflow-wrap: anywhere;
  }}
  .suspicion-score {{
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
  }}
  .suspicion-brief {{
    grid-column: 2 / 4;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.45;
    overflow-wrap: anywhere;
  }}
  .suspicion-body {{
    margin-top: 12px;
  }}
  .action-section {{
    border-left: 5px solid var(--accent);
  }}
  .action-list {{
    display: grid;
    gap: 10px;
  }}
  .action-card {{
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr) 140px;
    gap: 12px;
    align-items: start;
    padding: 14px;
    background: #fff8ed;
    border: 1px solid var(--border);
    border-radius: 12px;
  }}
  .action-rank {{
    background: rgba(193,95,60,0.14);
    color: var(--accent);
    border-radius: 999px;
    padding: 4px 8px;
    font-weight: 800;
    text-align: center;
  }}
  .action-card p {{
    color: var(--text-muted);
    margin-top: 4px;
    font-size: 13px;
  }}
  .action-card a, .review-overview a {{
    color: var(--accent);
    text-decoration: none;
  }}
  .action-source {{
    color: var(--text-muted);
    font-size: 12px;
    text-align: right;
  }}
  .review-overview {{
    border-left: 5px solid var(--accent2);
  }}
  .overview-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 16px;
  }}
  .overview-grid div {{
    border: 1px solid var(--border);
    background: #fff8ed;
    border-radius: 6px;
    padding: 10px;
  }}
  .overview-grid span {{
    display: block;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .overview-grid strong {{
    display: block;
    margin-top: 3px;
    overflow-wrap: anywhere;
  }}
  .overview-columns, .limitation-grid {{
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    gap: 18px;
  }}
  .overview-actions {{
    padding-left: 22px;
  }}
  .overview-actions li {{
    margin-bottom: 10px;
  }}
  .overview-actions li span {{
    color: var(--text-muted);
    font-weight: 800;
    margin-right: 6px;
  }}
  .overview-actions p, .artifact-list {{
    color: var(--text-muted);
    font-size: 13px;
  }}
  .artifact-list {{
    padding-left: 18px;
    overflow-wrap: anywhere;
  }}
  .limitation-panel {{
    border-left: 5px solid var(--yellow);
  }}
  .checks-table {{ table-layout: fixed; }}
  .checks-table th:nth-child(1), .checks-table td:nth-child(1) {{ width: 44px; text-align: center; }}
  .checks-table th:nth-child(2), .checks-table td:nth-child(2) {{ width: 120px; }}
  .evidence-table th:nth-child(4), .evidence-table td:nth-child(4),
  .evidence-table th:nth-child(5), .evidence-table td:nth-child(5) {{ width: 28%; }}
  .evidence-cell, .reason-cell {{
    color: var(--text);
    line-height: 1.55;
    word-break: break-word;
    overflow-wrap: anywhere;
  }}
  .muted {{ color: var(--text-muted); text-align: center; padding: 18px; }}
  .detail-num {{
    background: var(--accent);
    color: var(--bg);
    border-radius: 50%;
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 13px;
  }}
  .detail-cat {{ color: var(--accent); font-weight: 600; }}
  .detail-item {{ flex: 1; }}
  .detail-verdict {{ font-size: 14px; }}
  .detail-brief {{
    flex-basis: 100%;
    color: var(--text-muted);
    font-size: 13px;
    padding-left: 40px;
  }}
  .detail-body {{ margin-top: 12px; }}
  .detail-evidence {{
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(183,121,31,0.10);
    border-radius: 6px;
    font-size: 14px;
    color: #6f4b12;
  }}
  .detail-evidence blockquote {{
    margin-top: 8px;
    white-space: pre-wrap;
    color: #6f4b12;
  }}
  .table-hint {{
    display: inline-block;
    color: var(--accent);
    font-weight: 600;
    margin-right: 8px;
  }}
  .summary-excerpt {{
    color: var(--text-muted);
    display: block;
    margin-top: 4px;
  }}
  .data-table-details {{
    margin-top: 8px;
  }}
  .data-table-details summary {{
    cursor: pointer;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .data-table-wrap {{
    margin-top: 8px;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fffdf8;
  }}
  .data-table {{
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .data-table th,
  .data-table td {{
    min-width: 96px;
    max-width: 320px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    vertical-align: top;
    white-space: normal;
    color: var(--text);
  }}
  .data-table th {{
    position: sticky;
    top: 0;
    background: #efe3d3;
    color: var(--text);
    z-index: 1;
  }}
  .detail-text {{
    margin-top: 8px;
    font-size: 14px;
    color: var(--text-muted);
    white-space: pre-wrap;
  }}
  .conclusion-section {{ border-left: 4px solid var(--green); }}
  .conclusion-text {{ font-size: 16px; white-space: pre-wrap; color: var(--text); }}
  .coverage-warning {{
    border-left: 5px solid var(--yellow);
    background: rgba(183,121,31,0.10);
  }}
  .coverage-warning code {{ background: var(--surface2); padding: 2px 6px; border-radius: 4px; }}
  .coverage-ok {{
    border-left: 5px solid var(--green);
    background: rgba(47,125,80,0.08);
  }}
  .error-block {{
    background: rgba(180,35,24,0.08);
    border: 1px solid var(--red);
    border-radius: 8px;
    padding: 16px;
    white-space: pre-wrap;
    font-family: monospace;
    font-size: 13px;
    color: #fca5a5;
    overflow-x: auto;
  }}
  .score-bar {{
    height: 8px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
  }}
  .score-fill {{
    height: 100%;
    border-radius: 4px;
    background: var(--red);
    transition: none;
  }}
  .score-breakdown {{
    margin-top: 6px;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .reference-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .cross-file-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .cross-file-card {{
    border: 1px solid var(--border);
    border-left: 4px solid var(--yellow);
    border-radius: 10px;
    background: #fff8ed;
    padding: 12px 14px;
  }}
  .cross-file-card[open] {{
    background: #fbfbfb;
  }}
  .cross-file-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 46px minmax(110px, 160px) minmax(180px, 1fr);
    gap: 8px 12px;
    align-items: center;
  }}
  .cross-file-summary::-webkit-details-marker {{ display: none; }}
  .cross-file-rank {{
    color: var(--accent);
    font-weight: 800;
  }}
  .cross-file-severity {{
    font-weight: 800;
    border-radius: 999px;
    padding: 3px 8px;
    text-align: center;
    background: rgba(183,121,31,0.12);
  }}
  .cross-file-strong {{ color: var(--red); }}
  .cross-file-medium {{ color: var(--yellow); }}
  .cross-file-weak {{ color: var(--text-muted); }}
  .cross-file-title {{
    font-weight: 700;
    overflow-wrap: anywhere;
  }}
  .cross-file-reason {{
    grid-column: 2 / 4;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .cross-file-body {{
    margin-top: 12px;
    color: var(--text-muted);
    font-size: 14px;
    display: grid;
    gap: 10px;
  }}
  .cross-file-body p {{
    margin-top: 4px;
    overflow-wrap: anywhere;
  }}
  .reference-card {{
    border: 1px solid var(--border);
    border-radius: 10px;
    background: #fff8ed;
    padding: 12px 14px;
  }}
  .reference-summary {{
    cursor: pointer;
    list-style: none;
    display: grid;
    grid-template-columns: 46px minmax(98px, 140px) minmax(220px, 1fr) auto;
    gap: 8px 12px;
    align-items: center;
  }}
  .reference-summary::-webkit-details-marker {{ display: none; }}
  .reference-index {{
    color: var(--accent);
    font-weight: 800;
  }}
  .reference-status {{
    font-weight: 800;
    border-radius: 999px;
    padding: 3px 8px;
    text-align: center;
    background: rgba(47,111,115,0.10);
  }}
  .reference-verified, .reference-likely {{ color: var(--green); }}
  .reference-weak, .reference-not_found, .reference-error {{ color: var(--red); }}
  .reference-title {{
    font-weight: 700;
    overflow-wrap: anywhere;
  }}
  .reference-confidence {{
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
  }}
  .reference-issues {{
    grid-column: 2 / 5;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .reference-body {{
    margin-top: 12px;
    color: var(--text-muted);
    font-size: 14px;
  }}
  .reference-matches {{
    margin-top: 8px;
    padding-left: 22px;
  }}
  .reference-matches li {{
    margin: 8px 0;
  }}
  .reference-matches a, .image-section a {{
    color: var(--accent);
    font-weight: 700;
  }}
  .image-table code {{
    color: var(--text-muted);
    white-space: normal;
    overflow-wrap: anywhere;
  }}
  .detector-hint {{
    display: inline-block;
    color: var(--accent);
    font-weight: 800;
    font-size: 12px;
    margin-bottom: 4px;
  }}
  .web-action-section {{
    border-left: 5px solid #2563eb;
  }}
  .web-action-toolbar {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 12px 0;
  }}
  .action-button, .secondary-button {{
    border: 1px solid #cbd5e1;
    background: #ffffff;
    color: var(--text-main);
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 800;
    cursor: pointer;
  }}
  .action-button {{
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
  }}
  .draft-language-select {{
    border: 1px solid #cbd5e1;
    background: #ffffff;
    color: var(--text-main);
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 800;
  }}
  .identity-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 10px;
    margin: 12px 0;
  }}
  .identity-grid label, .custom-concern-label, .inline-control {{
    display: flex;
    flex-direction: column;
    gap: 5px;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
  }}
  .identity-grid input, .custom-concern-input {{
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px 10px;
    color: var(--text-main);
    background: #ffffff;
    font: inherit;
  }}
  .evidence-picker {{
    margin: 12px 0;
  }}
  .evidence-choice-list {{
    display: grid;
    gap: 8px;
    margin-top: 8px;
  }}
  .evidence-choice {{
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 8px;
    align-items: start;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px;
    background: #ffffff;
  }}
  .evidence-choice small {{
    display: block;
    color: var(--text-muted);
    line-height: 1.45;
    margin-top: 3px;
  }}
  .custom-concern-input {{
    width: 100%;
    min-height: 70px;
    resize: vertical;
  }}
  .manual-confirmation {{
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 8px;
    align-items: start;
    margin: 10px 0;
    color: var(--text-main);
    font-size: 13px;
  }}
  .existing-followups {{
    color: var(--text-muted);
    font-size: 13px;
    margin: 8px 0;
  }}
  .action-button:hover, .secondary-button:hover {{
    filter: brightness(0.96);
  }}
  .web-action-status {{
    color: var(--text-muted);
    font-size: 13px;
    margin: 8px 0;
  }}
  .web-action-status.error {{
    color: #b42318;
    font-weight: 700;
  }}
  .generated-draft {{
    width: 100%;
    min-height: 260px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font: 14px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: var(--text-main);
    background: #fff;
    resize: vertical;
  }}
  .footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 32px;
    padding: 16px;
  }}
  /* Compact grayscale report skin: evidence first, decoration last. */
  :root {{
    --bg: #f6f6f6;
    --paper: #ffffff;
    --surface: #ffffff;
    --surface2: #eeeeee;
    --text: #171717;
    --text-muted: #666666;
    --accent: #111111;
    --accent2: #3f3f46;
    --border: #d4d4d4;
    --red: #b42318;
    --yellow: #8a5a00;
    --green: #166534;
    --shadow: none;
  }}
  body {{
    background: #f6f6f6;
    color: var(--text);
    line-height: 1.55;
    padding: 18px;
  }}
  .container {{ max-width: 1280px; }}
  .header, .section {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: none;
  }}
  .header {{
    padding: 18px;
    margin-bottom: 14px;
    text-align: left;
  }}
  .report-topline {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 12px;
  }}
  .report-kicker {{
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0;
  }}
  .header h1 {{
    font-size: 24px;
    line-height: 1.2;
    margin: 3px 0 8px;
    letter-spacing: 0;
  }}
  .report-summary {{
    max-width: 820px;
    color: #333333;
    font-size: 14px;
  }}
  .risk-badge {{
    border-radius: 6px;
    padding: 7px 10px;
    margin: 0;
    font-size: 13px;
    line-height: 1;
    white-space: nowrap;
  }}
  .score-panel {{
    display: grid;
    grid-template-columns: 170px minmax(220px, 1fr);
    gap: 12px;
    align-items: center;
    padding: 12px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .score-value {{
    font-size: 34px;
    line-height: 1;
    font-weight: 900;
    color: {risk_color};
  }}
  .score-caption {{
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 4px;
  }}
  .priority-label {{
    font-weight: 900;
    color: {risk_color};
    margin-bottom: 4px;
  }}
  .score-bar {{
    height: 7px;
    background: #e5e5e5;
    border-radius: 4px;
    margin-top: 0;
  }}
  .score-fill {{
    background: {risk_color};
    border-radius: 4px;
    transition: none;
  }}
  .score-breakdown {{
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
  }}
  .meta-grid > div, .meta-item {{
    min-width: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 9px 10px;
    background: #fafafa;
    color: var(--text-muted);
    font-size: 12px;
  }}
  .meta-grid strong, .meta-item strong {{
    display: block;
    color: var(--text);
    font-size: 13px;
    margin-top: 3px;
    overflow-wrap: anywhere;
  }}
  .section {{
    padding: 16px;
    margin-bottom: 14px;
  }}
  .section h2 {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 17px;
    line-height: 1.25;
    margin-bottom: 12px;
    padding-bottom: 8px;
  }}
  .section-hint {{
    margin: -4px 0 12px;
    color: var(--text-muted);
    font-size: 13px;
  }}
  table {{ font-size: 13px; }}
  th, td {{
    padding: 8px 9px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  th {{
    background: #f1f1f1;
    color: #444444;
    font-size: 11px;
    letter-spacing: 0;
  }}
  .action-card, .suspicion-card, .detail-card, .reference-card {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-left: 3px solid #111111;
    border-radius: 6px;
    padding: 10px 12px;
  }}
  .cross-file-card {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-left: 3px solid var(--yellow);
    border-radius: 6px;
    padding: 10px 12px;
  }}
  .evidence-summary {{ border-left: 3px solid var(--red); }}
  .suspicion-summary {{
    grid-template-columns: 44px minmax(72px, 112px) minmax(180px, 1fr) 96px;
    gap: 7px 10px;
  }}
  .suspicion-rank, .action-rank, .detail-num {{
    background: #f1f1f1;
    color: #111111;
    border: 1px solid var(--border);
    border-radius: 5px;
  }}
  .suspicion-brief {{
    grid-column: 2 / 4;
    color: var(--text-muted);
  }}
  .summary-action {{
    grid-column: 4;
    grid-row: 2;
    justify-self: end;
    color: #111111;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
  }}
  .detail-summary .summary-action {{
    grid-column: auto;
    grid-row: auto;
    margin-left: auto;
  }}
  .detail-card[open], .suspicion-card[open] {{
    background: #fbfbfb;
  }}
  .cross-file-card[open] {{
    background: #fbfbfb;
  }}
  .detail-summary::after, .suspicion-summary::after {{
    content: none;
  }}
  .detail-body, .suspicion-body {{
    border-top: 1px solid var(--border);
    margin-top: 10px;
    padding-top: 10px;
  }}
  .detail-evidence {{
    background: #f7f7f7;
    color: #222222;
    border: 1px solid var(--border);
    border-radius: 6px;
  }}
  .detail-evidence blockquote {{
    color: #222222;
  }}
  .detail-text {{
    color: #4b4b4b;
  }}
  .data-table-wrap {{
    background: #ffffff;
    border-radius: 6px;
  }}
  .data-table th {{
    background: #ededed;
  }}
  .merged-group {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 10px;
    background: #fff;
  }}
  .merged-group summary {{
    cursor: pointer;
    font-weight: 800;
    color: #111111;
  }}
  .coverage-warning, .coverage-ok, .conclusion-section, .action-section, .web-action-section {{
    border-left-width: 3px;
    background: #ffffff;
  }}
  .web-action-section {{ border-left-color: #2563eb; }}
  .action-button, .secondary-button {{
    border-radius: 6px;
    padding: 8px 11px;
    color: #111111;
  }}
  .action-button {{ color: #ffffff; }}
  .generated-draft {{
    border-radius: 6px;
    min-height: 220px;
    color: #111111;
  }}
  .image-thumb {{
    max-width: 84px;
    max-height: 64px;
    object-fit: contain;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: #ffffff;
  }}
  .muted-inline {{
    color: var(--text-muted);
    font-size: 12px;
  }}
  @media (max-width: 900px) {{
    body {{ padding: 10px; }}
    .report-topline {{ flex-direction: column; }}
    .score-panel {{ grid-template-columns: 1fr; }}
    .meta-grid {{ grid-template-columns: 1fr 1fr; }}
    .overview-grid {{ grid-template-columns: 1fr 1fr; }}
    .overview-columns, .limitation-grid {{ grid-template-columns: 1fr; }}
    .suspicion-summary, .reference-summary {{
      grid-template-columns: 40px minmax(70px, 100px) 1fr;
    }}
    .suspicion-score, .reference-confidence, .summary-action {{
      grid-column: 2 / 4;
      justify-self: start;
    }}
    .suspicion-brief, .reference-issues {{
      grid-column: 1 / 4;
    }}
  }}
  @media (max-width: 560px) {{
    .meta-grid {{ grid-template-columns: 1fr; }}
    .overview-grid {{ grid-template-columns: 1fr; }}
    .checks-table {{ table-layout: auto; }}
  }}
</style>
</head>
{build_html_report_body_from_namespace(globals(), context)}"""
    return html


def update_patterns(comments_file):
    """从PubPeer评论文本中用LLM提取新的欺诈模式，更新知识库
    
    comments_file: 包含PubPeer评论文本的文件路径
    """
    return update_patterns_from_namespace(globals(), comments_file)


# ══════════════════════════════════════════════════════════════
# 腾讯朱雀AI文本检测辅助功能
# ══════════════════════════════════════════════════════════════

def copy_to_clipboard(text: str) -> bool:
    return copy_to_clipboard_from_namespace(globals(), text)


def launch_zhuque_ai_detect(text: str):
    return launch_zhuque_ai_detect_from_namespace(globals(), text)


# ──────────────────────────────────────────────────────────────
# AI图片检测（imagedetector.com）
# ──────────────────────────────────────────────────────────────

IMAGE_DETECT_URL = "https://imagedetector.com/"
IMAGE_DETECT_UPLOAD_BASE = "https://ai-image-detector-prod.nyc3.digitaloceanspaces.com"
GLM_IMAGE_MAX_BYTES = 5 * 1024 * 1024

# 支持的图片扩展名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}


def _extract_images_from_mineru_zip(zip_path: Path, output_dir: Path) -> List[str]:
    return _extract_images_from_mineru_zip_from_namespace(globals(), zip_path, output_dir)


def collect_mineru_image_files(input_path: str, output_dir=None) -> List[str]:
    return collect_mineru_image_files_from_namespace(globals(), input_path, output_dir=output_dir)




def analyze_image_reasonability(image_path: str):
    return analyze_image_reasonability_from_namespace(globals(), image_path)


def _image_file_fingerprint(image_path: str):
    return _image_file_fingerprint_from_namespace(globals(), image_path)


def _image_semantic_cache_key(image_path: str, api_url=None, model=None, cache_version=None):
    return _image_semantic_cache_key_from_namespace(
        globals(),
        image_path,
        api_url=api_url,
        model=model,
        cache_version=cache_version,
    )


def call_imagedetector(image_path: str, timeout=60):
    return call_imagedetector_from_namespace(globals(), image_path, timeout=timeout)


def _call_imagedetector_unbounded(image_path: str, timeout=60):
    return _call_imagedetector_unbounded_from_namespace(globals(), image_path, timeout=timeout)


def call_glm_image_semantics(image_path: str, timeout=45, api_key=None, model=None):
    return call_glm_image_semantics_from_namespace(
        globals(),
        image_path,
        timeout=timeout,
        api_key=api_key,
        model=model,
    )


def _call_glm_image_semantics_unbounded(image_path: str, timeout=45, api_key=None, model=None):
    return _call_glm_image_semantics_unbounded_from_namespace(
        globals(),
        image_path,
        timeout=timeout,
        api_key=api_key,
        model=model,
    )


def build_image_audit(
    input_path: str,
    output_dir=None,
    limit=None,
    semantic=True,
    semantic_limit=None,
    semantic_timeout=45,
    semantic_cache=None,
    semantic_cache_save=None,
    detector=True,
    detector_limit=None,
    detector_timeout=60,
    detector_cache=None,
    detector_cache_save=None,
):
    return build_image_audit_from_namespace(
        globals(),
        input_path,
        output_dir=output_dir,
        limit=limit,
        semantic=semantic,
        semantic_limit=semantic_limit,
        semantic_timeout=semantic_timeout,
        semantic_cache=semantic_cache,
        semantic_cache_save=semantic_cache_save,
        detector=detector,
        detector_limit=detector_limit,
        detector_timeout=detector_timeout,
        detector_cache=detector_cache,
        detector_cache_save=detector_cache_save,
    )


def format_image_audit_html(image_audit):
    return _format_image_audit_html(image_audit, image_detect_url=IMAGE_DETECT_URL)


def format_image_audit_markdown(image_audit):
    return _format_image_audit_markdown(image_audit, image_detect_url=IMAGE_DETECT_URL)


def save_image_review_manifest(image_audit, output_dir):
    return _save_image_review_manifest(image_audit, output_dir, image_detect_url=IMAGE_DETECT_URL)


def collect_image_files(input_path: str, include_pdf=True, include_mineru=True, output_dir=None) -> List[str]:
    return collect_image_files_from_namespace(
        globals(),
        input_path,
        include_pdf=include_pdf,
        include_mineru=include_mineru,
        output_dir=output_dir,
    )


def launch_image_ai_detect(
    input_path: str,
    output_dir=None,
    limit=None,
    semantic=True,
    semantic_limit=None,
    semantic_timeout=45,
    semantic_cache=None,
    detector=True,
    detector_limit=None,
    detector_timeout=60,
    detector_cache=None,
):
    """Run the automatic image audit subtool and save the review manifest."""
    print("\n" + "=" * 60)
    print("🖼️ AI图片检测子工具 (图像语义分析 + imagedetector.com)")
    print("=" * 60)

    target_output_dir = output_dir or (Path(input_path).parent if Path(input_path).is_file() else Path(input_path))
    image_audit = build_image_audit(
        input_path,
        output_dir=target_output_dir,
        limit=limit,
        semantic=semantic,
        semantic_limit=semantic_limit,
        semantic_timeout=semantic_timeout,
        semantic_cache=semantic_cache,
        detector=detector,
        detector_limit=detector_limit,
        detector_timeout=detector_timeout,
        detector_cache=detector_cache,
    )
    if not image_audit.get("image_count"):
        print("⚠️ 未找到可检测的图片文件")
        return image_audit

    manifest_path = save_image_review_manifest(image_audit, target_output_dir)
    if manifest_path:
        print(f"  🧾 图片AI检测结果清单: {manifest_path}")
    print(
        f"✅ 图片子工具完成: 本地{image_audit.get('checked_count')}/{image_audit.get('image_count')}张；"
        f"图像语义分析 {image_audit.get('semantic_checked')}张；imagedetector {image_audit.get('detector_checked')}张"
    )

    # 清理临时提取目录
    tmp_dir = os.path.join(os.path.dirname(input_path) if os.path.isfile(input_path) else input_path, "_veritas_images_tmp")
    if os.path.isdir(tmp_dir):
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
            print("  🧹 已清理临时图片目录")
        except Exception:
            pass
    return image_audit



def run_audit(run_request: RunRequest, args=None) -> RunResult:
    args = args if args is not None else run_request.to_args()
    input_path = run_request.input_path
    if not input_path.exists():
        print(f"❌ 路径不存在: {input_path}")
        failure = AuditFailure(
            capability="input",
            error_class="input_path_not_found",
            message=f"路径不存在: {input_path}",
            retry_command=retry_command_from_args(args, input_path),
        )
        return RunResult.failed(failure, {}, meta={"input_path": str(input_path)})

    output_dir, output_stem = get_output_base(input_path)
    setup_run_logging(input_path)
    print(f"📁 所有输出将保存到: {output_dir}")
    runtime_config = apply_runtime_config(load_runtime_config())
    print(f"🤖 当前LLM: model={LLM_MODEL}, url={LLM_API_URL}")
    config_errors = runtime_config.validation_errors()
    if config_errors:
        detail = "; ".join(f"{e['capability']}.{e['field']}" for e in config_errors)
        print(f"⚠️ 关键配置缺失: {detail}。关键能力预检会在对应正式阶段前停止并生成失败诊断。")
    resume_dir = get_resume_dir(output_dir, output_stem)
    _run_logging._RESUME_EVENTS_ENABLED = not bool(getattr(args, "no_resume", False))
    if getattr(args, "fresh", False):
        import shutil
        print(f"🧹 --fresh: 清空断点续作缓存目录 {resume_dir}")
        shutil.rmtree(resume_dir, ignore_errors=True)
        resume_dir = get_resume_dir(output_dir, output_stem)
    if args.no_resume:
        print("♻️ 已禁用断点续作缓存，本次将重新执行提取和LLM审查")
    else:
        print(f"🔁 断点续作缓存目录: {resume_dir}")
    retry_command = retry_command_from_args(args, input_path)
    failed_artifact_kwargs = _failed_artifact_options(input_path, output_dir, args)
    run_runtime = runtime_metadata()
    run_workspace = create_run_workspace(input_path, output_dir, output_stem)
    print(f"🗂️ 本次运行工作区: {run_workspace['run_dir']}")
    record_run_workspace_json(run_workspace, "input_manifest.json", run_input_manifest(input_path, run_runtime))
    allow_llm_cache_read = _allow_llm_cache_read(args.no_resume, getattr(args, "llm_cache_only", False))
    allow_llm_cache_write = not args.no_resume
    has_pdf_input = detect_pdf_input(input_path)
    use_mineru_default = has_pdf_input and not args.no_mineru
    if use_mineru_default and not args.mineru:
        print("📡 检测到PDF输入，默认启用MinerU提取；如需原始PDF文本提取请使用 --no-mineru")

    output_override_preview = explicit_output_path_from_args(args)
    preview_md, preview_html, preview_json = audit_artifact_paths(input_path, output_path=output_override_preview)
    extraction_route = run_extraction_route(input_path, use_mineru_default)
    scope_flags = run_scope_flags_from_args(args)
    print("🧭 运行摘要:")
    print(f"  - 输入: {input_path} ({'目录' if input_path.is_dir() else '单文件'})")
    print(f"  - 提取路线: {extraction_route}")
    print(f"  - 输出目录/产物: {preview_md.parent} / {preview_md.stem}")
    print(f"  - HTML/JSON预期: {preview_html.name} / {preview_json.name}")
    print(f"  - 断点续作缓存: {resume_dir}")
    print(f"  - 范围限制开关: {', '.join(scope_flags) if scope_flags else '无，默认尝试完整审查'}")

    resume_event(resume_dir, "init", "done", f"input={input_path}; llm={LLM_MODEL}; url={LLM_API_URL}; max_chars={args.max_chars}; use_mineru={use_mineru_default}")
    record_run_workspace_json(
        run_workspace,
        "cache_use.json",
        run_cache_use_manifest(
            resume_dir,
            args.no_resume,
            allow_llm_cache_read,
            allow_llm_cache_write,
            EXTRACT_CACHE_VERSION,
            IMAGE_SEMANTIC_CACHE_VERSION,
        ),
    )
    completed_stages = ["init", "runtime_config_loaded"]
    preflight_state = {}
    preflight_results = []

    def _record_preflight(result: PreflightResult):
        preflight_results.append(result.to_dict())
        record_run_workspace_json(run_workspace, "preflight.json", {
            "results": preflight_results,
            "updated_at": time.strftime("%F %T"),
        })
        resume_event(
            resume_dir,
            f"preflight_{result.capability}",
            "ok" if result.ok else "failed",
            result.message or "ok",
            error_class=result.error_class,
        )

    if use_mineru_default:
        print("🧪 关键能力预检: MinerU")
        mineru_preflight = run_preflight_once(preflight_state, "mineru", lambda: preflight_mineru(timeout=10))
        _record_preflight(mineru_preflight)
        if not mineru_preflight.ok:
            failure = preflight_failure_to_audit_failure(
                mineru_preflight,
                retry_command,
                completed_stages,
            )
            md_path, json_path = save_failed_audit_diagnostics(
                failure,
                input_path,
                **failed_artifact_kwargs,
                meta={"preflight_results": preflight_results},
            )
            record_run_workspace_artifacts(
                run_workspace,
                "failed",
                [md_path, json_path],
                meta={"preflight_results": preflight_results, "completed_stages": completed_stages},
            )
            print(f"❌ MinerU预检失败，未生成完整审查报告。失败诊断已保存: {md_path}, {json_path}")
            return RunResult.failed(
                failure,
                {"markdown": str(md_path), "json": str(json_path)},
                workspace=run_workspace,
                meta={"input_path": str(input_path), "preflight_results": preflight_results},
            )
        completed_stages.append("mineru_preflight")
    progress_bar(0, 5, "初始化完成")

    # ─── 阶段1：文本提取（支持单个文件/整个论文目录） ───
    extract_cache_path = resume_dir / "stage1_extract.json"
    cached_extract = None if args.no_resume else _json_load(extract_cache_path)
    extracted_file_texts = []
    if cached_extract and cached_extract.get("input") == str(input_path.resolve()) and cached_extract.get("use_mineru") == use_mineru_default and cached_extract.get("cache_version") == EXTRACT_CACHE_VERSION:
        full_text = cached_extract.get("full_text", "")
        meta = cached_extract.get("meta", {})
        extracted_file_texts = cached_extract.get("file_texts") or []
        raw_pdf = None
        use_mineru = cached_extract.get("use_mineru", use_mineru_default)
        print(f"🔁 断点续作：复用阶段1文本缓存 {extract_cache_path} ({len(full_text)}字符)")
        resume_event(resume_dir, "stage1_extract", "cache_hit", f"chars={len(full_text)}", cache=str(extract_cache_path))
        progress_bar(1, 5, "阶段1/5 文本提取缓存命中")
    else:
        full_text = None
        meta = {}
        raw_pdf = None
        use_mineru = use_mineru_default

    if full_text is None and input_path.is_dir():
        print(f"📂 检测到输入为目录，正在扫描所有论文相关文件...")
        file_classes, all_files = find_project_files(input_path)
        print(f"✅ 找到 {len(all_files)} 个相关文件:")
        for cat, files in file_classes.items():
            if not files:
                continue
            if isinstance(files, Path):
                print(f"  - {cat}: {files.name}")
            else:
                print(f"  - {cat}: {len(files)} 个文件")
        
        reference_file_set = set(file_classes.get("references") or [])
        audit_files = [p for p in all_files if p not in reference_file_set]

        def _file_audit_category(path):
            if path == file_classes.get("main_paper"):
                return "main_text"
            if path in set(file_classes.get("supplements") or []):
                return "supplement"
            if path in set(file_classes.get("data_files") or []):
                return "data_file"
            return "other"

        # 提取所有非参考文献文件文本合并；参考文献文件单独校检，避免污染主体审查
        full_text = ""
        reference_file_texts = []
        extracted_file_texts = []
        total_files = len(audit_files)
        for idx, file_path in enumerate(audit_files, 1):
            print(f"  📝 提取主体文件 [{idx}/{total_files}] {file_path.name}...")
            progress_bar(idx - 1, max(total_files, 1), f"阶段1/5 提取主体文件: {file_path.name}")
            dependency, install_command = optional_dependency_for_extension(file_path.suffix)
            if dependency:
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="missing_optional_dependency",
                    message=f"目录审查中的审查相关文件 {file_path.name} 需要安装可选依赖 {dependency}。",
                    fix_hints=[f"运行 `{install_command}` 后重试。", "或转换该文件为 PDF/文本格式后重新运行审查。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={
                        "file": str(file_path),
                        "extension": file_path.suffix.lower(),
                        "dependency": dependency,
                        "install_command": install_command,
                        "resume_dir": str(resume_dir),
                    },
                )
                md_path, json_path = save_failed_audit_diagnostics(
                    failure,
                    input_path,
                    **failed_artifact_kwargs,
                    meta={"runtime": run_runtime, "preflight_results": preflight_results},
                )
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            file_content = extract_text_from_file(file_path, max_chars_per_file=None,
                                                  use_mineru=use_mineru,
                                                  mineru_lang=args.mineru_lang,
                                                  output_dir=output_dir)
            body_text = extracted_body_text(file_content, file_path.name)
            if not body_text or body_text.startswith("[文件解析失败:"):
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="no_extractable_text",
                    message=f"未能从目录审查相关文件 {file_path.name} 提取到可审查文本。",
                    fix_hints=["检查文件是否为空、损坏、加密或需要额外依赖。", "转换该文件为 PDF/文本格式后重试，或在未来显式排除该文件。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={
                        "file": str(file_path),
                        "extension": file_path.suffix.lower(),
                        "category": _file_audit_category(file_path),
                        "extract_preview": _brief_text(file_content, 240),
                        "resume_dir": str(resume_dir),
                    },
                )
                md_path, json_path = save_failed_audit_diagnostics(
                    failure,
                    input_path,
                    **failed_artifact_kwargs,
                    meta={"runtime": run_runtime, "preflight_results": preflight_results},
                )
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            try:
                rel_path = str(file_path.relative_to(input_path))
            except Exception:
                rel_path = file_path.name
            extracted_file_texts.append({
                "file": file_path.name,
                "path": rel_path,
                "category": _file_audit_category(file_path),
                "text": file_content,
            })
            progress_bar(idx, max(total_files, 1), f"阶段1/5 已完成: {file_path.name}")
            full_text += f"\n\n=== 文件: {file_path.name} 路径: {file_path.relative_to(input_path)} ==="
            full_text += "\n" + file_content

        for idx, file_path in enumerate(file_classes.get("references") or [], 1):
            print(f"  📚 提取参考文献文件 [{idx}/{len(reference_file_set)}] {file_path.name}...")
            dependency, install_command = optional_dependency_for_extension(file_path.suffix)
            if dependency:
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="missing_optional_dependency",
                    message=f"目录审查中的参考文献文件 {file_path.name} 需要安装可选依赖 {dependency}。",
                    fix_hints=[f"运行 `{install_command}` 后重试。", "或转换该文件为 PDF/文本格式后重新运行审查。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={
                        "file": str(file_path),
                        "extension": file_path.suffix.lower(),
                        "dependency": dependency,
                        "install_command": install_command,
                        "resume_dir": str(resume_dir),
                    },
                )
                md_path, json_path = save_failed_audit_diagnostics(
                    failure,
                    input_path,
                    **failed_artifact_kwargs,
                    meta={"runtime": run_runtime, "preflight_results": preflight_results},
                )
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            reference_content = extract_text_from_file(file_path, max_chars_per_file=None,
                                                       use_mineru=use_mineru,
                                                       mineru_lang=args.mineru_lang,
                                                       output_dir=output_dir)
            if not extracted_body_text(reference_content, file_path.name):
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="no_extractable_text",
                    message=f"未能从目录审查相关参考文献文件 {file_path.name} 提取到可审查文本。",
                    fix_hints=["检查文件是否为空、损坏、加密或需要额外依赖。", "转换该文件为 PDF/文本格式后重试。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={"file": str(file_path), "extension": file_path.suffix.lower(), "resume_dir": str(resume_dir)},
                )
                md_path, json_path = save_failed_audit_diagnostics(
                    failure,
                    input_path,
                    **failed_artifact_kwargs,
                    meta={"runtime": run_runtime, "preflight_results": preflight_results},
                )
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            reference_file_texts.append(reference_content)
        
        def _class_count(v):
            if v is None:
                return 0
            if isinstance(v, Path):
                return str(v)
            try:
                return len(v)
            except TypeError:
                return str(v)

        meta = {
            "input_type": "directory",
            "total_files": len(all_files),
            "audit_files": len(audit_files),
            "reference_files": len(reference_file_set),
            "file_classes": {k: _class_count(v) for k, v in file_classes.items()},
            "total_chars": len(full_text),
            "extractor": "directory_multi_format",
            "extraction_method": "directory_multi_format",
            "size_mb": round(sum(p.stat().st_size for p in all_files if p.exists()) / 1024 / 1024, 2),
            "reference_file_text": "\n\n".join(reference_file_texts),
        }
        print(f"\n✅ 所有文件提取完成，总长度: {len(full_text)} 字符")
        progress_bar(1, 5, "阶段1/5 文本提取完成")
    elif full_text is None:
        # 单个文件走原有流程
        pdf_path = input_path
        print(f"📄 检测到输入为单个文件: {pdf_path.name}")
        single_suffix = pdf_path.suffix.lower()

        if single_suffix not in SUPPORTED_TEXT_FILE_EXTENSIONS:
            if single_suffix == ".doc":
                message = "暂不支持旧版二进制Word .doc 文件直接输入；请转换为 .docx 或 PDF 后重试。"
                hints = ["用 Word/WPS/LibreOffice 另存为 .docx。", "或导出为 PDF 后重新运行审查。"]
                error_class = "unsupported_legacy_doc"
            else:
                message = f"不支持的单文件输入类型: {single_suffix or '(无扩展名)'}。"
                hints = ["请使用 PDF、.docx、Excel、CSV、TXT 或 Markdown 文件。", "也可以把论文相关文件放入目录后进行目录审查。"]
                error_class = "unsupported_file_type"
            failure = AuditFailure(
                capability="input_extraction",
                error_class=error_class,
                message=message,
                fix_hints=hints,
                completed_stages=completed_stages,
                retry_command=retry_command,
            )
            md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs)
            record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
            return RunResult.failed(
                failure,
                {"markdown": str(md_path), "json": str(json_path)},
                workspace=run_workspace,
                meta={"input_path": str(input_path)},
            )

        if single_suffix != ".pdf":
            missing_dependency = (
                single_suffix == ".docx" and not DOCX_SUPPORTED
            ) or (
                single_suffix in {".xlsx", ".xlsm"} and not EXCEL_SUPPORTED
            )
            if missing_dependency:
                dependency, install_command = optional_dependency_for_extension(single_suffix)
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="missing_optional_dependency",
                    message=f"读取 {single_suffix} 文件需要安装可选依赖 {dependency}。",
                    fix_hints=[f"运行 `{install_command}` 后重试。", "或转换为 PDF 后重新运行审查。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={"dependency": dependency, "install_command": install_command, "resume_dir": str(resume_dir)},
                )
                md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs)
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            print(f"📖 正在提取{single_suffix}文件文本: {pdf_path}")
            full_text = extract_text_from_file(
                pdf_path,
                max_chars_per_file=None,
                use_mineru=False,
                mineru_lang=args.mineru_lang,
                output_dir=output_dir,
            )
            body_text = extracted_body_text(full_text, pdf_path.name)
            if not body_text:
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="no_extractable_text",
                    message=f"未能从 {single_suffix} 文件中提取到可审查文本。",
                    fix_hints=["检查文件是否为空、损坏或受保护。", "尝试另存为 .docx/PDF 后重试。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                )
                md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs)
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            meta = {
                "input_type": "file",
                "source_file": pdf_path.name,
                "size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2),
                "total_chars": len(full_text),
                "chars_sent": len(full_text),
                "extractor": "single_file_multi_format",
                "extraction_method": f"{single_suffix.lstrip('.')}_text",
            }
            extracted_file_texts = [{
                "file": pdf_path.name,
                "path": pdf_path.name,
                "category": "main_text",
                "text": full_text,
            }]
            raw_pdf = None
            print(f"✅ 提取完成: {meta['total_chars']} 字符（全文保留）")
            progress_bar(1, 5, "阶段1/5 单文件文本提取完成")

        if single_suffix == ".pdf" and use_mineru:
            print(f"📡 [MinerU] 正在将PDF转为Markdown: {pdf_path.name}")
            md_text, md_meta = mineru_extract(pdf_path, language=args.mineru_lang, output_dir=output_dir)
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
                extracted_file_texts = [{
                    "file": pdf_path.name,
                    "path": pdf_path.name,
                    "category": "main_text",
                    "text": full_text,
                }]
                print(f"✅ MinerU提取完成: {len(md_text)} 字符（全文保留）")
                progress_bar(1, 5, "阶段1/5 MinerU文本提取完成")
            else:
                err = md_meta.get("error", "未知错误") if md_meta else "未知错误"
                print(f"❌ MinerU提取失败: {err}")
                print(f"⚠️ 降级使用原始PDF文本提取...")
                use_mineru = False

        if single_suffix == ".pdf" and (not use_mineru or full_text is None):
            print(f"📖 正在提取PDF文本: {pdf_path}")
            # extract_pdf_text的max_chars参数传大值以获取全文
            full_text, meta, raw_pdf = extract_pdf_text(str(pdf_path), max_chars=999999)
            if not full_text:
                print("❌ 未能从PDF中提取到文本（可能是扫描件或加密PDF）")
                print("💡 建议: 使用 --mineru 参数通过MinerU API提取（支持OCR）")
                failure = AuditFailure(
                    capability="input_extraction",
                    error_class="no_extractable_text",
                    message="未能从PDF中提取到文本（可能是扫描件或加密PDF）。",
                    fix_hints=["检查PDF是否加密或为扫描件。", "确认MinerU配置可用后重试。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                )
                md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs)
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            print(f"✅ 提取完成: {meta['total_chars']} 字符（全文保留）")
            extracted_file_texts = [{
                "file": pdf_path.name,
                "path": pdf_path.name,
                "category": "main_text",
                "text": full_text,
            }]
            progress_bar(1, 5, "阶段1/5 PDF文本提取完成")

    meta = normalize_run_meta(meta, input_path, full_text)
    meta["runtime"] = run_runtime
    meta["paper_identity"] = extract_paper_identity(full_text, input_path)
    meta["preflight_results"] = preflight_results
    meta["cross_file_consistency_audit"] = build_cross_file_consistency_audit(extracted_file_texts, root_path=input_path)
    completed_stages.append("stage1_text_extraction")

    if not args.no_resume and full_text:
        _json_save(extract_cache_path, {
            "input": str(input_path.resolve()),
            "cache_version": EXTRACT_CACHE_VERSION,
            "use_mineru": use_mineru,
            "mineru_lang": args.mineru_lang,
            "full_text": full_text,
            "meta": meta,
            "file_texts": extracted_file_texts,
            "saved_at": time.strftime("%F %T"),
        })
        resume_event(resume_dir, "stage1_extract", "saved", f"chars={len(full_text)}; use_mineru={use_mineru}", cache=str(extract_cache_path))

    # ─── 朱雀AI文本检测（可选） ───
    if args.ai_detect:
        launch_zhuque_ai_detect(full_text)

    # ─── AI图片检测兼容参数 ───
    if args.image_detect:
        print("ℹ️ --image-detect 已改为兼容参数；图片检测将在阶段4自动调用图像语义分析与imagedetector子工具，不会打开网页或要求手动上传。")

    # ─── 参考文献剥离与单独校检 ───
    audit_text, references_text = split_references_from_text(full_text)
    reference_file_text = meta.pop("reference_file_text", "")
    if reference_file_text:
        references_text = (references_text + "\n\n" + reference_file_text).strip()
    reference_online_cache_path = resume_dir / "reference_online_cache.json"
    reference_online_enabled = bool(references_text) and not args.no_reference_online
    reference_online_cache = {} if args.no_resume else (_json_load(reference_online_cache_path, {}) or {})
    if reference_online_enabled:
        print(f"🔎 参考文献在线检索已启用: 上限{args.reference_online_limit}条, 超时{args.reference_timeout}s")
    reference_audit = audit_references(
        references_text,
        online=reference_online_enabled,
        online_limit=args.reference_online_limit,
        timeout=args.reference_timeout,
        cache=reference_online_cache,
    )
    if reference_online_enabled and not args.no_resume:
        _json_save(reference_online_cache_path, reference_online_cache)
        resume_event(
            resume_dir,
            "stage1_reference_online",
            "saved",
            f"checked={reference_audit.get('online_checked', 0)}; cache_entries={len(reference_online_cache)}",
            cache=str(reference_online_cache_path),
        )
    if references_text:
        meta["references_excluded_from_main_audit"] = True
        meta["reference_chars"] = len(references_text)
        meta["reference_count"] = reference_audit.get("reference_count", 0)
        meta["reference_audit"] = reference_audit
        print(f"📚 已从主体审查中剥离参考文献: {meta['reference_count']}条, {len(references_text)}字符；将单独校检")
        resume_event(resume_dir, "stage1_references", "done", f"refs={meta['reference_count']}; chars={len(references_text)}")
    else:
        meta["references_excluded_from_main_audit"] = False
        meta["reference_audit"] = reference_audit
        print("📚 未识别到独立参考文献章节，主体审查不做引用剥离")
    completed_stages.append("stage1_reference_audit")

    # ─── 代码仓库与在线部署资源可用性校检 ───
    resource_online_cache_path = resume_dir / "resource_online_cache.json"
    resource_online_cache = {} if args.no_resume else (_json_load(resource_online_cache_path, {}) or {})
    resource_online_enabled = not getattr(args, "no_resource_online", False)
    resource_audit = audit_resources(
        full_text,
        online=resource_online_enabled,
        timeout=getattr(args, "resource_timeout", 10),
        cache=resource_online_cache,
    )
    if resource_online_enabled and not args.no_resume:
        _json_save(resource_online_cache_path, resource_online_cache)
        resume_event(
            resume_dir,
            "stage1_resource_online",
            "saved",
            f"checked={resource_audit.get('online_checked', 0)}; cache_entries={len(resource_online_cache)}",
            cache=str(resource_online_cache_path),
        )
    meta["resource_count"] = resource_audit.get("resource_count", 0)
    meta["resource_audit"] = resource_audit
    if resource_audit.get("resource_count"):
        print(f"🔗 已识别代码仓库/在线资源: {resource_audit.get('resource_count')}项；在线检测{resource_audit.get('online_checked', 0)}项")
    else:
        print("🔗 未识别到代码仓库或论文部署的在线资源链接")
    completed_stages.append("stage1_resource_audit")

    # ─── 阶段2：本地统计检测（使用全文，统计不截断） ───
    progress_bar(1, 5, "阶段2/5 开始本地统计检测")
    print(f"🔢 正在执行本地统计检测...")
    stat_result = local_stat_check(audit_text)
    benford_str = f"{round(stat_result['benford_deviation'],3)}" if stat_result['benford_deviation'] else 'N/A'
    print(f"✅ 统计检测完成: Benford偏差={benford_str}, p值异常={stat_result['p_value_abnormal']}, 数字数={stat_result['number_count']}")
    resume_event(resume_dir, "stage2_stat", "done", f"numbers={stat_result['number_count']}; benford={benford_str}")
    progress_bar(2, 5, "阶段2/5 本地统计检测完成")
    completed_stages.append("stage2_stat_check")

    # ─── 阶段3：智能分块 + LLM语义审查（冗余机制） ───
    print("🧪 关键能力预检: 文本语义审查LLM")
    text_llm_preflight = run_preflight_once(preflight_state, "text_llm", lambda: preflight_text_llm(timeout=min(30, LLM_TIMEOUT)))
    _record_preflight(text_llm_preflight)
    meta["preflight_results"] = preflight_results
    if not text_llm_preflight.ok:
        failure = preflight_failure_to_audit_failure(
            text_llm_preflight,
            retry_command,
            completed_stages,
        )
        md_path, json_path = save_failed_audit_diagnostics(
            failure,
            input_path,
            **failed_artifact_kwargs,
            meta=meta,
        )
        record_run_workspace_artifacts(
            run_workspace,
            "failed",
            [md_path, json_path],
            meta={"preflight_results": preflight_results, "completed_stages": completed_stages},
        )
        print(f"❌ 文本LLM预检失败，未生成完整审查报告。失败诊断已保存: {md_path}, {json_path}")
        return RunResult.failed(
            failure,
            {"markdown": str(md_path), "json": str(json_path)},
            workspace=run_workspace,
            meta={"input_path": str(input_path), "preflight_results": preflight_results},
        )
    completed_stages.append("text_llm_preflight")

    chunk_size = min(int(args.max_chars), 4096)  # LLM单块硬上限4096字符
    overlap = min(512, chunk_size // 8)  # 重叠区约12.5%，最多512字符

    chunks = smart_chunk_text(audit_text, chunk_size=chunk_size, overlap=overlap)
    total_chunks = len(chunks)
    llm_cache_key = _text_fingerprint(audit_text, f"{LLM_API_URL}|{LLM_MODEL}|{chunk_size}|{overlap}|refs_excluded")
    llm_cache_dir = resume_dir / f"llm_{llm_cache_key}"
    llm_cache_dir.mkdir(parents=True, exist_ok=True)
    resume_event(resume_dir, "stage3_llm", "start", f"chunks={total_chunks}; chunk_size={chunk_size}; overlap={overlap}", cache_dir=str(llm_cache_dir))

    progress_bar(2, 5, f"阶段3/5 开始LLM审查：{total_chunks}块")

    if total_chunks == 1:
        # 短论文：直接全文审查
        print(f"🔍 论文长度({len(audit_text)}字符，已排除参考文献)在单块范围内，直接审查...")
        single_cache = llm_cache_dir / "chunk_0000.json"
        cached = _json_load(single_cache) if allow_llm_cache_read else None
        if cached:
            print(f"🔁 断点续作：复用LLM审查缓存 {single_cache}")
            resume_event(resume_dir, "stage3_llm_chunk", "cache_hit", "chunk=1/1", cache=str(single_cache))
            report = cached.get("report", {"parse_error": True, "raw_output": "缓存格式异常"})
        else:
            try:
                raw_content = ""
                report = {"parse_error": True, "raw_output": ""}
                schema_errors = []
                for schema_attempt in range(2):
                    raw_content = call_llm(audit_text)
                    report = parse_report(raw_content)
                    if not report.get("parse_error"):
                        break
                    schema_errors = report.get("schema_errors") or [report.get("raw_output", "")[:180]]
                    if schema_attempt == 0:
                        print(f"  ↻ LLM证据schema不合格，重试1次: {schema_errors}")
                if report.get("parse_error"):
                    raise RuntimeError(f"LLM返回结构不符合证据schema: {schema_errors}")
                if allow_llm_cache_write:
                    _json_save(single_cache, {"report": report, "raw_content": raw_content, "saved_at": time.strftime("%F %T")})
                    resume_event(resume_dir, "stage3_llm_chunk", "saved", "chunk=1/1", cache=str(single_cache))
            except Exception as e:
                print(f"❌ LLM调用失败: {e}")
                failure = AuditFailure(
                    capability="text_llm",
                    error_class="schema_error",
                    message=f"LLM语义审查失败或返回结构不符合证据schema: {e}",
                    fix_hints=["检查文本LLM服务稳定性和提示词输出格式。", "稍后重试或更换稳定的文本语义审查服务。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={"raw_error": str(e), "chunk": "1/1"},
                )
                md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs, meta=meta)
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
    else:
        # 长论文：分块审查 + 合并
        print(f"🔍 论文较长({len(audit_text)}字符，已排除参考文献)，分为{total_chunks}块(每块≤{chunk_size}字符，重叠{overlap}字符)进行审查...")
        chunk_reports = [None] * total_chunks
        failed_chunks = []

        def _run_chunk_once(chunk_text, chunk_idx, retry=False):
            chunk_cache = llm_cache_dir / f"chunk_{chunk_idx:04d}.json"
            print(("  🔁 重试" if retry else "  📝 审查") + f"第{chunk_idx+1}/{total_chunks}块({len(chunk_text)}字符)...")
            raw_content = call_llm(chunk_text, chunk_info=(chunk_idx, total_chunks))
            chunk_report = parse_report(raw_content)
            if chunk_report.get("parse_error"):
                raise RuntimeError(f"LLM返回解析失败: {str(chunk_report.get('raw_output',''))[:180]}")
            if allow_llm_cache_write:
                _json_save(chunk_cache, {"report": chunk_report, "raw_content": raw_content, "saved_at": time.strftime("%F %T"), "chunk_index": chunk_idx, "total_chunks": total_chunks, "status": "ok", "retry": retry})
                resume_event(resume_dir, "stage3_llm_chunk", "retry_saved" if retry else "saved", f"chunk={chunk_idx+1}/{total_chunks}; chars={len(chunk_text)}", cache=str(chunk_cache))
            return chunk_report

        for chunk_text, chunk_idx, _ in chunks:
            progress_bar(chunk_idx, total_chunks, f"阶段3/5 LLM审查中：第{chunk_idx+1}/{total_chunks}块")
            chunk_cache = llm_cache_dir / f"chunk_{chunk_idx:04d}.json"
            cached = _json_load(chunk_cache) if allow_llm_cache_read else None
            if cached and cached.get("status") == "ok" and cached.get("report") and not cached.get("report", {}).get("parse_error"):
                print(f"     ↳ 断点续作：复用第{chunk_idx+1}块成功LLM缓存")
                resume_event(resume_dir, "stage3_llm_chunk", "cache_hit", f"chunk={chunk_idx+1}/{total_chunks}", cache=str(chunk_cache))
                chunk_reports[chunk_idx] = cached.get("report")
            elif getattr(args, "llm_cache_only", False):
                print(f"     ↳ cache-only：第{chunk_idx+1}块无成功缓存，跳过API调用")
                failed_chunks.append((chunk_text, chunk_idx, "cache_only_no_success_cache"))
                resume_event(resume_dir, "stage3_llm_chunk", "cache_only_miss", f"chunk={chunk_idx+1}/{total_chunks}", cache=str(chunk_cache))
            else:
                try:
                    chunk_reports[chunk_idx] = _run_chunk_once(chunk_text, chunk_idx, retry=False)
                except Exception as e:
                    print(f"  ⚠️ 第{chunk_idx+1}块LLM调用/解析失败，先记录并继续其他块: {e}")
                    failed_chunks.append((chunk_text, chunk_idx, str(e)))
                    if allow_llm_cache_write:
                        _json_save(chunk_cache, {"report": {"parse_error": True, "raw_output": str(e)}, "raw_content": str(e), "saved_at": time.strftime("%F %T"), "chunk_index": chunk_idx, "total_chunks": total_chunks, "status": "failed_pending_retry"})
                        resume_event(resume_dir, "stage3_llm_chunk", "failed_pending_retry", f"chunk={chunk_idx+1}/{total_chunks}; error={e}", cache=str(chunk_cache))
            if chunk_reports[chunk_idx] and not chunk_reports[chunk_idx].get("parse_error"):
                print(f"     → 第{chunk_idx+1}块风险: {chunk_reports[chunk_idx].get('risk_level', '未知')}")
            progress_bar(chunk_idx + 1, total_chunks, f"阶段3/5 LLM审查完成：第{chunk_idx+1}/{total_chunks}块")

        if failed_chunks:
            print(f"🔁 首轮完成，按顺序重试失败块: {[idx+1 for _, idx, _ in failed_chunks]}")
            resume_event(resume_dir, "stage3_llm_retry", "start", f"failed_chunks={[idx+1 for _, idx, _ in failed_chunks]}; cache_only={getattr(args, 'llm_cache_only', False)}")
            still_failed = []
            if getattr(args, "llm_cache_only", False):
                still_failed = [(idx, first_error) for _, idx, first_error in failed_chunks]
                print("⚠️ cache-only模式：不调用API重试，直接用已有成功缓存生成部分报告。")
            else:
                for chunk_text, chunk_idx, first_error in failed_chunks:
                    try:
                        chunk_reports[chunk_idx] = _run_chunk_once(chunk_text, chunk_idx, retry=True)
                        print(f"     ✅ 第{chunk_idx+1}块重试成功")
                    except Exception as e:
                        print(f"     ❌ 第{chunk_idx+1}块重试仍失败: {e}")
                        still_failed.append((chunk_idx, str(e)))
                        chunk_cache = llm_cache_dir / f"chunk_{chunk_idx:04d}.json"
                        if allow_llm_cache_write:
                            _json_save(chunk_cache, {"report": {"parse_error": True, "raw_output": str(e)}, "raw_content": str(e), "saved_at": time.strftime("%F %T"), "chunk_index": chunk_idx, "total_chunks": total_chunks, "status": "failed_final", "first_error": first_error})
                            resume_event(resume_dir, "stage3_llm_chunk", "failed_final", f"chunk={chunk_idx+1}/{total_chunks}; error={e}", cache=str(chunk_cache))
            if still_failed:
                failed_nums = [idx + 1 for idx, _ in still_failed]
                detail = "; ".join([f"第{idx+1}块: {err}" for idx, err in still_failed])
                resume_event(resume_dir, "stage3_llm_retry", "still_failed", f"still_failed={failed_nums}; strict={args.strict_failed_chunks}")
                failure = AuditFailure(
                    capability="text_llm",
                    error_class="schema_error",
                    message="LLM分块重试后仍失败，停止生成完整审查报告: " + detail,
                    fix_hints=["检查文本LLM服务稳定性和严格证据schema输出。", "更换稳定服务或稍后重试。"],
                    completed_stages=completed_stages,
                    retry_command=retry_command,
                    details={"failed_chunks": failed_nums, "detail": detail},
                )
                md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs, meta=meta)
                record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
                return RunResult.failed(
                    failure,
                    {"markdown": str(md_path), "json": str(json_path)},
                    workspace=run_workspace,
                    meta={"input_path": str(input_path)},
                )
            else:
                resume_event(resume_dir, "stage3_llm_retry", "done", "all failed chunks recovered")

        successful_count = sum(1 for r in chunk_reports if r is not None and not r.get("parse_error"))
        failed_final = []
        for idx in range(total_chunks):
            if chunk_reports[idx] is None or chunk_reports[idx].get("parse_error"):
                failed_final.append(idx + 1)
        meta["llm_success_chunks"] = successful_count
        meta["llm_failed_chunks"] = failed_final
        meta["llm_coverage"] = f"{successful_count}/{total_chunks}"
        meta["llm_partial_report"] = bool(failed_final)

        chunk_reports = [r for r in chunk_reports if r is not None and not r.get("parse_error")]
        if not chunk_reports:
            message = f"所有LLM分块均失败，无法生成语义审查报告。失败块: {failed_final}。"
            resume_event(resume_dir, "stage4_merge", "skipped_no_success", message)
            failure = AuditFailure(
                capability="text_llm",
                error_class="schema_error",
                message=message,
                fix_hints=["检查文本LLM服务和证据schema输出。", "更换稳定服务后重试。"],
                completed_stages=completed_stages,
                retry_command=retry_command,
                details={"failed_chunks": failed_final},
            )
            md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs, meta=meta)
            record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
            return RunResult.failed(
                failure,
                {"markdown": str(md_path), "json": str(json_path)},
                workspace=run_workspace,
                meta={"input_path": str(input_path)},
            )
        else:

            progress_bar(3, 5, "阶段3/5 LLM审查完成")
            # 合并所有块的审查结果
            progress_bar(3, 5, "阶段4/5 开始合并审查结果")
            print(f"🔗 正在合并{len(chunk_reports)}块审查结果...")
            report = merge_chunk_reports(chunk_reports, stat_result)
            if report.get("_merged_from"):
                print(f"✅ 合并完成: 来自{report['_merged_from']}块，共{len(report.get('checks', []))}个检查项")
            meta["chunk_count"] = total_chunks
            meta["chunk_size"] = chunk_size
            meta["overlap"] = overlap
            if meta.get("llm_partial_report"):
                warning = f"注意：本报告仅覆盖 {meta.get('llm_coverage')} 个LLM分块；失败块: {meta.get('llm_failed_chunks')}。结论不完整，建议换稳定API后断点续跑。"
                report["_partial_warning"] = warning
                report["summary"] = warning + " " + str(report.get("summary", ""))
            resume_event(resume_dir, "stage4_merge", "done", f"checks={len(report.get('checks', [])) if isinstance(report, dict) else 'N/A'}; coverage={meta.get('llm_coverage')}")
            progress_bar(4, 5, "阶段4/5 审查结果合并完成")

    # ─── 图像合理性检测：使用MinerU已保存zip中的图片/目录图片生成报告清单 ───
    image_semantic_cache_path = resume_dir / "image_semantic_cache.json"
    image_semantic_local_cache_path = output_dir / "image_semantic_cache.json"
    image_semantic_cache = {} if args.no_resume else _load_merged_json_dicts(
        image_semantic_local_cache_path,
        image_semantic_cache_path,
    )
    image_detector_cache_path = resume_dir / "image_detector_cache.json"
    image_detector_cache = {} if args.no_resume else (_json_load(image_detector_cache_path, {}) or {})
    image_semantic_enabled = not args.no_image_semantic and bool(GLM_API_KEY)
    image_detector_enabled = not args.no_image_detector
    if not args.no_image_semantic and not GLM_API_KEY:
        print("⚠️ 图像语义分析API Key未配置，图像语义分析将跳过；本地合理性检测和imagedetector清单仍会生成")
    image_semantic_cache_save = None
    if image_semantic_enabled and not args.no_resume:
        def image_semantic_cache_save():
            _json_save(image_semantic_cache_path, image_semantic_cache)
            _json_save(image_semantic_local_cache_path, image_semantic_cache)
    image_detector_cache_save = None
    if image_detector_enabled and not args.no_resume:
        image_detector_cache_save = lambda: _json_save(image_detector_cache_path, image_detector_cache)
    image_audit = build_image_audit(
        str(input_path),
        output_dir=output_dir,
        limit=args.image_audit_limit,
        semantic=image_semantic_enabled,
        semantic_limit=args.image_semantic_limit,
        semantic_timeout=args.image_semantic_timeout,
        semantic_cache=image_semantic_cache,
        semantic_cache_save=image_semantic_cache_save,
        detector=image_detector_enabled,
        detector_limit=args.image_detector_limit,
        detector_timeout=args.image_detector_timeout,
        detector_cache=image_detector_cache,
        detector_cache_save=image_detector_cache_save,
    )
    if image_semantic_enabled and not args.no_resume:
        _json_save(image_semantic_cache_path, image_semantic_cache)
        _json_save(image_semantic_local_cache_path, image_semantic_cache)
        resume_event(
            resume_dir,
            "stage4_image_semantic",
            "saved",
            f"semantic_checked={image_audit.get('semantic_checked', 0)}; cache_entries={len(image_semantic_cache)}; local_cache={image_semantic_local_cache_path}",
            cache=str(image_semantic_cache_path),
        )
    if image_detector_enabled and not args.no_resume:
        _json_save(image_detector_cache_path, image_detector_cache)
        resume_event(
            resume_dir,
            "stage4_image_detector",
            "saved",
            f"detector_checked={image_audit.get('detector_checked', 0)}; cache_entries={len(image_detector_cache)}",
            cache=str(image_detector_cache_path),
        )
    meta["image_audit"] = image_audit
    if image_audit.get("image_count"):
        print(f"🖼️ 图像检测完成: 本地{image_audit.get('checked_count')}/{image_audit.get('image_count')}张；图像语义分析 {image_audit.get('semantic_checked')}张；imagedetector {image_audit.get('detector_checked')}张")
        manifest_path = save_image_review_manifest(image_audit, output_dir)
        if manifest_path:
            meta["image_review_manifest"] = str(manifest_path)
            print(f"🖼️ 图像AI检测结果清单已保存: {manifest_path}")
    failed_capability, failed_message, failed_details = coverage_blocking_failure(meta)
    if failed_capability:
        failure = AuditFailure(
            capability=failed_capability,
            error_class="provider_unavailable",
            message=failed_message,
            fix_hints=["检查第三方服务配置、网络情况和服务商状态后重试。"],
            completed_stages=completed_stages,
            retry_command=retry_command,
            details=failed_details,
        )
        md_path, json_path = save_failed_audit_diagnostics(failure, input_path, **failed_artifact_kwargs, meta=meta)
        record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta={"completed_stages": completed_stages})
        return RunResult.failed(
            failure,
            {"markdown": str(md_path), "json": str(json_path)},
            workspace=run_workspace,
            meta={"input_path": str(input_path)},
        )
    report = apply_risk_rules(report, stat_result=stat_result, image_audit=meta.get("image_audit"))
    meta["risk_rule_version"] = RISK_RULE_VERSION
    meta["evidence_chain_audit"] = build_evidence_chain_audit(
        full_text,
        extracted_file_texts,
        report,
        meta,
        stat_result,
    )

    # ─── 阶段5：生成报告 ───
    progress_bar(4, 5, "阶段5/5 开始生成报告")
    limited_reasons = audit_limited_reasons(args, meta, has_pdf_input=has_pdf_input)
    apply_audit_artifact_type(meta, limited_reasons)
    report_actions_port = int(getattr(args, "report_actions_port", 8765) or 8765)
    meta["report_actions"] = {
        "host": "127.0.0.1",
        "port": report_actions_port,
        "url": report_action_service_url("127.0.0.1", report_actions_port),
        "auto_start": not bool(getattr(args, "no_open", False)),
    }
    # 确定输出路径（优先HTML）
    output_override = explicit_output_path_from_args(args)
    output_path, html_output_path, json_path = audit_artifact_paths(
        input_path,
        artifact_type=meta.get("artifact_type", "complete"),
        output_path=output_override,
    )
    meta["artifact_paths"] = {
        "markdown": str(output_path),
        "html": str(html_output_path),
        "json": str(json_path),
    }
    meta["followups_dir"] = str(html_output_path.parent / "followups")
    report_input = str(input_path)
    md_report = format_report(report, report_input, meta, stat_result)

    # 生成HTML报告
    html_report = format_html_report(report, report_input, meta, stat_result)

    # 写入Markdown报告
    output_path.write_text(md_report, encoding="utf-8")
    print(f"✅ Markdown报告已保存: {output_path}")
    resume_event(resume_dir, "stage5_report", "markdown_saved", str(output_path))

    # 写入HTML报告
    html_output_path.write_text(html_report, encoding="utf-8")
    print(f"✅ HTML报告已保存: {html_output_path}")
    resume_event(resume_dir, "stage5_report", "html_saved", str(html_output_path))

    if args.json:
        json_path.write_text(
            json.dumps({"report_type": meta.get("artifact_type", "complete"), "llm_report": report, "stat_result": stat_result, "meta": meta, "reference_audit": reference_audit, "resource_audit": resource_audit, "cross_file_consistency_audit": meta.get("cross_file_consistency_audit"), "evidence_chain_audit": meta.get("evidence_chain_audit")},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"✅ 原始JSON已保存: {json_path}")

    record_run_workspace_artifacts(
        run_workspace,
        meta.get("artifact_type", "complete"),
        [output_path, html_output_path, json_path],
        meta={"artifact_type": meta.get("artifact_type"), "limited_reasons": meta.get("limited_reasons", [])},
    )

    resume_event(resume_dir, "all", "done", "audit completed")
    progress_bar(5, 5, "阶段5/5 全部完成")
    print(f"🧾 完整日志: {_run_logging._RUN_LOG_FILE}")

    # 自动打开HTML报告
    if args.no_open:
        print(f"🌐 已跳过自动打开HTML报告: {html_output_path}")
    else:
        action_status = ensure_report_action_service(
            port=report_actions_port,
            log_path=Path(run_workspace["run_dir"]) / "report_actions.log",
        )
        meta["report_actions"]["service_status"] = action_status.get("status")
        if action_status.get("ok"):
            if action_status.get("status") == "already_running":
                print(f"🌐 HTML动作服务已在运行: {action_status.get('url')}")
            else:
                print(f"🌐 HTML动作服务已自动启动: {action_status.get('url')}")
        else:
            print(f"⚠️ HTML动作服务自动启动失败: {action_status.get('error') or action_status.get('status')}，报告仍可打开")
        try:
            open_html_artifact(html_output_path)
            print(f"🌐 已在浏览器中打开HTML报告")
        except Exception as e:
            print(f"⚠️ 自动打开浏览器失败: {e}，请手动打开: {html_output_path}")

    # 打印摘要
    if not report.get("parse_error"):
        risk = report.get("risk_level", "未知")
        print(f"\n📊 复核优先级: {risk} | 总评: {report.get('summary', 'N/A')}")

    artifact_paths = {"markdown": str(output_path), "html": str(html_output_path)}
    if json_path.exists():
        artifact_paths["json"] = str(json_path)
    result_factory = RunResult.limited if meta.get("artifact_type") == "limited" else RunResult.complete
    return result_factory(artifact_paths, workspace=run_workspace, meta=meta)

def main():
    global LLM_TIMEOUT, LLM_RETRIES
    parser = argparse.ArgumentParser(
        description="学术论文自动审查工具（耿同学标准 + MinerU）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 默认：PDF优先使用MinerU提取 + 完整审查
  python paper_audit.py paper.pdf

  # 调试/范围受限：禁用MinerU，不作为完整正式审查
  python paper_audit.py paper.pdf --no-mineru

  # 指定输出路径
  python paper_audit.py paper.pdf --mineru -o report.md --json
  
  # 更新欺诈模式知识库（从PubPeer评论自动提取新pattern）
  python paper_audit.py --update-patterns pubpeer_comments.txt
""")
    parser.add_argument("pdf_path", nargs='?', help="待审查的文件路径或论文目录路径（支持PDF、Word .docx、Excel、Supplement等，更新/服务模式下无需提供）")
    parser.add_argument("--serve-report-actions", action="store_true",
                        help="启动本机HTML报告动作服务：一键生成PubPeer comment和期刊letter")
    parser.add_argument("--report-actions-port", type=int, default=8765,
                        help="HTML报告动作服务端口（默认8765，仅监听127.0.0.1）")
    parser.add_argument("--serve-web", action="store_true",
                        help="启动本机Web Runner工作台：通过浏览器运行审查、查看日志和打开产物")
    parser.add_argument("--gui", action="store_true",
                        help="启动本机桌面GUI软件：选择输入、运行审查并直接打开报告产物")
    parser.add_argument("--web-port", type=int, default=8765,
                        help="Web Runner端口（默认8765，仅监听127.0.0.1）")
    parser.add_argument("--update-patterns", metavar="COMMENTS_FILE", 
                        help="从PubPeer评论文本文件中自动提取新的欺诈模式，更新知识库")
    parser.add_argument("--mineru", action="store_true",
                        help="使用MinerU API将PDF转为Markdown再审查（PDF默认已启用，保留该参数用于兼容旧命令）")
    parser.add_argument("--mineru-model", default="vlm",
                        choices=["pipeline", "vlm", "MinerU-HTML"],
                        help="MinerU模型版本（默认vlm，仅Precision API生效）")
    parser.add_argument("--mineru-lang", default="ch",
                        help="MinerU OCR语言（默认ch=中英，en=英文，japan=日文）")
    parser.add_argument("--no-mineru", action="store_true",
                        help="调试/范围受限：禁用MinerU；不能作为完整正式审查")
    parser.add_argument("--max-chars", type=int, default=4096,
                        help="LLM分块单块最大字符数（默认4096；超过4096会自动压到4096）")
    parser.add_argument("--output", "-o", help="输出报告文件路径（默认输出到同目录）")
    parser.add_argument("--json", action="store_true", help="同时保存原始JSON结果")
    parser.add_argument("--ai-detect", action="store_true", help="开启腾讯朱雀AI文本检测：自动复制文本到剪贴板+打开检测页面")
    parser.add_argument("--image-detect", action="store_true", help="兼容旧参数：图片检测已默认自动执行，不再打开网页或要求手动上传")
    parser.add_argument("--image-audit-limit", type=int, default=None,
                        help="报告中纳入图像合理性检测的图片数量上限（默认全部；设置后为范围受限审查）")
    parser.add_argument("--no-image-semantic", action="store_true",
                        help="调试/范围受限：关闭图像语义分析；存在可检测图片时不能作为完整正式审查")
    parser.add_argument("--image-semantic-limit", type=int, default=None,
                        help="调用图像语义分析的图片数量上限（默认全部；设置后为范围受限审查）")
    parser.add_argument("--image-semantic-timeout", type=int, default=45,
                        help="单张图片图像语义分析请求超时时间秒数（默认45）")
    parser.add_argument("--no-image-detector", action="store_true",
                        help="调试/范围受限：关闭imagedetector.com自动图片AI概率检测；存在可检测图片时不能作为完整正式审查")
    parser.add_argument("--image-detector-limit", type=int, default=None,
                        help="自动调用imagedetector.com检测的图片数量上限（默认全部；设置后为范围受限审查）")
    parser.add_argument("--image-detector-timeout", type=int, default=60,
                        help="单张图片imagedetector自动检测超时时间秒数（默认60）")
    parser.add_argument("--no-reference-online", action="store_true",
                        help="调试/范围受限：关闭参考文献在线真实性检索；识别到参考文献时不能作为完整正式审查")
    parser.add_argument("--reference-online-limit", type=int, default=None,
                        help="参考文献在线检索条数上限（默认全部；设置后为范围受限审查）")
    parser.add_argument("--reference-timeout", type=int, default=10,
                        help="单个参考文献外部检索源超时时间秒数（默认10）")
    parser.add_argument("--no-resource-online", action="store_true",
                        help="调试/范围受限：关闭代码仓库与在线资源可用性校检；识别到资源时不能作为完整正式审查")
    parser.add_argument("--resource-timeout", type=int, default=10,
                        help="单个代码仓库/在线资源可用性请求超时时间秒数（默认10）")
    parser.add_argument("--no-resume", action="store_true",
                        help="禁用断点续作缓存，强制重新提取文本和重新LLM审查")
    parser.add_argument("--fresh", action="store_true",
                        help="运行前清空本输入的断点续作缓存，然后重新开始；默认不清空缓存并自动续跑")
    parser.add_argument("--llm-timeout", type=int, default=LLM_TIMEOUT,
                        help=f"单次LLM请求超时时间秒数（默认{LLM_TIMEOUT}；不稳定网关可调小以更快跳过）")
    parser.add_argument("--llm-retries", type=int, default=LLM_RETRIES,
                        help=f"每次LLM调用内部重试次数（默认{LLM_RETRIES}，即最多{LLM_RETRIES + 1}次尝试）")
    parser.add_argument("--strict-failed-chunks", action="store_true",
                        help="严格模式：失败块首轮+补跑仍失败时停止生成报告；当前默认仍生成覆盖率受限报告，后续将改为失败诊断")
    parser.add_argument("--llm-cache-only", action="store_true",
                        help="调试/范围受限：只复用已有成功LLM分块缓存，不再调用API；不能作为完整正式审查")
    parser.add_argument("--no-open", action="store_true",
                        help="生成报告后不自动打开HTML报告，适合CI、服务器和批处理环境")
    args = parser.parse_args()
    if getattr(args, "max_chars", 4096) > 4096:
        print(f"⚠️ --max-chars={args.max_chars} 超过4096，已自动调整为4096")
        args.max_chars = 4096
    if getattr(args, "max_chars", 4096) < 512:
        print(f"⚠️ --max-chars={args.max_chars} 过小，已自动调整为512")
        args.max_chars = 512
    LLM_TIMEOUT = max(10, int(getattr(args, "llm_timeout", LLM_TIMEOUT) or LLM_TIMEOUT))
    LLM_RETRIES = max(0, int(getattr(args, "llm_retries", LLM_RETRIES) or 0))

    # ─── 知识库更新模式 ───
    if args.update_patterns:
        apply_runtime_config(load_runtime_config())
        return update_patterns(args.update_patterns)
    if args.serve_report_actions:
        apply_runtime_config(load_runtime_config())
        return serve_report_actions(port=args.report_actions_port)
    if args.serve_web:
        apply_runtime_config(load_runtime_config())
        return serve_web_runner(port=args.web_port, open_browser=not args.no_open)
    if args.gui:
        return gui_main()

    # ─── 正常审查模式 ───
    if not args.pdf_path:
        parser.error("审查模式需要提供path参数（文件或目录，或使用 --update-patterns / --serve-web / --gui 更新知识库或启动服务）")

    run_request = RunRequest.from_args(args)
    return run_audit(run_request, args).exit_code


if __name__ == "__main__":
    exit(main())
