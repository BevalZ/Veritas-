import json
import io
import types
import subprocess
import sys
import threading
import time
from pathlib import Path
import zipfile

import paper_audit
import veritas
from veritas.models import AuditReportModel, EvidenceFinding, audit_report_from_dict, model_to_dict
from veritas.renderers import render_html_report, render_markdown_report


def test_runtime_config_validation_reports_missing_required_config():
    cfg = paper_audit.default_runtime_config()

    errors = cfg.validation_errors()

    assert {"capability": "text_llm", "field": "api_key", "error": "missing_required_config"} in errors
    assert {"capability": "mineru", "field": "api_key", "error": "missing_required_config"} in errors


def test_load_runtime_config_reads_explicit_config_module(monkeypatch):
    fake_config = types.SimpleNamespace(
        LLM_API_KEY="llm-key",
        LLM_API_URL="https://llm.example.test/v1/chat/completions",
        LLM_MODEL="model-x",
        MINERU_TOKEN="mineru-token",
        MINERU_BASE="https://mineru.example.test",
        IMAGE_SEMANTIC_API_KEY="vision-key",
        IMAGE_SEMANTIC_API_URL="https://vision.example.test/chat",
        IMAGE_SEMANTIC_MODEL="vision-x",
        LLM_TIMEOUT=12,
        LLM_RETRIES=3,
    )

    monkeypatch.setattr(paper_audit.importlib, "import_module", lambda name: fake_config)

    cfg = paper_audit.load_runtime_config(verbose=False)

    assert cfg.text_llm.api_key == "llm-key"
    assert cfg.text_llm.model == "model-x"
    assert cfg.mineru.api_key == "mineru-token"
    assert cfg.mineru.base_url == "https://mineru.example.test"
    assert cfg.image_semantic.api_key == "vision-key"
    assert cfg.llm_timeout == 12
    assert cfg.llm_retries == 3


def test_runtime_config_module_loads_environment_without_legacy_globals():
    cfg = veritas.runtime_config.load_runtime_config(
        config_module_name="missing_config_module_for_test",
        env={
            "LLM_API_KEY": "env-llm-key",
            "LLM_API_URL": "https://llm.example.test/v1/chat/completions",
            "LLM_MODEL": "env-model",
            "MINERU_TOKEN": "env-mineru-token",
            "MINERU_BASE": "https://mineru.example.test",
            "GLM_API_KEY": "env-vision-key",
            "GLM_API_URL": "https://vision.example.test/chat",
            "GLM_VISION_MODEL": "env-vision-model",
            "LLM_TIMEOUT": "13",
            "LLM_RETRIES": "4",
        },
        verbose=False,
    )

    assert cfg.text_llm.api_key == "env-llm-key"
    assert cfg.mineru.api_key == "env-mineru-token"
    assert cfg.image_semantic.api_key == "env-vision-key"
    assert cfg.image_semantic.model == "env-vision-model"
    assert cfg.llm_timeout == 13
    assert cfg.llm_retries == 4


def test_report_action_service_mode_loads_runtime_config(monkeypatch):
    fake_config = types.SimpleNamespace(
        LLM_API_KEY="llm-key",
        LLM_API_URL="https://llm.example.test/v1/chat/completions",
        LLM_MODEL="model-x",
        MINERU_TOKEN="mineru-token",
        MINERU_BASE="https://mineru.example.test",
        IMAGE_SEMANTIC_API_KEY="vision-key",
        IMAGE_SEMANTIC_API_URL="https://vision.example.test/chat",
        IMAGE_SEMANTIC_MODEL="vision-x",
        LLM_TIMEOUT=12,
        LLM_RETRIES=3,
    )
    captured = {}

    for name in ("LLM_API_KEY", "LLM_API_URL", "LLM_MODEL", "LLM_TIMEOUT", "LLM_RETRIES"):
        monkeypatch.setattr(paper_audit, name, getattr(paper_audit, name))
    monkeypatch.setattr(paper_audit.importlib, "import_module", lambda name: fake_config)
    monkeypatch.setattr(sys, "argv", ["paper_audit.py", "--serve-report-actions", "--report-actions-port", "9010"])

    def fake_serve_report_actions(port=8765):
        captured["port"] = port
        captured["llm_api_key"] = paper_audit.LLM_API_KEY
        captured["llm_api_url"] = paper_audit.LLM_API_URL
        captured["llm_model"] = paper_audit.LLM_MODEL
        captured["llm_timeout"] = paper_audit.LLM_TIMEOUT
        return 0

    monkeypatch.setattr(paper_audit, "serve_report_actions", fake_serve_report_actions)

    assert paper_audit.main() == 0
    assert captured == {
        "port": 9010,
        "llm_api_key": "llm-key",
        "llm_api_url": "https://llm.example.test/v1/chat/completions",
        "llm_model": "model-x",
        "llm_timeout": 12,
    }


def test_web_runner_service_mode_loads_runtime_config(monkeypatch):
    fake_config = types.SimpleNamespace(
        LLM_API_KEY="llm-key",
        LLM_API_URL="https://llm.example.test/v1/chat/completions",
        LLM_MODEL="model-x",
        MINERU_TOKEN="mineru-token",
        MINERU_BASE="https://mineru.example.test",
        IMAGE_SEMANTIC_API_KEY="vision-key",
        IMAGE_SEMANTIC_API_URL="https://vision.example.test/chat",
        IMAGE_SEMANTIC_MODEL="vision-x",
        LLM_TIMEOUT=12,
        LLM_RETRIES=3,
    )
    captured = {}

    monkeypatch.setattr(paper_audit.importlib, "import_module", lambda name: fake_config)
    monkeypatch.setattr(sys, "argv", ["paper_audit.py", "--serve-web", "--web-port", "9011", "--no-open"])

    def fake_serve_web_runner(port=8765, open_browser=True):
        captured["port"] = port
        captured["open_browser"] = open_browser
        captured["llm_api_key"] = paper_audit.LLM_API_KEY
        captured["llm_model"] = paper_audit.LLM_MODEL
        return 0

    monkeypatch.setattr(paper_audit, "serve_web_runner", fake_serve_web_runner)

    assert paper_audit.main() == 0
    assert captured == {
        "port": 9011,
        "open_browser": False,
        "llm_api_key": "llm-key",
        "llm_model": "model-x",
    }


def test_desktop_gui_mode_loads_runtime_config(monkeypatch):
    fake_config = types.SimpleNamespace(
        LLM_API_KEY="llm-key",
        LLM_API_URL="https://llm.example.test/v1/chat/completions",
        LLM_MODEL="model-x",
        MINERU_TOKEN="mineru-token",
        MINERU_BASE="https://mineru.example.test",
        IMAGE_SEMANTIC_API_KEY="vision-key",
        IMAGE_SEMANTIC_API_URL="https://vision.example.test/chat",
        IMAGE_SEMANTIC_MODEL="vision-x",
        LLM_TIMEOUT=12,
        LLM_RETRIES=3,
    )
    captured = {}

    monkeypatch.setattr(paper_audit.importlib, "import_module", lambda name: fake_config)
    monkeypatch.setattr(sys, "argv", ["paper_audit.py", "--gui"])

    def fake_run_desktop_gui():
        captured["llm_api_key"] = paper_audit.LLM_API_KEY
        captured["llm_model"] = paper_audit.LLM_MODEL
        return 0

    monkeypatch.setattr(paper_audit, "run_desktop_gui", fake_run_desktop_gui)

    assert paper_audit.main() == 0
    assert captured == {
        "llm_api_key": "llm-key",
        "llm_model": "model-x",
    }


def test_desktop_gui_console_script_is_declared():
    pyproject = (paper_audit.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (paper_audit.Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")

    assert 'veritas-gui = "veritas.legacy:gui_main"' in pyproject
    assert 'packages = ["veritas"]' in pyproject
    assert '"tkinterdnd2>=0.5.0"' in pyproject
    assert "tkinterdnd2>=0.5.0" in requirements


def test_chat_completions_endpoint_accepts_base_or_full_url():
    assert paper_audit._chat_completions_endpoint("https://llm.example.test/v1") == "https://llm.example.test/v1/chat/completions"
    assert paper_audit._chat_completions_endpoint("https://llm.example.test/v1/") == "https://llm.example.test/v1/chat/completions"
    assert paper_audit._chat_completions_endpoint("https://llm.example.test/v1/chat/completions") == "https://llm.example.test/v1/chat/completions"


def test_run_preflight_once_reuses_result_within_run_only():
    calls = {"count": 0}

    def runner():
        calls["count"] += 1
        return paper_audit.PreflightResult("text_llm", True)

    run_state = {}

    first = paper_audit.run_preflight_once(run_state, "text_llm", runner)
    second = paper_audit.run_preflight_once(run_state, "text_llm", runner)
    third = paper_audit.run_preflight_once({}, "text_llm", runner)

    assert first is second
    assert third is not first
    assert calls["count"] == 2


def test_preflight_mineru_reports_auth_failure(monkeypatch):
    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    monkeypatch.setattr(paper_audit, "MINERU_TOKEN", "bad-token")
    monkeypatch.setattr(paper_audit, "MINERU_BASE", "https://mineru.example.test")
    monkeypatch.setattr(paper_audit.requests, "get", lambda *args, **kwargs: FakeResponse())

    result = paper_audit.preflight_mineru(timeout=1)

    assert not result.ok
    assert result.capability == "mineru"
    assert result.error_class == "provider_auth_failed"
    assert result.details["http_status"] == 401


def test_preflight_text_llm_performs_lightweight_call(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(paper_audit, "LLM_API_KEY", "llm-key")
    monkeypatch.setattr(paper_audit, "LLM_API_URL", "https://llm.example.test/v1/chat/completions")
    monkeypatch.setattr(paper_audit, "LLM_MODEL", "model-x")
    monkeypatch.setattr(paper_audit.requests, "post", fake_post)

    result = paper_audit.preflight_text_llm(timeout=2)

    assert result.ok
    assert result.capability == "text_llm"
    assert calls[0]["json"]["max_tokens"] == 1
    assert calls[0]["json"]["model"] == "model-x"
    assert calls[0]["headers"]["Authorization"] == "Bearer llm-key"


def test_preflight_failure_to_audit_failure_has_retry_guidance():
    result = paper_audit.PreflightResult(
        capability="text_llm",
        ok=False,
        error_class="provider_unavailable",
        message="timeout",
        details={"http_status": 503},
        created_at="2026-05-28 12:00:00",
    )

    failure = paper_audit.preflight_failure_to_audit_failure(
        result,
        "python paper_audit.py paper.pdf --json",
        ["init", "stage1_text_extraction"],
    )

    assert failure.capability == "text_llm"
    assert failure.error_class == "provider_unavailable"
    assert failure.retry_command == "python paper_audit.py paper.pdf --json"
    assert failure.completed_stages == ["init", "stage1_text_extraction"]
    assert "LLM_API_KEY" in " ".join(failure.fix_hints)


def test_adapter_result_structured_success_failure_skip():
    success = paper_audit.AdapterResult.success({"ok": True})
    failure = paper_audit.AdapterResult.failure("provider_auth_failed", "bad key")
    skipped = paper_audit.AdapterResult.skipped("unsupported_content", "not supported")

    assert success.ok
    assert success.to_dict()["status"] == "success"
    assert not failure.ok
    assert failure.error_class == "provider_auth_failed"
    assert skipped.status == "skipped"
    assert skipped.error_class == "unsupported_content"


def test_fake_adapters_simulate_required_failure_modes():
    scenarios = {
        "auth_failure": "provider_auth_failed",
        "network_failure": "provider_unavailable",
        "rate_limit": "provider_rate_limited",
        "schema_error": "schema_error",
    }

    for scenario, error_class in scenarios.items():
        adapters = paper_audit.fake_audit_adapters(scenario=scenario)
        assert adapters.mineru.preflight().error_class == error_class
        assert adapters.text_llm.review("text").error_class == error_class
        assert adapters.reference_lookup.audit("refs").error_class == error_class
        assert adapters.image_semantic.analyze("image.png").error_class == error_class
        assert adapters.image_detector.detect("image.png").error_class == error_class

    skipped = paper_audit.fake_audit_adapters(scenario="unsupported_content")
    assert skipped.mineru.extract(Path("paper.pdf")).status == "skipped"
    assert skipped.image_detector.detect("tiny.png").error_class == "unsupported_content"


def test_production_adapters_wrap_injected_functions_without_monkeypatching_globals():
    mineru = paper_audit.ProductionMinerUAdapter(
        preflight_func=lambda: paper_audit.PreflightResult("mineru", True),
        extract_func=lambda file_path, language="ch", output_dir=None: ("text", {"source": "fake"}),
    )
    text_llm = paper_audit.ProductionTextLLMAdapter(
        preflight_func=lambda: paper_audit.PreflightResult("text_llm", False, "provider_auth_failed", "bad key"),
        review_func=lambda text, chunk_info=None: "raw llm",
    )
    references = paper_audit.ProductionReferenceLookupAdapter(
        audit_func=lambda references_text, online=False, online_limit=50, timeout=10, cache=None: {"reference_count": 1}
    )
    image_semantic = paper_audit.ProductionImageSemanticAdapter(
        analyze_func=lambda image_path, timeout=45: {"status": "ok", "summary": "ok"}
    )
    image_detector = paper_audit.ProductionImageDetectorAdapter(
        detect_func=lambda image_path, timeout=60: {"status": "skipped", "reason": "too_small", "summary": "tiny"}
    )

    assert mineru.preflight().ok
    assert mineru.extract(Path("paper.pdf")).value["text"] == "text"
    assert text_llm.preflight().error_class == "provider_auth_failed"
    assert text_llm.review("body").value == "raw llm"
    assert references.audit("refs").value["reference_count"] == 1
    assert image_semantic.analyze("image.png").ok
    assert image_detector.detect("tiny.png").status == "skipped"


def _complete_fake_adapters(**overrides):
    values = {
        "text_llm": json.dumps({
            "summary": "fake complete",
            "risk_level": "低",
            "detection_score": 0,
            "checks": [],
            "conclusion": "fake complete",
        }, ensure_ascii=False)
    }
    adapters = paper_audit.fake_audit_adapters(values=values)
    for name, adapter in overrides.items():
        setattr(adapters, name, adapter)
    return adapters


def test_fake_adapter_e2e_complete_writes_complete_artifacts(tmp_path):
    result = paper_audit.run_adapter_e2e_audit(
        tmp_path,
        _complete_fake_adapters(),
        text="Fake manuscript text with n=20 and p=0.04.",
    )

    assert result["outcome"] == "complete"
    assert result["md_path"] == tmp_path / "audit_report.audit.md"
    assert result["json_path"] == tmp_path / "audit_report.audit.json"
    assert "**产物类型**: 完整审查 (complete)" in result["md_path"].read_text(encoding="utf-8")
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["report_type"] == "complete"
    assert payload["meta"]["artifact_type"] == "complete"


def test_fake_adapter_e2e_llm_failure_writes_failed_diagnostics(tmp_path):
    result = paper_audit.run_adapter_e2e_audit(
        tmp_path,
        _complete_fake_adapters(text_llm=paper_audit.FakeTextLLMAdapter("network_failure")),
    )

    assert result["outcome"] == "failed"
    assert result["capability"] == "text_llm"
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["report_type"] == "failed"
    assert payload["complete_report_generated"] is False
    assert payload["failure"]["error_class"] == "provider_unavailable"


def test_fake_adapter_e2e_llm_schema_gap_recovers_to_complete(tmp_path):
    result = paper_audit.run_adapter_e2e_audit(
        tmp_path,
        _complete_fake_adapters(text_llm=paper_audit.FakeTextLLMAdapter("success", value=json.dumps({
            "summary": "bad schema",
            "risk_level": "中",
            "checks": [{"verdict": "⚠️疑点", "evidence": "missing required fields"}],
            "conclusion": "bad",
        }, ensure_ascii=False))),
    )

    assert result["outcome"] == "complete"
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["llm_report"]["_schema_recovered"] is True
    assert payload["llm_report"]["checks"][0]["confidence"] == 0.2


def test_fake_adapter_e2e_reference_lookup_failure_when_references_exist(tmp_path):
    result = paper_audit.run_adapter_e2e_audit(
        tmp_path,
        _complete_fake_adapters(reference_lookup=paper_audit.FakeReferenceLookupAdapter("network_failure")),
        references_text="References\n1. Smith J. Test Journal. 2024. doi:10.1000/xyz",
    )

    assert result["outcome"] == "failed"
    assert result["capability"] == "reference_lookup"
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["failure"]["capability"] == "reference_lookup"
    assert payload["failure"]["error_class"] == "provider_unavailable"


def test_fake_adapter_e2e_image_detector_failure_when_images_exist(tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 2048)

    result = paper_audit.run_adapter_e2e_audit(
        tmp_path,
        _complete_fake_adapters(image_detector=paper_audit.FakeImageDetectorAdapter("network_failure")),
        image_paths=[str(image_path)],
    )

    assert result["outcome"] == "failed"
    assert result["capability"] == "image_detector"
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["failure"]["capability"] == "image_detector"
    assert payload["failure"]["error_class"] == "provider_unavailable"


def test_run_request_maps_argparse_values():
    args = types.SimpleNamespace(
        pdf_path="paper.pdf",
        output="out.md",
        json=True,
        no_open=True,
        mineru=True,
        no_mineru=False,
        mineru_model="vlm",
        mineru_lang="en",
        max_chars=2048,
        no_reference_online=True,
        reference_online_limit=12,
        reference_timeout=3,
        no_resource_online=True,
        resource_timeout=9,
        image_audit_limit=8,
        no_image_semantic=True,
        image_semantic_limit=4,
        image_semantic_timeout=5,
        no_image_detector=True,
        image_detector_limit=6,
        image_detector_timeout=7,
        no_resume=True,
        fresh=True,
        llm_timeout=11,
        llm_retries=2,
        strict_failed_chunks=True,
        llm_cache_only=True,
        ai_detect=False,
        image_detect=False,
        report_actions_port=8766,
    )

    request = paper_audit.RunRequest.from_args(args)
    legacy_args = request.to_args()

    assert request.input_path == Path("paper.pdf")
    assert request.output == "out.md"
    assert request.json_output is True
    assert request.no_open is True
    assert request.mineru_lang == "en"
    assert request.max_chars == 2048
    assert request.no_reference_online is True
    assert request.no_resource_online is True
    assert request.resource_timeout == 9
    assert request.image_audit_limit == 8
    assert request.fresh is True
    assert request.llm_timeout == 11
    assert request.strict_failed_chunks is True
    assert request.report_actions_port == 8766
    assert legacy_args.pdf_path == "paper.pdf"
    assert legacy_args.json is True
    assert legacy_args.image_audit_limit == 8
    assert legacy_args.report_actions_port == 8766


def _minimal_run_args(input_path, output_path):
    return types.SimpleNamespace(
        pdf_path=str(input_path),
        output=str(output_path),
        json=True,
        no_open=True,
        mineru=False,
        no_mineru=False,
        mineru_model="vlm",
        mineru_lang="ch",
        max_chars=4096,
        no_reference_online=True,
        reference_online_limit=None,
        reference_timeout=1,
        no_resource_online=True,
        resource_timeout=1,
        image_audit_limit=None,
        no_image_semantic=True,
        image_semantic_limit=None,
        image_semantic_timeout=1,
        no_image_detector=True,
        image_detector_limit=None,
        image_detector_timeout=1,
        no_resume=True,
        fresh=False,
        llm_timeout=1,
        llm_retries=0,
        strict_failed_chunks=True,
        llm_cache_only=False,
        ai_detect=False,
        image_detect=False,
        report_actions_port=8765,
    )


def test_run_audit_accepts_direct_docx_file_input(monkeypatch, tmp_path):
    docx_path = tmp_path / "paper.docx"
    docx_path.write_bytes(b"fake-docx")
    output_base = tmp_path / "word_report"
    args = _minimal_run_args(docx_path, output_base)
    calls = {}

    def fake_extract_text_from_file(file_path, **kwargs):
        calls["file_path"] = Path(file_path)
        calls["kwargs"] = kwargs
        return "\n\n=== 文件: paper.docx ===\nA Word manuscript with p = 0.04 and Methods section."

    def fail_pdf_extract(*args, **kwargs):
        raise AssertionError("direct .docx input must not use PDF extraction")

    monkeypatch.setattr(paper_audit, "DOCX_SUPPORTED", True)
    monkeypatch.setattr(paper_audit, "extract_text_from_file", fake_extract_text_from_file)
    monkeypatch.setattr(paper_audit, "extract_pdf_text", fail_pdf_extract)
    monkeypatch.setattr(paper_audit, "preflight_text_llm", lambda timeout=10: paper_audit.PreflightResult("text_llm", True, "", "ok"))
    monkeypatch.setattr(paper_audit, "call_llm", lambda *a, **k: json.dumps({
        "summary": "ok",
        "risk_level": "低",
        "detection_score": 3,
        "checks": [],
        "conclusion": "done",
    }, ensure_ascii=False))
    monkeypatch.setattr(paper_audit, "build_image_audit", lambda *a, **k: {
        "image_count": 0,
        "checked_count": 0,
        "semantic_checked": 0,
        "detector_checked": 0,
        "images": [],
    })

    result = paper_audit.run_audit(paper_audit.RunRequest.from_args(args))

    assert result.outcome == "complete"
    assert calls["file_path"] == docx_path
    assert calls["kwargs"]["use_mineru"] is False
    payload = json.loads((tmp_path / "word_report.audit.json").read_text(encoding="utf-8"))
    assert payload["meta"]["input_type"] == "file"
    assert payload["meta"]["extractor"] == "single_file_multi_format"
    assert payload["meta"]["extraction_method"] == "docx_text"


def test_run_audit_rejects_directory_audit_docx_when_dependency_missing(monkeypatch, tmp_path):
    input_dir = tmp_path / "paper_dir"
    input_dir.mkdir()
    docx_path = input_dir / "manuscript.docx"
    docx_path.write_bytes(b"fake-docx")
    output_base = tmp_path / "dir_report"
    args = _minimal_run_args(input_dir, output_base)

    def fail_extract(*args, **kwargs):
        raise AssertionError("missing dependency should fail before extraction")

    monkeypatch.setattr(paper_audit, "DOCX_SUPPORTED", False)
    monkeypatch.setattr(paper_audit, "extract_text_from_file", fail_extract)

    result = paper_audit.run_audit(paper_audit.RunRequest.from_args(args), args)

    assert result.outcome == "failed"
    failed_json = tmp_path / "dir_report.failed.json"
    failed_md = tmp_path / "dir_report.failed.md"
    assert failed_json.exists()
    assert failed_md.exists()
    payload = json.loads(failed_json.read_text(encoding="utf-8"))
    assert payload["failure"]["capability"] == "input_extraction"
    assert payload["failure"]["error_class"] == "missing_optional_dependency"
    assert payload["failure"]["details"]["dependency"] == "python-docx"
    assert "python3 -m pip install python-docx" in failed_md.read_text(encoding="utf-8")


def test_run_audit_rejects_direct_legacy_doc_file_input(monkeypatch, tmp_path):
    doc_path = tmp_path / "paper.doc"
    doc_path.write_bytes(b"legacy-doc")
    args = _minimal_run_args(doc_path, tmp_path / "legacy_doc_report")

    def fail_pdf_extract(*args, **kwargs):
        raise AssertionError("legacy .doc input must fail before PDF extraction")

    monkeypatch.setattr(paper_audit, "extract_pdf_text", fail_pdf_extract)

    result = paper_audit.run_audit(paper_audit.RunRequest.from_args(args), args)

    assert result.outcome == "failed"
    assert result.failure["capability"] == "input_extraction"
    assert result.failure["error_class"] == "unsupported_legacy_doc"
    assert ".docx" in result.failure["message"]


def test_run_result_represents_complete_limited_and_failed(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="text_llm",
        error_class="provider_unavailable",
        message="down",
        retry_command="python paper_audit.py paper.pdf --json",
    )

    complete = paper_audit.RunResult.complete({"markdown": "paper.audit.md"})
    limited = paper_audit.RunResult.limited({"markdown": "paper.limited.md"})
    failed = paper_audit.RunResult.failed(
        failure,
        {"markdown": "paper.failed.md", "json": "paper.failed.json"},
        meta={"input_path": str(tmp_path / "paper.pdf")},
    )

    assert complete.outcome == "complete"
    assert complete.exit_code == 0
    assert limited.outcome == "limited"
    assert limited.artifact_type == "limited"
    assert failed.outcome == "failed"
    assert failed.exit_code == 1
    assert failed.failure["capability"] == "text_llm"


def test_package_boundaries_export_existing_compatibility_surface():
    assert veritas.runtime_config.RuntimeConfig is paper_audit.RuntimeConfig
    assert veritas.config.RuntimeConfig is paper_audit.RuntimeConfig
    assert veritas.config.CapabilityConfig is paper_audit.CapabilityConfig
    assert veritas.preflight_types.PreflightResult is paper_audit.PreflightResult
    assert veritas.preflight.PreflightResult is paper_audit.PreflightResult
    assert veritas.preflight.run_preflight_once is paper_audit.run_preflight_once
    assert veritas.run_types.RunRequest is paper_audit.RunRequest
    assert veritas.run_types.RunResult is paper_audit.RunResult
    assert veritas.run.RunRequest is paper_audit.RunRequest
    assert veritas.run.RunResult is paper_audit.RunResult
    assert veritas.models.AuditFailure is paper_audit.AuditFailure
    assert veritas.models.EvidenceFinding is paper_audit.EvidenceFinding
    assert veritas.models.AuditReportModel is paper_audit.AuditReportModel
    assert veritas.models.CoverageModel is paper_audit.CoverageModel
    assert veritas.file_utils._safe_name is paper_audit._safe_name
    assert veritas.file_utils._json_save is paper_audit._json_save
    assert veritas.file_utils._json_load is paper_audit._json_load
    assert veritas.file_utils._load_merged_json_dicts is paper_audit._load_merged_json_dicts
    assert veritas.workspace.create_run_workspace is paper_audit.create_run_workspace
    assert veritas.workspace.run_workspace_path is paper_audit.run_workspace_path
    assert veritas.workspace.record_run_workspace_json is paper_audit.record_run_workspace_json
    assert veritas.workspace.record_run_workspace_artifacts is paper_audit.record_run_workspace_artifacts
    assert veritas.report_schema.parse_report is paper_audit.parse_report
    assert veritas.report_schema.normalize_llm_report_schema is paper_audit.normalize_llm_report_schema
    assert veritas.retry_commands.retry_command_from_args is paper_audit.retry_command_from_args
    assert veritas.retry_commands.default_retry_command is paper_audit.default_retry_command
    assert veritas.runtime_metadata.runtime_utc_year is paper_audit.runtime_utc_year
    assert veritas.runtime_metadata.runtime_metadata is paper_audit.runtime_metadata
    assert veritas.runtime_metadata.ensure_runtime_meta is paper_audit.ensure_runtime_meta
    assert veritas.artifacts.audit_artifact_paths is paper_audit.audit_artifact_paths
    assert veritas.artifacts.failed_audit_artifact_paths is paper_audit.failed_audit_artifact_paths
    assert veritas.artifacts.audit_limited_reasons is paper_audit.audit_limited_reasons
    assert veritas.artifacts.coverage_blocking_failure is paper_audit.coverage_blocking_failure
    assert veritas.artifacts.apply_audit_artifact_type is paper_audit.apply_audit_artifact_type
    assert veritas.risk_rules.apply_risk_rules is paper_audit.apply_risk_rules
    assert veritas.adapter_types.AdapterResult is paper_audit.AdapterResult
    assert veritas.adapters.AdapterResult is paper_audit.AdapterResult
    assert veritas.adapter_types.AuditAdapters is paper_audit.AuditAdapters
    assert veritas.adapters.AuditAdapters is paper_audit.AuditAdapters
    assert veritas.adapter_types.TextLLMAdapter is paper_audit.TextLLMAdapter
    assert veritas.adapters.TextLLMAdapter is paper_audit.TextLLMAdapter
    assert veritas.fake_adapters.FakeTextLLMAdapter is paper_audit.FakeTextLLMAdapter
    assert veritas.adapters.FakeTextLLMAdapter is paper_audit.FakeTextLLMAdapter
    assert veritas.fake_adapters.fake_audit_adapters is paper_audit.fake_audit_adapters
    assert veritas.adapters.fake_audit_adapters is paper_audit.fake_audit_adapters
    assert veritas.production_adapters.ProductionTextLLMAdapter is paper_audit.ProductionTextLLMAdapter
    assert veritas.adapters.ProductionTextLLMAdapter is paper_audit.ProductionTextLLMAdapter
    assert veritas.production_adapters.default_audit_adapters is paper_audit.default_audit_adapters
    assert veritas.adapters.default_audit_adapters is paper_audit.default_audit_adapters
    assert veritas.web_runner_paths.resolve_web_runner_input_path is paper_audit.resolve_web_runner_input_path
    assert veritas.web_runner_paths._web_runner_common_search_roots is paper_audit._web_runner_common_search_roots


def test_paper_audit_import_still_allows_legacy_monkeypatches(monkeypatch):
    calls = {"count": 0}

    def fake_verify(ref, timeout=10):
        calls["count"] += 1
        return {"online_status": "verified", "confidence": 1.0, "matched_sources": [], "problems": [], "query": {}}

    monkeypatch.setattr(paper_audit, "verify_reference_online", fake_verify)

    audit = paper_audit.audit_references(
        "References\n1. Smith J. Reliable paper. Nature. 2020. doi:10.1000/abc",
        online=True,
        online_limit=None,
    )

    assert audit["online_checked"] == 1
    assert calls["count"] == 1


def test_renderer_boundary_accepts_stable_report_model(tmp_path):
    finding = EvidenceFinding(
        category="数据与结果",
        item="样本量",
        verdict="✅通过",
        source_text="Methods: n=20",
        evidence="Methods reports n=20.",
        reason="样本量前后一致。",
        recommendation="无需额外处理。",
        confidence=0.91,
    )
    report = AuditReportModel(
        summary="ok",
        risk_level="低",
        detection_score=0,
        checks=[finding],
        conclusion="done",
    )
    meta = {"artifact_type": "complete", "risk_rule_version": paper_audit.RISK_RULE_VERSION}
    stat = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }

    markdown = render_markdown_report(report, tmp_path / "paper.pdf", meta, stat)
    html = render_html_report(report, tmp_path / "paper.pdf", meta, stat)

    assert "**产物类型**: 完整审查 (complete)" in markdown
    assert "prompt=text_audit_prompt_v1" in markdown
    assert "schema=strict_evidence_schema_v1" in markdown
    assert "adapter=audit_adapters_v1" in markdown
    assert "证据风险分" in markdown
    assert "样本量" in markdown
    assert "Prompt版本" in html
    assert "Schema版本" in html
    assert "Adapter版本" in html
    assert "证据风险分" in html


def test_model_boundary_normalizes_report_dicts():
    report = audit_report_from_dict({
        "summary": "needs review",
        "risk_level": "中",
        "detection_score": "42",
        "checks": [{
            "category": "图像",
            "item": "Figure 1",
            "verdict": "⚠️疑点",
            "source": "Figure 1 legend",
            "evidence": "Possible duplicated panel.",
            "confidence": "0.73",
        }],
    })
    payload = model_to_dict(report)

    assert isinstance(report, AuditReportModel)
    assert report.detection_score == 42
    assert report.checks[0].source_text == "Figure 1 legend"
    assert report.checks[0].confidence == 0.73
    assert report.checks[0].reason == ""
    assert payload["checks"][0]["item"] == "Figure 1"


def test_evaluation_replay_suite_runs_synthetic_fixture_without_network():
    results = veritas.evaluation.run_replay_suite()
    payload = veritas.evaluation.eval_results_payload(results)

    assert payload["passed"] is True
    assert payload["total"] >= 2
    assert any(result.case_id == "high-risk-red-flags" and result.risk_level == "高" for result in results)
    assert payload["prompt_version"] == veritas.evaluation.EVAL_PROMPT_VERSION
    assert payload["schema_version"] == veritas.evaluation.EVAL_SCHEMA_VERSION
    assert payload["risk_rule_version"] == paper_audit.RISK_RULE_VERSION


def test_evaluation_record_mode_stores_required_versions(tmp_path):
    case = veritas.evaluation.EvalCase(
        case_id="recordable",
        input_text="Synthetic public paper text",
        expected_risk_level="低",
    )
    response = {
        "summary": "ok",
        "risk_level": "低",
        "detection_score": 0,
        "checks": [],
        "conclusion": "ok",
    }

    record = veritas.evaluation.build_eval_record(
        case,
        response=response,
        adapter="fake_text_llm",
        model="fixture-model",
        recorded_at="2026-05-28 12:00:00",
    )
    record_path = veritas.evaluation.write_eval_record(record, tmp_path)
    loaded = json.loads(record_path.read_text(encoding="utf-8"))

    assert loaded["adapter"] == "fake_text_llm"
    assert loaded["model"] == "fixture-model"
    assert loaded["prompt_version"] == veritas.evaluation.EVAL_PROMPT_VERSION
    assert loaded["schema_version"] == veritas.evaluation.EVAL_SCHEMA_VERSION
    assert loaded["risk_rule_version"] == paper_audit.RISK_RULE_VERSION
    assert loaded["input_hash"] == veritas.evaluation.evaluation_input_hash(case.input_text)
    assert loaded["response"]["summary"] == "ok"


def test_extract_all_numbers_filters_years_and_small_noise():
    text = "In 2024, group A had 12.5 units, group B had 99, and page 3 showed 0.25."

    assert paper_audit.extract_all_numbers(text) == [12.5, 99.0, 0.25]


def test_local_stat_check_flags_abnormal_p_values_and_sample_conflict():
    result = paper_audit.local_stat_check("n=12, N=14, p=0.06, p < 0.001, SD=2.4")

    assert result["p_value_count"] == 2
    assert result["p_value_abnormal"] == 1
    assert "不同样本量" in result["number_consistency"]
    assert result["sd_count"] == 1


def test_cross_file_consistency_detects_sample_size_mismatch():
    audit = paper_audit.build_cross_file_consistency_audit([
        {
            "file": "main.pdf",
            "path": "main.pdf",
            "category": "main_text",
            "text": "Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.",
        },
        {
            "file": "supplement.docx",
            "path": "supplement.docx",
            "category": "supplement",
            "text": "Supplement table: experiment alpha treatment cohort n=24 mice after exclusions.",
        },
    ])

    assert audit["status"] == "ok"
    assert audit["strong_count"] == 1
    finding = audit["findings"][0]
    assert finding["conflict_type"] == "sample_size_mismatch"
    assert finding["severity"] == "strong"
    assert "main.pdf" in finding["claim_file"]
    assert "supplement.docx" in finding["counter_file"]
    assert finding["manual_check"]


def test_cross_file_consistency_matching_sample_sizes_no_false_positive():
    audit = paper_audit.build_cross_file_consistency_audit([
        {
            "file": "main.pdf",
            "path": "main.pdf",
            "category": "main_text",
            "text": "Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.",
        },
        {
            "file": "supplement.docx",
            "path": "supplement.docx",
            "category": "supplement",
            "text": "Supplement table: experiment alpha treatment cohort n=42 mice after exclusions.",
        },
    ])

    assert audit["finding_count"] == 0


def test_cross_file_consistency_noisy_table_mismatch_is_weak():
    audit = paper_audit.build_cross_file_consistency_audit([
        {
            "file": "main.pdf",
            "path": "main.pdf",
            "category": "main_text",
            "text": "Experiment alpha treatment cohort n=42 mice.",
        },
        {
            "file": "supplement.csv",
            "path": "supplement.csv",
            "category": "data_file",
            "text": "experiment alpha treatment cohort | n=24 | a | b | c | d | e | f | g | h | i | j | k | l",
        },
    ])

    assert audit["finding_count"] == 1
    assert audit["findings"][0]["severity"] == "weak"


def test_cross_file_consistency_detects_group_label_mismatch():
    audit = paper_audit.build_cross_file_consistency_audit([
        {
            "file": "main.pdf",
            "path": "main.pdf",
            "category": "main_text",
            "text": "Methods define the Control group for experiment beta.",
        },
        {
            "file": "supplement.xlsx",
            "path": "supplement.xlsx",
            "category": "data_file",
            "text": "Sheet beta lists Vehicle group measurements for the same assay.",
        },
    ])

    assert any(
        finding["conflict_type"] == "group_label_mismatch" and finding["severity"] == "medium"
        for finding in audit["findings"]
    )


def test_cross_file_consistency_renders_reports_and_followup_context():
    audit = paper_audit.build_cross_file_consistency_audit([
        {
            "file": "main.pdf",
            "path": "main.pdf",
            "category": "main_text",
            "text": "Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.",
        },
        {
            "file": "supplement.docx",
            "path": "supplement.docx",
            "category": "supplement",
            "text": "Supplement table: experiment alpha treatment cohort n=24 mice after exclusions.",
        },
    ])
    report = {"summary": "ok", "risk_level": "中", "detection_score": 50, "checks": [], "conclusion": "done"}
    stat = {
        "benford_deviation": 0,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }
    meta = {"cross_file_consistency_audit": audit}

    markdown = paper_audit.format_report(report, "paper.pdf", meta, stat)
    html = paper_audit.format_html_report(report, "paper.pdf", meta, stat)
    context = paper_audit._report_action_context(report, "paper.pdf", meta, stat)

    assert "跨文件一致性审查" in markdown
    assert "sample_size_mismatch" in markdown
    assert "cross-file-card" in html
    assert context["cross_file_consistency"]["finding_count"] == 1
    assert context["top_issues"][0]["source"] == "cross_file_consistency"


def test_evidence_chain_audit_detects_methods_results_sample_mismatch():
    text = """
Abstract
The alpha treatment improves tumor volume.

Methods
Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.

Results
Experiment alpha treatment cohort tumor volume was plotted in Figure 2 with n=24 mice after exclusions.

Conclusion
Results require review.
"""

    audit = paper_audit.build_evidence_chain_audit(
        text,
        [{"file": "paper.pdf", "category": "main_text", "text": text}],
        {"checks": []},
        {},
        {},
    )

    assert audit["status"] == "ok"
    assert audit["finding_count"] == 1
    assert audit["claim_chain_findings"][0]["type"] == "methods_results_sample_size_mismatch"
    assert audit["claim_chain_findings"][0]["severity"] == "strong"
    assert audit["strong_count"] == 1


def test_evidence_chain_audit_flags_strong_abstract_claim_without_results_support():
    text = """
Abstract
This study demonstrates that biomarker omega significantly improves survival.

Methods
We enrolled patients for biomarker testing.

Results
The baseline demographic table lists age and sex only.

Conclusion
Further work is needed.
"""

    audit = paper_audit.build_evidence_chain_audit(
        text,
        [{"file": "paper.pdf", "category": "main_text", "text": text}],
        {"checks": []},
        {},
        {},
    )

    assert audit["finding_count"] == 1
    finding = audit["claim_chain_findings"][0]
    assert finding["type"] == "strong_claim_without_result_support"
    assert finding["severity"] == "medium"
    assert "Results" in finding["chain"]


def test_evidence_chain_clusters_cross_file_and_llm_same_figure():
    text = """
Methods
Experiment alpha treatment cohort n=42 mice.
Results
Figure 2 reports experiment alpha treatment cohort n=24 mice.
"""
    cross_file = paper_audit.build_cross_file_consistency_audit([
        {"file": "main.pdf", "path": "main.pdf", "category": "main_text", "text": "Figure 2 shows experiment alpha treatment cohort n=42 mice."},
        {"file": "supp.docx", "path": "supp.docx", "category": "supplement", "text": "Figure 2 supplement lists experiment alpha treatment cohort n=24 mice."},
    ])
    report = {
        "checks": [{
            "category": "图表",
            "item": "Figure 2",
            "verdict": "⚠️疑点",
            "source_text": "Figure 2 reports experiment alpha treatment cohort with conflicting sample sizes.",
            "detail": "Figure 2 样本量需人工核对。",
            "confidence": 0.8,
        }]
    }

    audit = paper_audit.build_evidence_chain_audit(
        text,
        [{"file": "main.pdf", "category": "main_text", "text": text}, {"file": "supp.docx", "category": "supplement", "text": "Figure 2 supplement n=24"}],
        report,
        {"cross_file_consistency_audit": cross_file},
        {},
    )

    cluster = next(item for item in audit["clusters"] if "figure:2" in item["keys"])
    assert cluster["severity"] == "strong"
    assert "cross_file_consistency" in cluster["source_types"]
    assert "llm_check" in cluster["source_types"]


def test_evidence_chain_audit_consistent_chain_has_no_finding():
    text = """
Abstract
This study reports tumor volume results.

Methods
Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.

Results
Experiment alpha treatment cohort tumor volume was plotted in Figure 2 with n=42 mice.

Conclusion
The findings should be independently validated.
"""

    audit = paper_audit.build_evidence_chain_audit(
        text,
        [{"file": "paper.pdf", "category": "main_text", "text": text}],
        {"checks": []},
        {},
        {},
    )

    assert audit["finding_count"] == 0
    assert audit["strong_count"] == 0


def test_evidence_chain_audit_renders_reports_and_followup_context():
    text = """
Methods
Experiment alpha measured tumor volume in the treatment cohort with n=42 mice.

Results
Figure 2 reports experiment alpha treatment cohort tumor volume with n=24 mice.
"""
    audit = paper_audit.build_evidence_chain_audit(
        text,
        [{"file": "paper.pdf", "category": "main_text", "text": text}],
        {"checks": []},
        {},
        {},
    )
    report = {"summary": "ok", "risk_level": "中", "detection_score": 50, "checks": [], "conclusion": "done"}
    stat = {
        "benford_deviation": 0,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }
    meta = {"evidence_chain_audit": audit}

    markdown = paper_audit.format_report(report, "paper.pdf", meta, stat)
    html = paper_audit.format_html_report(report, "paper.pdf", meta, stat)
    context = paper_audit._report_action_context(report, "paper.pdf", meta, stat)
    payload = {"meta": meta}

    assert "证据链与证据簇审查" in markdown
    assert "methods_results_sample_size_mismatch" in markdown
    assert "evidence-chain-section" in html
    assert payload["meta"]["evidence_chain_audit"]["cluster_count"] == 1
    assert context["evidence_chain_audit"]["cluster_count"] == 1
    assert context["top_issues"][0]["source"] == "evidence_chain_audit"
    assert context["top_issues"][0]["default_selected"] is True


def test_smart_chunk_text_never_exceeds_limit_for_long_paragraph():
    text = "A" * 350 + "\n\n" + "B" * 350 + "\n\n" + "C" * 350

    chunks = paper_audit.smart_chunk_text(text, chunk_size=200, overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk_text) <= 200 for chunk_text, _, _ in chunks)
    assert [idx for _, idx, _ in chunks] == list(range(len(chunks)))
    assert all(total == len(chunks) for _, _, total in chunks)


def test_smart_chunk_text_preserves_table_boundaries():
    rows = ["| col1 | col2 |", "| --- | --- |"] + [f"| row{i} | value{i} |" for i in range(40)]
    table = "\n".join([
        "[[TABLE_START page=1 id=1]]",
        "[[EXTRACTION_NOTE]] table noise [[/EXTRACTION_NOTE]]",
        *rows,
        "[[TABLE_END]]",
    ])

    chunks = paper_audit.smart_chunk_text(table, chunk_size=360, overlap=40)

    assert len(chunks) > 1
    for chunk_text, _, _ in chunks:
        assert len(chunk_text) <= 360
        assert "[[TABLE_START" in chunk_text
        assert "[[TABLE_END]]" in chunk_text
        assert "[[TABLE_CONTINUATION" in chunk_text


def test_mineru_structured_text_prefers_content_list_v2(tmp_path):
    zip_path = tmp_path / "mineru.zip"
    content = [
        {"type": "text", "page_idx": 0, "text": "Main paragraph."},
        {"type": "table", "page_idx": 1, "text": "| A | B |\n| --- | --- |\n| 1 | 2 |"},
    ]
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("paper_content_list_v2.json", json.dumps(content))
        zf.writestr("full.md", "fallback markdown")

    with zipfile.ZipFile(zip_path) as zf:
        text = paper_audit._extract_mineru_structured_text(zf)

    assert "[[TABLE_START page=1 id=1]]" in text
    assert "[[EXTRACTION_NOTE]]" in text
    assert "Main paragraph." in text
    assert "fallback markdown" not in text


def test_mineru_structured_text_handles_nested_v2_html_tables(tmp_path):
    zip_path = tmp_path / "mineru.zip"
    content = [[
        {
            "type": "title",
            "content": {"title_content": [{"type": "text", "content": "Code availability"}]},
            "page_idx": 0,
        },
        {
            "type": "table",
            "content": {
                "table_caption": [{"type": "text", "content": "Table 1 Model performance"}],
                "html": "<table><tr><td>Model</td><td>AUC</td></tr><tr><td>DNN</td><td>0.987</td></tr></table>",
            },
            "page_idx": 1,
        },
    ]]
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("paper_content_list_v2.json", json.dumps(content))

    with zipfile.ZipFile(zip_path) as zf:
        text = paper_audit._extract_mineru_structured_text(zf)

    assert "[[BLOCK type=title page=0]]" in text
    assert "Code availability" in text
    assert "[[TABLE_START page=1 id=1]]" in text
    assert "Table 1 Model performance" in text
    assert "| Model | AUC |" in text
    assert "<td>" not in text


def test_split_references_from_text_removes_reference_tail():
    text = "Abstract\nBody with n=20.\n\nReferences\n1. Smith J. Journal X. 2020. doi:10.1000/abc\n2. Missing source"

    main_text, refs = paper_audit.split_references_from_text(text)

    assert "Body with n=20" in main_text
    assert "Smith J" not in main_text
    assert "Smith J" in refs


def test_split_references_from_text_handles_mineru_singular_reference_heading():
    text = """Body text.

[[BLOCK type=text page=26]]
Reference
[[/BLOCK]]

[[BLOCK type=reference_list page=27]]
1. Smith J. Journal X. 2020. doi:10.1000/abc
[[/BLOCK]]
"""

    main_text, refs = paper_audit.split_references_from_text(text)

    assert "Body text" in main_text
    assert "Smith J" not in main_text
    assert "Smith J" in refs
    parsed = paper_audit.parse_references(refs)
    assert parsed[0]["doi"] == "10.1000/abc"


def test_audit_references_reports_basic_verifiability_issues():
    refs = """References
1. Smith J. Journal X. 2020. doi:10.1000/abc
2. No year or doi here
"""

    audit = paper_audit.audit_references(refs)

    assert audit["reference_count"] == 2
    assert audit["doi_count"] == 1
    assert audit["year_count"] == 1
    assert audit["issues"]
    assert audit["issues"][0]["index"] == 2


def test_parse_references_strips_mineru_markup():
    refs = """[[EXTRACTION_NOTE]] noise [[/EXTRACTION_NOTE]]
[[BLOCK type=text page=1]]
References
[[/BLOCK]]
1. Smith J. Journal X. 2020. doi:10.1000/abc
"""

    parsed = paper_audit.parse_references(refs)

    assert parsed[0]["text"].startswith("Smith J.")
    assert "EXTRACTION_NOTE" not in parsed[0]["text"]
    assert "[[BLOCK" not in parsed[0]["text"]


def test_parse_references_skips_html_table_noise():
    refs = """
<table><tr><td>Variables</td><td>Total</td></tr><tr><td>Age</td><td>42</td></tr></table>

[1] Smith J. Real paper title. Journal of Testing. 2020. doi:10.1000/xyz123
"""

    parsed = paper_audit.parse_references(refs)

    assert len(parsed) == 1
    assert parsed[0]["doi"] == "10.1000/xyz123"


def test_parse_references_merges_mineru_page_continuations_and_truncates_figure_legends():
    refs = """[[BLOCK type=title page=?]]
Reference
[[/BLOCK]]

[[BLOCK type=reference_list page=?]]
1. 1. Alpha A. First complete reference. Journal X 1, 1-2 (2020).
2. 2. Beta B. Second reference title. Journal Y 2, 3-4 (2021).
3. 3. Gamma C. A split title starts before page break
[[/BLOCK]]

[[BLOCK type=page_header page=?]]
ARTICLE IN PRESS
[[/BLOCK]]

[[BLOCK type=reference_list page=?]]
1. and continues after the break. Journal Z 3, 5-6 (2022).
2. 4. Delta D. Fourth reference title. Journal Q 4, 7-8 (2023).
[[/BLOCK]]

[[BLOCK type=title page=?]]
Figure legends
[[/BLOCK]]

[[BLOCK type=paragraph page=?]]
Figure 1 Workflow of the study.
[[/BLOCK]]
"""

    parsed = paper_audit.parse_references(refs)

    assert len(parsed) == 4
    assert "continues after the break" in parsed[2]["text"]
    assert "Figure 1" not in parsed[-1]["text"]


def test_reference_html_renders_table_noise_without_escaped_td():
    audit = {
        "status": "needs_review",
        "reference_count": 1,
        "doi_count": 0,
        "year_count": 0,
        "online_enabled": False,
        "online_checked": 0,
        "note": "",
        "issues": [{"index": 1, "issues": ["missing_doi"], "text": "<table><tr><td>A</td><td>B</td></tr></table>"}],
        "references": [{"text": "<table><tr><td>A</td><td>B</td></tr></table>", "online": {}}],
    }

    rendered = paper_audit.format_reference_audit_html(audit)

    assert "&lt;td" not in rendered
    assert '<table class="data-table">' in rendered


def test_reference_html_renders_empty_audit_section():
    rendered = paper_audit.format_reference_audit_html({
        "status": "ok",
        "reference_count": 0,
        "doi_count": 0,
        "year_count": 0,
        "online_enabled": False,
        "online_checked": 0,
        "note": "未识别到独立参考文献章节。",
        "issues": [],
        "references": [],
    })

    assert "参考文献真实性/可核验性校检" in rendered
    assert "未发现可解析参考文献" in rendered


def test_find_project_files_does_not_treat_reference_named_pdf_as_reference_file(tmp_path):
    supplement = tmp_path / "41746_2026_2649_MOESM1_ESM.pdf"
    article = tmp_path / "s41746-026-02649-8_reference.pdf"
    supplement.write_bytes(b"0" * 1_000_000)
    article.write_bytes(b"0" * 2_000_000)

    classes, all_files = paper_audit.find_project_files(tmp_path)

    assert set(all_files) == {supplement, article}
    assert classes["main_paper"] == article
    assert article not in classes["references"]
    assert supplement in classes["other"] or supplement in classes["supplements"]


def test_verify_reference_online_uses_doi_exact_match(monkeypatch):
    ref = {
        "text": "Smith J. Reliable cancer marker discovery. Nature Medicine. 2020. doi:10.1000/abc",
        "doi": "10.1000/abc",
        "year": "2020",
        "title_hint": "Reliable cancer marker discovery",
    }

    def fake_crossref(_ref, timeout=10):
        return [{
            "source": "Crossref",
            "title": "Reliable cancer marker discovery",
            "year": "2020",
            "doi": "10.1000/abc",
            "url": "https://doi.org/10.1000/abc",
        }]

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", fake_crossref)
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", lambda _ref, timeout=10: [])

    result = paper_audit.verify_reference_online(ref)

    assert result["online_status"] == "verified"
    assert result["confidence"] >= 0.9
    assert result["matched_sources"][0]["source"] == "Crossref"


def test_extract_reference_title_keeps_real_title_with_year(tmp_path):
    ref1 = "Sung,H. et al. Global Cancer Statistics 2020: GLOBOCAN Estimates of Incidence and Mortality Worldwide for 36 Cancers in 185 Countries. CA Cancer JClin 71, 209-249 (2021)."
    ref2 = "Haugen, B. R. et al. 2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer: The American Thyroid Association Guidelines Task Force on Thyroid Nodules and Differentiated Thyroid Cancer. Thyroid 26, (2016)."
    ref3 = "Liu, Z. et al. Machine learning-based integration develops an immune-derived lncRNA signature for improving outcomes in colorectal cancer. Nat Commun 13,(2022)."
    ref4 = "Chen, D. W., Lang, B. H. H., McLeod, D. S.A., Newbold, K.& Haymart, M. R. Thyroid cancer. The Lancet 401,1531-1544 (2023)."
    ref5 = "Davies, L.& Welch, H. G. Increasing Incidence of Thyroid Cancer in the United States, 1973-2002. JAMA 295,2164 (2006)."

    assert paper_audit.extract_reference_title(ref1).startswith("Global Cancer Statistics 2020")
    assert paper_audit.extract_reference_title(ref2).startswith("2015 American Thyroid Association Management Guidelines")
    assert paper_audit.extract_reference_title(ref3).startswith("Machine learning-based integration")
    assert paper_audit.extract_reference_title(ref4) == "Thyroid cancer"
    assert paper_audit.extract_reference_title(ref5).startswith("Increasing Incidence of Thyroid Cancer")
    assert paper_audit.extract_reference_year_hint(ref1) == "2021"
    assert paper_audit.extract_reference_year_hint(ref2) == "2016"


def test_verify_reference_online_can_verify_without_doi(monkeypatch):
    ref = {
        "text": "Haugen, B. R. et al. 2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer: The American Thyroid Association Guidelines Task Force on Thyroid Nodules and Differentiated Thyroid Cancer. Thyroid 26, (2016).",
        "year": "2015",
        "title_hint": "2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer",
        "author_hint": "Haugen",
        "container_hint": "Thyroid",
    }

    def fake_crossref(_ref, timeout=10):
        return [{
            "source": "Crossref",
            "title": "2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer",
            "year": "2015",
            "doi": "10.1089/thy.2015.0020",
            "authors": ["Haugen", "Brent", "Sherman"],
            "container": "Thyroid",
            "url": "https://doi.org/10.1089/thy.2015.0020",
        }]

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", fake_crossref)
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", lambda _ref, timeout=10: [])

    result = paper_audit.verify_reference_online(ref)

    assert result["online_status"] == "verified"
    assert result["confidence"] >= 0.9
    assert result["matched_sources"][0]["source"] == "Crossref"


def test_lookup_openalex_reference_prefers_exact_title_search(monkeypatch):
    ref = {
        "text": "Haugen, B. R. et al. 2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer: The American Thyroid Association Guidelines Task Force on Thyroid Nodules and Differentiated Thyroid Cancer. Thyroid 26, (2016).",
        "title_hint": "2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer: The American Thyroid Association Guidelines Task Force on Thyroid Nodules and Differentiated Thyroid Cancer",
        "author_hint": "Haugen",
        "container_hint": "Thyroid",
        "year": "2016",
    }

    def fake_get_json(url, timeout=10, headers=None):
        if "filter=title.search" in url:
            return {
                "results": [{
                    "display_name": ref["title_hint"],
                    "publication_year": 2015,
                    "doi": "https://doi.org/10.1089/thy.2015.0020",
                    "authorships": [{"author": {"display_name": "Haugen"}}],
                    "primary_location": {"source": {"display_name": "Thyroid"}},
                }]
            }
        return {"results": []}

    monkeypatch.setattr(paper_audit, "_reference_get_json", fake_get_json)

    matches = paper_audit.lookup_openalex_reference(ref)

    assert matches
    assert matches[0]["title"] == ref["title_hint"]


def test_lookup_official_site_reference_searches_publisher_site(monkeypatch):
    ref = {
        "text": "Haugen, B. R. et al. 2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer. Thyroid 26, (2016).",
        "title_hint": "2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules and Differentiated Thyroid Cancer",
        "author_hint": "Haugen",
        "container_hint": "Thyroid",
        "year": "2016",
    }
    seen_urls = []

    def fake_http(url, method="GET", headers=None, data=None, timeout=60):
        seen_urls.append(url)
        html = """
        <html><title>Thyroid search</title><body>
        2015 American Thyroid Association Management Guidelines for Adult Patients with Thyroid Nodules
        and Differentiated Thyroid Cancer. Published in 2016.
        </body></html>
        """
        return html.encode("utf-8"), 200

    monkeypatch.setattr(paper_audit, "_http_request", fake_http)

    matches = paper_audit.lookup_official_site_reference(ref)

    assert matches
    assert matches[0]["source"] == "Official site: Mary Ann Liebert"
    assert "liebertpub.com" in seen_urls[0]


def test_lookup_official_site_reference_retries_title_tail_for_ocr_damage(monkeypatch):
    ref = {
        "text": "Metallprotease-disintegrin ADAM12 actively promotes the stem cell-like phenotype in claudin-low breast cancer. Mol Cancer 16, (2017).",
        "title_hint": "Metallprotease-disintegrin ADAM12 actively promotes the stem cell-like phenotype in claudin-low breast cancer",
        "container_hint": "Mol Cancer",
        "year": "2017",
    }
    seen_urls = []

    def fake_http(url, method="GET", headers=None, data=None, timeout=60):
        seen_urls.append(url)
        if "Metallprotease" in url:
            return b"<html><body>No results</body></html>", 200
        html = """
        <html><body>
        Metalloprotease-disintegrin ADAM12 actively promotes the stem cell-like phenotype
        in claudin-low breast cancer. Molecular Cancer, 2017.
        </body></html>
        """
        return html.encode("utf-8"), 200

    monkeypatch.setattr(paper_audit, "_http_request", fake_http)

    matches = paper_audit.lookup_official_site_reference(ref)

    assert matches
    assert matches[0]["source"] == "Official site: BMC Molecular Cancer"
    assert len(seen_urls) >= 2


def test_verify_reference_online_uses_official_site_fallback(monkeypatch):
    ref = {
        "text": "Sung,H. et al. Global Cancer Statistics 2020: GLOBOCAN Estimates of Incidence and Mortality Worldwide for 36 Cancers in 185 Countries. CA Cancer JClin 71, 209-249 (2021).",
        "title_hint": "Global Cancer Statistics 2020: GLOBOCAN Estimates of Incidence and Mortality Worldwide for 36 Cancers in 185 Countries",
        "author_hint": "Sung",
        "container_hint": "CA Cancer JClin",
        "year": "2021",
    }

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_official_site_reference", lambda _ref, timeout=10: [{
        "source": "Official site: Wiley Online Library",
        "title": ref["title_hint"],
        "year": "2021",
        "doi": "",
        "authors": ["Sung"],
        "container": "CA Cancer JClin",
        "url": "https://onlinelibrary.wiley.com/action/doSearch?AllField=Global",
        "official_site": True,
    }])

    result = paper_audit.verify_reference_online(ref)

    assert result["online_status"] == "verified"
    assert result["matched_sources"][0]["source"] == "Official site: Wiley Online Library"


def test_verify_reference_online_reports_not_found_without_network_error(monkeypatch):
    ref = {"text": "Invented title. Imaginary Journal. 2021. doi:10.9999/notfound", "doi": "10.9999/notfound", "year": "2021"}

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_official_site_reference", lambda _ref, timeout=10: [])

    result = paper_audit.verify_reference_online(ref)

    assert result["online_status"] == "not_found"
    assert "doi_not_found" in result["problems"]


def test_verify_reference_online_handles_source_errors(monkeypatch):
    ref = {"text": "Network broken reference. Journal. 2022.", "year": "2022", "title_hint": "Network broken reference"}

    def boom(_ref, timeout=10):
        raise RuntimeError("network down")

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", boom)
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", boom)
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", boom)

    result = paper_audit.verify_reference_online(ref)

    assert result["online_status"] == "error"
    assert "all_sources_error" in result["problems"]


def test_audit_references_uses_online_cache(monkeypatch):
    refs = "References\n1. Smith J. Reliable cancer marker discovery. Nature Medicine. 2020. doi:10.1000/abc"
    calls = {"count": 0}

    def fake_verify(ref, timeout=10):
        calls["count"] += 1
        return {"online_status": "verified", "confidence": 1.0, "matched_sources": [], "problems": [], "query": {}}

    monkeypatch.setattr(paper_audit, "verify_reference_online", fake_verify)
    cache = {}

    first = paper_audit.audit_references(refs, online=True, cache=cache)
    second = paper_audit.audit_references(refs, online=True, cache=cache)

    assert first["online_checked"] == 1
    assert second["online_checked"] == 1
    assert calls["count"] == 1


def test_audit_references_checks_all_references_by_default(monkeypatch):
    refs = """References
1. Smith J. Reliable cancer marker discovery. Nature Medicine. 2020. doi:10.1000/abc
2. Jones A. Another reliable paper. Science. 2021. doi:10.1000/def
"""
    calls = {"count": 0}

    def fake_verify(ref, timeout=10):
        calls["count"] += 1
        return {"online_status": "verified", "confidence": 1.0, "matched_sources": [], "problems": [], "query": {}}

    monkeypatch.setattr(paper_audit, "verify_reference_online", fake_verify)

    audit = paper_audit.audit_references(refs, online=True, online_limit=None)

    assert audit["reference_count"] == 2
    assert audit["online_checked"] == 2
    assert calls["count"] == 2


def test_audit_references_all_verified_overrides_format_only_weak_status(monkeypatch):
    refs = """References
1. Smith J. Reliable cancer marker discovery. Nature Medicine. 2020.
2. Jones A. Another reliable paper. Science. 2021.
"""

    monkeypatch.setattr(
        paper_audit,
        "verify_reference_online",
        lambda ref, timeout=10: {"online_status": "verified", "confidence": 1.0, "matched_sources": [], "problems": [], "query": {}},
    )

    audit = paper_audit.audit_references(refs, online=True, online_limit=None)

    assert audit["reference_count"] == 2
    assert audit["online_checked"] == 2
    assert audit["status"] == "ok"


def test_extract_images_from_mineru_zip(tmp_path):
    zip_path = tmp_path / "paper.abc.mineru.zip"
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("images/figure1.png", image_bytes)
        zf.writestr("tiny.png", b"x")

    images = paper_audit.collect_mineru_image_files(str(tmp_path), output_dir=tmp_path)

    assert len(images) == 1
    assert Path(images[0]).suffix == ".png"


def test_collect_mineru_image_files_reuses_extracted_image_cache_without_zip(tmp_path):
    cache_dir = tmp_path / "_paper_audit_images"
    cache_dir.mkdir()
    image_path = cache_dir / "cached.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    images = paper_audit.collect_mineru_image_files(str(tmp_path), output_dir=tmp_path)

    assert images == [str(image_path.resolve())] or images == [str(image_path)]


def test_collect_mineru_image_files_ignores_stale_cache_when_zip_exists(tmp_path):
    cache_dir = tmp_path / "_paper_audit_images"
    cache_dir.mkdir()
    stale_image = cache_dir / "paper.old.mineru_stale.png"
    stale_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    zip_path = tmp_path / "paper.new.mineru.zip"
    fresh_bytes = b"\x89PNG\r\n\x1a\n" + b"y" * (paper_audit.MIN_IMAGE_BYTES + 10)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("images/fresh.png", fresh_bytes)

    images = paper_audit.collect_mineru_image_files(str(tmp_path), output_dir=tmp_path)

    assert len(images) == 1
    assert Path(images[0]).name == "paper.new.mineru_fresh.png"
    assert Path(images[0]).read_bytes() == fresh_bytes


def test_latest_mineru_zips_keeps_newest_per_source(tmp_path):
    older = tmp_path / "paper.11111111-1111-1111-1111-111111111111.mineru.zip"
    newer = tmp_path / "paper.22222222-2222-2222-2222-222222222222.mineru.zip"
    other = tmp_path / "supplement.33333333-3333-3333-3333-333333333333.mineru.zip"
    for path in (older, newer, other):
        path.write_text("zip-placeholder", encoding="utf-8")
    older_time = 100
    newer_time = 200
    other_time = 150
    import os
    os.utime(older, (older_time, older_time))
    os.utime(newer, (newer_time, newer_time))
    os.utime(other, (other_time, other_time))

    selected = {Path(path).name for path in paper_audit._latest_mineru_zips([older, newer, other])}

    assert selected == {newer.name, other.name}


def test_no_resume_still_allows_llm_cache_only_read():
    assert paper_audit._allow_llm_cache_read(no_resume=True, llm_cache_only=True)
    assert not paper_audit._allow_llm_cache_read(no_resume=True, llm_cache_only=False)
    assert paper_audit._allow_llm_cache_read(no_resume=False, llm_cache_only=False)


def test_retry_command_from_args_preserves_resume_scope():
    args = types.SimpleNamespace(
        output="reports/final.md",
        json=True,
        no_open=True,
        mineru=False,
        no_mineru=False,
        mineru_model="vlm",
        mineru_lang="ch",
        max_chars=4096,
        reference_online_limit=None,
        reference_timeout=20,
        no_reference_online=False,
        no_resource_online=True,
        resource_timeout=15,
        image_audit_limit=None,
        no_image_semantic=False,
        image_semantic_limit=30,
        image_semantic_timeout=120,
        no_image_detector=False,
        image_detector_limit=None,
        image_detector_timeout=90,
        llm_timeout=180,
        llm_retries=2,
        strict_failed_chunks=False,
        ai_detect=False,
        image_detect=False,
        no_resume=True,
        fresh=True,
    )

    command = paper_audit.retry_command_from_args(args, Path("Test_paper"))

    assert command.startswith("python paper_audit.py Test_paper")
    assert "--output reports/final.md" in command
    assert "--json" in command
    assert "--no-open" in command
    assert "--no-resource-online" in command
    assert "--image-semantic-timeout 120" in command
    assert "--llm-retries 2" in command
    assert "--no-resume" not in command
    assert "--fresh" not in command


def test_failed_artifact_options_uses_output_prefix(monkeypatch, tmp_path):
    args = types.SimpleNamespace(output="full_risk_from_scratch.md")
    monkeypatch.chdir(tmp_path)

    options = paper_audit._failed_artifact_options(tmp_path / "paper_dir", tmp_path, args)
    failure = paper_audit.AuditFailure(
        capability="text_llm",
        error_class="provider_unavailable",
        message="down",
    )

    md_path, json_path = paper_audit.save_failed_audit_diagnostics(
        failure,
        tmp_path / "paper_dir",
        **options,
    )

    assert md_path == tmp_path / "full_risk_from_scratch.failed.md"
    assert json_path == tmp_path / "full_risk_from_scratch.failed.json"


def test_call_glm_image_semantics_parses_json_response(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)

    payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": "一张科研流程图",
                    "image_type": "流程图",
                    "scientific_context": "方法流程说明",
                    "visible_text": "Input Output",
                    "reasonability": "合理",
                    "risks": [],
                    "manual_checks": ["核对图注"],
                    "confidence": 0.82,
                }, ensure_ascii=False)
            }
        }]
    }

    def fake_http(url, method="GET", headers=None, data=None, timeout=60):
        assert method == "POST"
        assert "Authorization" in headers
        body = json.loads(data.decode("utf-8"))
        assert body["model"] == "glm-test"
        assert body["max_tokens"] == 10000
        assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/")
        return json.dumps(payload).encode("utf-8"), 200

    monkeypatch.setattr(paper_audit, "_http_request", fake_http)

    result = paper_audit.call_glm_image_semantics(str(image_path), api_key="test-key", model="glm-test")

    assert result["status"] == "ok"
    assert result["summary"] == "一张科研流程图"
    assert result["image_type"] == "流程图"
    assert result["visible_text"] == "Input Output"
    assert result["confidence"] == 0.82


def test_call_glm_image_semantics_reports_rate_limit(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)

    class FakeResponse:
        status_code = 429
        text = '{"error":{"code":"1305","message":"该模型当前访问量过大，请您稍后再试"}}'

        def json(self):
            return {"error": {"code": "1305", "message": "该模型当前访问量过大，请您稍后再试"}}

    class FakeHTTPError(Exception):
        response = FakeResponse()

    def fake_http(*args, **kwargs):
        raise FakeHTTPError("429 Client Error")

    monkeypatch.setattr(paper_audit, "_http_request", fake_http)

    result = paper_audit.call_glm_image_semantics(str(image_path), api_key="test-key", model="glm-test")

    assert result["status"] == "error"
    assert result["http_status"] == 429
    assert "glm_rate_limited" in result["risks"]
    assert "访问量过大" in result["error_message"]


def test_call_glm_image_semantics_treats_no_image_response_as_error(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
    payload = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": "未检测到上传的图片，无法进行语义理解与合理性审查",
                    "image_type": "其他",
                    "reasonability": "需人工核对",
                    "risks": ["缺少图像数据，无法执行分析"],
                    "manual_checks": [],
                    "confidence": 0,
                }, ensure_ascii=False)
            }
        }]
    }

    monkeypatch.setattr(
        paper_audit,
        "_http_request",
        lambda *args, **kwargs: (json.dumps(payload).encode("utf-8"), 200),
    )

    result = paper_audit.call_glm_image_semantics(str(image_path), api_key="test-key", model="deepseek-v4-flash")

    assert result["status"] == "error"
    assert result["error_reason"] == "image_input_not_received"
    assert "image_input_not_supported" in result["risks"]


def test_call_glm_image_semantics_treats_plain_no_image_response_as_error(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
    payload = {
        "choices": [{
            "message": {
                "content": "未提供图片，无法进行审查"
            }
        }]
    }

    monkeypatch.setattr(
        paper_audit,
        "_http_request",
        lambda *args, **kwargs: (json.dumps(payload).encode("utf-8"), 200),
    )

    result = paper_audit.call_glm_image_semantics(str(image_path), api_key="test-key", model="deepseek-v4-flash")

    assert result["status"] == "error"
    assert result["error_reason"] == "image_input_not_received"
    assert "image_input_not_supported" in result["risks"]


def test_call_glm_image_semantics_accepts_reasoning_content_response(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
    payload = {
        "choices": [{
            "message": {
                "role": "assistant",
                "reasoning_content": json.dumps({
                    "summary": "一张标题为Sample 2的水平条形图",
                    "image_type": "图",
                    "scientific_context": "展示不同节点的输出值",
                    "visible_text": "Sample 2, From Node, Output",
                    "reasonability": "需人工核对",
                    "risks": ["需核对图注解释"],
                    "manual_checks": ["核对正文是否解释这些节点输出值"],
                    "confidence": 0.74,
                }, ensure_ascii=False),
            }
        }]
    }

    monkeypatch.setattr(
        paper_audit,
        "_http_request",
        lambda *args, **kwargs: (json.dumps(payload).encode("utf-8"), 200),
    )

    result = paper_audit.call_glm_image_semantics(str(image_path), api_key="test-key", model="mimo-v2.5-free")

    assert result["status"] == "ok"
    assert result["summary"] == "一张标题为Sample 2的水平条形图"
    assert result["visible_text"] == "Sample 2, From Node, Output"
    assert result["confidence"] == 0.74


def test_image_semantic_display_includes_visual_fields():
    summary, status = paper_audit._image_semantic_display({
        "semantic": {
            "summary": "一张热图",
            "image_type": "热图",
            "scientific_context": "展示基因表达聚类",
            "visible_text": "Gene A",
            "reasonability": "需人工核对",
            "risks": ["色标不可见"],
            "manual_checks": ["核对图注"],
            "confidence": 0.73,
        }
    })

    assert "类型: 热图" in summary
    assert "可读文字: Gene A" in summary
    assert "风险: 色标不可见" in summary
    assert "复核: 核对图注" in summary
    assert status == "需人工核对 / 置信度 0.73"


def test_call_imagedetector_uses_web_upload_flow(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"x" * 2048)
    calls = []

    monkeypatch.setattr(
        paper_audit,
        "_prepare_detector_upload_file",
        lambda path: ("figure.png", "image/png", b"x" * 2048),
    )

    def fake_http(url, method="GET", headers=None, data=None, timeout=60):
        calls.append((method, url, headers or {}, data))
        if method == "GET":
            assert "/api/get-presigned-url?" in url
            return json.dumps({
                "presignedUrl": "https://upload.test/object",
                "filePath": "uploads/figure.png",
                "expectedContentType": "image/png",
            }).encode("utf-8"), 200
        if method == "PUT":
            assert url == "https://upload.test/object"
            assert headers["Content-Type"] == "image/png"
            assert data == b"x" * 2048
            return b"", 200
        if method == "POST":
            body = json.loads(data.decode("utf-8"))
            assert body["imageUrl"] == f"{paper_audit.IMAGE_DETECT_UPLOAD_BASE}/uploads/figure.png"
            return json.dumps({
                "success": True,
                "result": 87.5,
                "isAI": True,
                "confidence": "High",
                "result_details": {"source": "Midjourney"},
                "preview_url": "https://example.test/preview.png",
                "image_id": "img-1",
            }).encode("utf-8"), 200
        raise AssertionError(method)

    monkeypatch.setattr(paper_audit, "_http_request", fake_http)

    result = paper_audit.call_imagedetector(str(image_path), timeout=12)

    assert [call[0] for call in calls] == ["GET", "PUT", "POST"]
    assert result["status"] == "ok"
    assert result["score"] == 87.5
    assert result["label"] == "AI生成"
    assert result["source"] == "Midjourney"


def test_build_image_audit_uses_semantic_cache(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(image_path)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 200,
        "height": 100,
    })
    calls = {"count": 0}

    def fake_semantic(path, timeout=45):
        calls["count"] += 1
        return {"status": "ok", "summary": "显微图", "reasonability": "需人工核对", "risks": [], "confidence": 0.7}

    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", fake_semantic)
    cache = {}

    first = paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    second = paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)

    assert first["semantic_checked"] == 1
    assert second["images"][0]["semantic"]["summary"] == "显微图"
    assert calls["count"] == 1


def test_build_image_audit_semantic_cache_key_includes_service_context(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(image_path)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 200,
        "height": 100,
    })
    monkeypatch.setattr(paper_audit, "GLM_API_URL", "https://vision-a.example.test/v1")
    monkeypatch.setattr(paper_audit, "GLM_VISION_MODEL", "model-a")
    original_cache_version = paper_audit.IMAGE_SEMANTIC_CACHE_VERSION
    calls = []

    def fake_semantic(path, timeout=45):
        calls.append((paper_audit.GLM_API_URL, paper_audit.GLM_VISION_MODEL, paper_audit.IMAGE_SEMANTIC_CACHE_VERSION))
        return {
            "status": "ok",
            "summary": paper_audit.GLM_VISION_MODEL,
            "reasonability": "合理",
            "risks": [],
            "confidence": 0.8,
        }

    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", fake_semantic)
    cache = {}

    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    monkeypatch.setattr(paper_audit, "GLM_VISION_MODEL", "model-b")
    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    monkeypatch.setattr(paper_audit, "GLM_API_URL", "https://vision-b.example.test/v1")
    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    monkeypatch.setattr(paper_audit, "IMAGE_SEMANTIC_CACHE_VERSION", original_cache_version + 1)
    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)

    assert calls == [
        ("https://vision-a.example.test/v1", "model-a", original_cache_version),
        ("https://vision-a.example.test/v1", "model-b", original_cache_version),
        ("https://vision-b.example.test/v1", "model-b", original_cache_version),
        ("https://vision-b.example.test/v1", "model-b", original_cache_version + 1),
    ]
    assert len(cache) == 4
    assert all(":image_semantic:" in key for key in cache)


def test_build_image_audit_flushes_semantic_cache_after_each_success(monkeypatch, tmp_path):
    first_image = tmp_path / "a.png"
    second_image = tmp_path / "b.png"
    for image_path in (first_image, second_image):
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(first_image), str(second_image)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 200,
        "height": 100,
    })
    cache = {}
    flushed = []
    cache_path = tmp_path / "image_semantic_cache.json"

    def fake_semantic(path, timeout=45):
        if Path(path).name == "b.png":
            raise KeyboardInterrupt("stop after first image")
        return {"status": "ok", "summary": "first image", "reasonability": "合理", "risks": [], "confidence": 0.8}

    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", fake_semantic)

    try:
        paper_audit.build_image_audit(
            str(tmp_path),
            limit=2,
            semantic=True,
            semantic_cache=cache,
            semantic_cache_save=lambda: (flushed.append(json.loads(json.dumps(cache))), paper_audit._json_save(cache_path, cache)),
            detector=False,
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected interrupted semantic image audit")

    assert len(flushed) == 1
    assert any(value.get("summary") == "first image" for value in flushed[0].values())
    saved_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert any(value.get("summary") == "first image" for value in saved_cache.values())


def test_load_merged_json_dicts_combines_visible_and_resume_cache(tmp_path):
    visible_cache = tmp_path / "image_semantic_cache.json"
    resume_cache = tmp_path / ".paper.paper_audit_resume" / "image_semantic_cache.json"
    paper_audit._json_save(visible_cache, {
        "visible-only": {"summary": "visible"},
        "conflict": {"summary": "visible stale"},
    })
    paper_audit._json_save(resume_cache, {
        "resume-only": {"summary": "resume"},
        "conflict": {"summary": "resume fresh"},
    })

    merged = paper_audit._load_merged_json_dicts(visible_cache, resume_cache)

    assert merged["visible-only"]["summary"] == "visible"
    assert merged["resume-only"]["summary"] == "resume"
    assert merged["conflict"]["summary"] == "resume fresh"


def test_build_image_audit_uses_detector_cache(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(image_path)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 240,
        "height": 160,
    })
    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", lambda path, timeout=45: {
        "status": "ok",
        "summary": "流程图",
        "reasonability": "合理",
        "risks": [],
        "confidence": 0.8,
    })
    calls = {"count": 0}

    def fake_detector(path, timeout=60):
        calls["count"] += 1
        return {"status": "ok", "score": 12.0, "label": "真实/人工", "provider": "imagedetector.com"}

    monkeypatch.setattr(paper_audit, "call_imagedetector", fake_detector)
    cache = {}

    first = paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache={}, detector=True, detector_cache=cache)
    second = paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache={}, detector=True, detector_cache=cache)

    assert first["detector_checked"] == 1
    assert second["images"][0]["detector"]["score"] == 12.0
    assert calls["count"] == 1


def test_build_image_audit_flushes_detector_cache_after_each_success(monkeypatch, tmp_path):
    first_image = tmp_path / "a.png"
    second_image = tmp_path / "b.png"
    for image_path in (first_image, second_image):
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(first_image), str(second_image)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 240,
        "height": 160,
    })
    cache = {}
    flushed = []

    def fake_detector(path, timeout=60):
        if Path(path).name == "b.png":
            raise KeyboardInterrupt("stop after first image")
        return {"status": "ok", "score": 9.0, "label": "真实/人工", "provider": "imagedetector.com"}

    monkeypatch.setattr(paper_audit, "call_imagedetector", fake_detector)

    try:
        paper_audit.build_image_audit(
            str(tmp_path),
            limit=2,
            semantic=False,
            detector=True,
            detector_cache=cache,
            detector_cache_save=lambda: flushed.append(json.loads(json.dumps(cache))),
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected interrupted imagedetector audit")

    assert len(flushed) == 1
    assert any(value.get("score") == 9.0 for value in flushed[0].values())


def test_alarm_timeout_bounds_image_capability_calls():
    started = time.monotonic()

    result = paper_audit._run_with_alarm_timeout(
        lambda: time.sleep(2),
        1,
        lambda: {"status": "error", "reason": "timeout"},
    )

    assert result == {"status": "error", "reason": "timeout"}
    assert time.monotonic() - started < 1.8


def test_build_image_audit_checks_all_images_by_default(monkeypatch, tmp_path):
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    image_a.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))
    image_b.write_bytes(b"\x89PNG\r\n\x1a\n" + b"y" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(image_a), str(image_b)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 200,
        "height": 100,
    })
    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", lambda path, timeout=45: {"status": "ok", "summary": Path(path).name})
    monkeypatch.setattr(paper_audit, "call_imagedetector", lambda path, timeout=60: {"status": "ok", "score": 1.0, "label": "真实/人工"})

    audit = paper_audit.build_image_audit(str(tmp_path), limit=None, semantic=True, semantic_limit=None, detector=True, detector_limit=None)

    assert audit["image_count"] == 2
    assert audit["checked_count"] == 2
    assert audit["semantic_checked"] == 2
    assert audit["detector_checked"] == 2


def test_launch_image_ai_detect_runs_automatic_subtool_without_browser(monkeypatch, tmp_path):
    captured = {}

    def fake_build(input_path, **kwargs):
        captured["input_path"] = input_path
        captured["kwargs"] = kwargs
        return {
            "image_count": 1,
            "checked_count": 1,
            "semantic_checked": 1,
            "detector_checked": 1,
            "images": [{
                "path": str(tmp_path / "figure.png"),
                "file": "figure.png",
                "risk": "local_ok",
                "issues": [],
                "semantic": {"summary": "流程图", "reasonability": "合理"},
                "detector": {"status": "ok", "score": 8.0, "label": "真实/人工"},
            }],
        }

    opened = []
    monkeypatch.setattr(paper_audit, "build_image_audit", fake_build)
    monkeypatch.setattr(paper_audit, "webbrowser", type("WB", (), {"open": staticmethod(lambda url: opened.append(url))}))

    result = paper_audit.launch_image_ai_detect(
        str(tmp_path),
        output_dir=tmp_path,
        limit=3,
        semantic=True,
        semantic_limit=2,
        detector=True,
        detector_limit=2,
        semantic_cache={},
        detector_cache={},
    )

    assert result["detector_checked"] == 1
    assert captured["kwargs"]["detector"] is True
    assert captured["kwargs"]["semantic"] is True
    assert opened == []
    assert (tmp_path / "image_ai_review_manifest.html").exists()


def test_build_image_audit_does_not_cache_glm_errors(monkeypatch, tmp_path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(image_path)])
    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", lambda path: {
        "path": path,
        "file": Path(path).name,
        "risk": "local_ok",
        "issues": [],
        "width": 200,
        "height": 100,
    })
    calls = {"count": 0}

    def fake_semantic(path, timeout=45):
        calls["count"] += 1
        return {"status": "error", "summary": "需稍后重试", "reasonability": "需人工核对", "risks": [], "confidence": 0}

    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", fake_semantic)
    cache = {}

    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)
    paper_audit.build_image_audit(str(tmp_path), limit=1, semantic=True, semantic_cache=cache)

    assert calls["count"] == 2
    assert cache == {}


def test_build_image_audit_prioritizes_informative_images_for_semantics(monkeypatch, tmp_path):
    strip = tmp_path / "strip.png"
    rich = tmp_path / "rich.png"
    strip.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))
    rich.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (paper_audit.MIN_IMAGE_BYTES + 10))

    monkeypatch.setattr(paper_audit, "collect_image_files", lambda *args, **kwargs: [str(strip), str(rich)])

    def fake_analyze(path):
        if Path(path).name == "strip.png":
            return {
                "path": path,
                "file": "strip.png",
                "risk": "local_warning",
                "issues": ["low_resolution", "extreme_aspect_ratio"],
                "width": 900,
                "height": 20,
            }
        return {
            "path": path,
            "file": "rich.png",
            "risk": "local_ok",
            "issues": [],
            "width": 800,
            "height": 600,
        }

    calls = []

    def fake_semantic(path, timeout=45):
        calls.append(Path(path).name)
        return {"status": "ok", "summary": Path(path).stem, "reasonability": "合理", "risks": [], "confidence": 0.8}

    monkeypatch.setattr(paper_audit, "analyze_image_reasonability", fake_analyze)
    monkeypatch.setattr(paper_audit, "call_glm_image_semantics", fake_semantic)

    audit = paper_audit.build_image_audit(str(tmp_path), limit=2, semantic=True, semantic_limit=1, semantic_cache={})

    assert calls == ["rich.png"]
    by_name = {item["file"]: item for item in audit["images"]}
    assert by_name["rich.png"]["semantic"]["summary"] == "rich"
    assert "semantic" not in by_name["strip.png"]


def test_image_semantic_display_explains_uncovered_local_warning():
    summary, status = paper_audit._image_semantic_display({
        "risk": "local_warning",
        "issues": ["low_resolution", "extreme_aspect_ratio"],
    })

    assert "未进入图像语义分析优先队列" in summary
    assert status == "人工优先"


def test_action_summary_includes_multiple_detection_sources():
    checks = [{
        "category": "数据与结果",
        "item": "模型指标异常",
        "verdict": "🚩红旗",
        "detail": "多个模型指标完全一致，需复核原始预测结果。",
    }]
    checks.extend({
        "category": "方法论",
        "item": f"高分LLM问题{i}",
        "verdict": "🚩红旗",
        "detail": "严重问题。" * 20,
    } for i in range(10))
    report = {
        "checks": checks
    }
    meta = {
        "reference_audit": {
            "online_enabled": True,
            "issues": [{"index": 1, "issues": ["online_not_found"]}],
            "references": [{"online": {"online_status": "not_found"}}],
        },
        "image_audit": {
            "images": [{
                "risk": "local_warning",
                "semantic": {"reasonability": "需人工核对"},
            }]
        },
    }
    stat = {"benford_status": "高偏差⚠️", "benford_deviation": 0.5}

    items = paper_audit.build_audit_action_items(report, meta, stat)
    sources = {item["source"] for item in items}

    assert {"LLM语义审查", "本地统计", "参考文献在线检索", "图像检测"}.issubset(sources)


def test_reference_issue_text_uses_chinese_labels():
    text = paper_audit._reference_issue_text(["missing_doi", "online_not_found", "year_mismatch"])

    assert "缺少DOI" in text
    assert "在线未检索到" in text
    assert "年份不一致" in text


def test_image_review_manifest_uses_cards_and_semantic_text(tmp_path):
    audit = {
        "images": [{
            "path": str(tmp_path / "figure.png"),
            "file": "figure.png",
            "risk": "local_warning",
            "issues": ["low_resolution"],
            "semantic": {
                "summary": "流程图",
                "image_type": "流程图",
                "visible_text": "Input",
                "reasonability": "需人工核对",
            },
            "detector": {"status": "ok", "score": 75.0, "label": "AI生成"},
        }]
    }
    (tmp_path / "figure.png").write_bytes(b"not really an image")

    path = paper_audit.save_image_review_manifest(audit, tmp_path)
    html = path.read_text(encoding="utf-8")

    assert 'class="image-card"' in html
    assert "<table" not in html
    assert "图像语义分析" in html
    assert "类型: 流程图" in html
    assert "可读文字: Input" in html
    assert "imagedetector自动结果" in html
    assert "AI分数 75.0" in html


def test_parse_report_extracts_json_from_fenced_response():
    raw = """```json
{"summary":"ok","risk_level":"低","detection_score":3,"checks":[],"conclusion":"done"}
```"""

    parsed = paper_audit.parse_report(raw)

    assert parsed["summary"] == "ok"
    assert parsed["risk_level"] == "低"
    assert not parsed.get("parse_error")


def test_parse_report_preserves_partial_truncated_json():
    raw = """{
  "summary": "文本严重乱码",
  "risk_level": "高",
  "detection_score": 95,
  "checks": [
    {
      "category": "结构与引用",
      "item": "文本完整性",
      "verdict": "🚩红旗"
"""

    parsed = paper_audit.parse_report(raw)

    assert not parsed.get("parse_error")
    assert parsed["_schema_recovered"] is True
    assert "truncated_json" in parsed["schema_errors"]
    assert parsed["partial_fields"]["summary"] == "文本严重乱码"
    assert parsed["partial_fields"]["risk_level"] == "高"
    assert parsed["partial_fields"]["verdict"] == "🚩红旗"
    assert parsed["checks"][0]["recommendation"]


def test_parse_report_rejects_findings_missing_required_schema_fields():
    raw = json.dumps({
        "summary": "missing fields",
        "risk_level": "中",
        "checks": [{
            "category": "数据与结果",
            "item": "缺少证据字段",
            "verdict": "⚠️疑点",
            "evidence": "n=20",
            "reason": "样本量需要核验",
        }],
        "conclusion": "retry",
    }, ensure_ascii=False)

    parsed = paper_audit.parse_report(raw)

    assert not parsed.get("parse_error")
    assert parsed["_schema_recovered"] is True
    assert "missing_or_invalid_check_fields" in parsed["schema_errors"]
    assert parsed["checks"][0]["source_text"] == "未找到直接原文证据"
    assert parsed["checks"][0]["confidence"] == 0.2


def test_parse_report_normalizes_valid_strict_finding():
    raw = json.dumps({
        "summary": "ok",
        "risk_level": "低",
        "detection_score": 0,
        "checks": [{
            "category": "数据与结果",
            "item": "样本量",
            "verdict": "✅通过",
            "source": "Methods",
            "source_text": "n=20",
            "evidence": "Methods reports n=20.",
            "reason": "样本量前后一致。",
            "recommendation": "无需额外处理。",
            "confidence": 0.91,
        }],
        "conclusion": "ok",
    }, ensure_ascii=False)

    parsed = paper_audit.parse_report(raw)

    assert not parsed.get("parse_error")
    assert parsed["checks"][0]["source"] == "Methods"
    assert parsed["checks"][0]["confidence"] == 0.91
    assert parsed["_raw_response_preserved"] is True


def test_merge_chunk_reports_keeps_more_severe_duplicate_verdict():
    reports = [
        {
            "summary": "a",
            "risk_level": "低",
            "checks": [{"category": "数据与结果", "item": "p值", "verdict": "✅通过"}],
        },
        {
            "summary": "b",
            "risk_level": "高",
            "checks": [{"category": "数据与结果", "item": "p值", "verdict": "🚩红旗"}],
        },
    ]

    merged = paper_audit.merge_chunk_reports(reports)

    assert merged["risk_level"] == "中"
    assert len(merged["checks"]) == 1
    assert merged["checks"][0]["verdict"] == "🚩红旗"


def test_merge_chunk_reports_consolidates_similar_findings():
    reports = [
        {
            "summary": "a",
            "risk_level": "中",
            "checks": [{
                "category": "参考文献",
                "item": "参考文献年份异常",
                "verdict": "⚠️疑点",
                "evidence": "Reference 12 metadata year differs from cited year.",
                "reason": "参考文献年份与在线元数据不一致，需要核验。",
            }],
        },
        {
            "summary": "b",
            "risk_level": "中",
            "checks": [{
                "category": "参考文献",
                "item": "引用年份和在线元数据不一致",
                "verdict": "🚩红旗",
                "evidence": "Reference 12 cited year does not match Crossref metadata.",
                "reason": "参考文献年份与在线元数据不一致，需要核验。",
            }],
        },
    ]

    merged = paper_audit.merge_chunk_reports(reports)

    assert len(merged["checks"]) == 1
    assert merged["checks"][0]["verdict"] == "🚩红旗"
    assert merged["checks"][0]["_merged_similar_count"] == 2


def test_future_publication_flag_uses_runtime_year_not_llm_knowledge(monkeypatch):
    monkeypatch.setattr(paper_audit, "runtime_utc_year", lambda: 2026)
    report = {
        "summary": "ok",
        "risk_level": "高",
        "checks": [{
            "category": "参考文献",
            "item": "发表时间在未来",
            "verdict": "🚩红旗",
            "evidence": "该文献被模型认为尚未发表，但未给出晚于当前年份的元数据。",
            "reason": "LLM知识库认为该出版时间在未来。",
        }],
        "conclusion": "ok",
    }

    ruled = paper_audit.apply_risk_rules(report)

    assert ruled["checks"][0]["verdict"] == "⚠️疑点"
    assert ruled["checks"][0]["_verdict_adjusted"] == "future_publication_runtime_year_not_confirmed"
    assert ruled["checks"][0]["_runtime_year_check"]["current_year"] == 2026
    assert ruled["score_breakdown"]["red_flags"] == 0


def test_future_publication_flag_keeps_future_year_when_evidence_exceeds_runtime(monkeypatch):
    monkeypatch.setattr(paper_audit, "runtime_utc_year", lambda: 2026)
    report = {
        "summary": "ok",
        "risk_level": "高",
        "checks": [{
            "category": "参考文献",
            "item": "发表时间在未来",
            "verdict": "🚩红旗",
            "evidence": "Crossref publication year is 2028.",
            "reason": "发表年份2028晚于当前运行时间。",
        }],
        "conclusion": "ok",
    }

    ruled = paper_audit.apply_risk_rules(report)

    assert ruled["checks"][0]["verdict"] == "🚩红旗"
    assert ruled["checks"][0]["_runtime_year_check"]["future_years"] == [2028]


def test_audit_references_marks_future_year_by_runtime_clock(monkeypatch):
    monkeypatch.setattr(paper_audit, "runtime_utc_year", lambda: 2026)

    audit = paper_audit.audit_references(
        "1. Future A. Runtime year based reference. Journal X. 2028. doi:10.1000/future",
        online=False,
    )

    assert "future_year" in audit["issues"][0]["issues"]
    assert "年份晚于运行时当前年份" in paper_audit._reference_issue_text(audit["issues"][0]["issues"])


def test_merge_chunk_reports_does_not_escalate_ocr_noise_to_high_risk():
    reports = []
    for idx in range(8):
        reports.append({
            "summary": f"chunk {idx}",
            "risk_level": "中",
            "checks": [{
                "category": "图片与图表",
                "item": f"表格OCR提取异常{idx}",
                "verdict": "⚠️疑点",
                "detail": "OCR提取错位，表格结构不清，需要人工核对原PDF；当前不构成造假结论。",
            }],
        })

    merged = paper_audit.merge_chunk_reports(reports, {"benford_deviation": 0.45, "p_value_abnormal": 0})

    assert merged["risk_level"] == "低"
    assert merged["score_breakdown"]["evidence_warnings"] == 0
    assert merged["score_breakdown"]["extraction_warnings"] == 8
    assert merged["detection_score"] < 50


def test_merge_chunk_reports_downgrades_ocr_table_red_flag():
    reports = [{
        "summary": "a",
        "risk_level": "高",
        "checks": [{
            "category": "数据与结果",
            "item": "表格中出现完全重复的数据行",
            "verdict": "🚩红旗",
            "source_text": "<tr><td>1</td><td>2</td></tr> 出现两次",
            "detail": "该表格来自OCR提取，可能为OCR错位，需要人工核对原PDF确认。",
        }],
    }]

    merged = paper_audit.merge_chunk_reports(reports + [{"summary": "b", "risk_level": "低", "checks": []}])

    assert merged["checks"][0]["verdict"] == "⚠️疑点"
    assert merged["checks"][0]["_verdict_adjusted"] == "extraction_red_flag_downgraded"
    assert merged["score_breakdown"]["red_flags"] == 0
    assert merged["risk_level"] == "低"


def test_merge_chunk_reports_rebuilds_conclusion_after_ocr_red_flag_downgrade():
    reports = [{
        "summary": "原始分段称表格重复为红旗",
        "risk_level": "高",
        "conclusion": "基于明显的表格重复行，判定为红旗。建议拒稿。",
        "checks": [{
            "category": "数据与结果",
            "item": "表格中出现完全重复的数据行",
            "verdict": "🚩红旗",
            "source_text": "<tr><td>1</td><td>2</td></tr> 出现两次",
            "detail": "该表格来自OCR提取，可能为OCR错位，需要人工核对原PDF确认。判定为红旗。再判断是否构成🚩红旗。建议拒稿。",
        }],
    }, {"summary": "b", "risk_level": "低", "checks": []}]

    merged = paper_audit.merge_chunk_reports(reports)

    assert merged["score_breakdown"]["red_flags"] == 0
    assert "判定为红旗" not in merged["summary"]
    assert "判定为红旗" not in merged["conclusion"]
    assert "建议拒稿" not in merged["conclusion"]
    assert "未发现可直接保留为红旗" in merged["conclusion"]
    assert "逐段审查中的红旗表述已自动降级" in merged["conclusion"]
    assert "判定为红旗" not in merged["checks"][0]["detail"]
    assert "构成🚩红旗" not in merged["checks"][0]["detail"]


def test_merge_chunk_reports_softens_conditional_red_flag_language_for_warnings():
    reports = [{
        "summary": "a",
        "risk_level": "低",
        "checks": [{
            "category": "数据与结果",
            "item": "表格数据不完整或数值异常",
            "verdict": "⚠️疑点",
            "reason": "不应直接判定为红旗。",
            "detail": "需人工核对原PDF，再判断是否构成🚩红旗。",
        }],
    }, {"summary": "b", "risk_level": "低", "checks": []}]

    merged = paper_audit.merge_chunk_reports(reports)

    assert "构成🚩红旗" not in merged["checks"][0]["detail"]
    assert "判定为红旗" not in merged["checks"][0]["reason"]
    assert "升级为严重问题" in merged["checks"][0]["detail"]


def test_apply_risk_rules_overrides_llm_risk_level_and_records_version():
    report = {"summary": "LLM says high", "risk_level": "高", "detection_score": 99, "checks": [], "conclusion": "raw"}

    ruled = paper_audit.apply_risk_rules(report)

    assert ruled["risk_level"] == "低"
    assert ruled["detection_score"] == 0
    assert ruled["rule_version"] == paper_audit.RISK_RULE_VERSION
    assert ruled["score_breakdown"]["rule_version"] == paper_audit.RISK_RULE_VERSION


def test_apply_risk_rules_imagedetector_high_score_alone_is_not_highest_risk():
    report = {"summary": "ok", "risk_level": "低", "checks": [], "conclusion": "ok"}
    image_audit = {"images": [{"detector": {"status": "ok", "score": 99.0}}]}

    ruled = paper_audit.apply_risk_rules(report, image_audit=image_audit)

    assert ruled["risk_level"] == "中"
    assert ruled["risk_level"] != "严重证据冲突"
    assert ruled["score_breakdown"]["image_detector_high"] == 1


def test_apply_risk_rules_can_emit_severe_evidence_conflict():
    report = {"summary": "ok", "risk_level": "低", "checks": [
        {"category": "数据", "item": "a", "verdict": "🚩红旗"},
        {"category": "数据", "item": "b", "verdict": "🚩红旗"},
        {"category": "引用", "item": "c", "verdict": "⚠️疑点"},
        {"category": "方法", "item": "d", "verdict": "⚠️疑点"},
    ], "conclusion": "ok"}

    ruled = paper_audit.apply_risk_rules(report)

    assert ruled["risk_level"] == "严重证据冲突"
    assert ruled["detection_score"] >= 85


def test_format_html_report_normalizes_cached_directory_meta(tmp_path):
    (tmp_path / "paper.pdf").write_bytes(b"%PDF")
    report = {"summary": "ok", "risk_level": "低", "detection_score": 3, "checks": [], "conclusion": "done"}
    stat = {
        "benford_deviation": 0,
        "benford_status": None,
        "p_value_abnormal": 0,
        "p_value_count": 0,
        "sd_count": 0,
        "number_count": 0,
    }

    rendered = paper_audit.format_html_report(
        report,
        str(tmp_path),
        {"input_type": "directory", "extractor": "directory_multi_format"},
        stat,
    )

    assert "N/A MB" not in rendered
    assert "<span>提取方式</span><strong>directory_multi_format</strong>" in rendered


def test_clipboard_windows_uses_clip_exe_without_shell(monkeypatch):
    calls = []

    class DummyProcess:
        returncode = 0

        def communicate(self, data):
            self.data = data

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return DummyProcess()

    monkeypatch.setattr(paper_audit.platform, "system", lambda: "Windows")
    monkeypatch.setattr(paper_audit.subprocess, "Popen", fake_popen)

    assert paper_audit.copy_to_clipboard("hello")
    assert calls[0][0][0] == ["clip.exe"]
    assert calls[0][1]["stdin"] == subprocess.PIPE
    assert "shell" not in calls[0][1]


def test_cli_help_exposes_no_open():
    result = subprocess.run(
        [sys.executable, "paper_audit.py", "--help"],
        cwd=paper_audit.Path(__file__).resolve().parents[1],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--no-open" in result.stdout
    assert "--image-detector-limit" in result.stdout
    assert "--no-resource-online" in result.stdout
    assert "不再打开网页或要求手动上传" in result.stdout
    assert "--serve-report-actions" in result.stdout
    assert "--serve-web" in result.stdout
    assert "--gui" in result.stdout
    assert "--web-port" in result.stdout
    assert "--llm-provider" not in result.stdout
    assert "--ignore-config-llm" not in result.stdout
    assert "mykey.py" not in result.stdout


def test_json_report_payload_shape_stays_stable(tmp_path):
    payload = {
        "llm_report": {"summary": "ok"},
        "stat_result": {"number_count": 1},
        "meta": {"llm_coverage": "1/1"},
    }

    assert json.loads(json.dumps(payload))["meta"]["llm_coverage"] == "1/1"


def test_audit_artifact_paths_separate_complete_and_limited(tmp_path):
    complete_md, complete_html, complete_json = paper_audit.audit_artifact_paths(tmp_path, artifact_type="complete")
    limited_md, limited_html, limited_json = paper_audit.audit_artifact_paths(tmp_path, artifact_type="limited")
    single_md, single_html, single_json = paper_audit.audit_artifact_paths(tmp_path / "paper.pdf", artifact_type="limited")

    assert complete_md == tmp_path / "audit_report.audit.md"
    assert complete_html == tmp_path / "audit_report.audit.html"
    assert complete_json == tmp_path / "audit_report.audit.json"
    assert limited_md == tmp_path / "audit_report.limited.md"
    assert limited_html == tmp_path / "audit_report.limited.html"
    assert limited_json == tmp_path / "audit_report.limited.json"
    assert single_md == tmp_path / "paper.limited.md"
    assert single_html == tmp_path / "paper.limited.html"
    assert single_json == tmp_path / "paper.limited.json"


def test_run_workspace_is_unique_and_records_artifacts(tmp_path):
    input_pdf = tmp_path / "paper.pdf"
    input_pdf.write_bytes(b"%PDF-1.4")
    first = paper_audit.create_run_workspace(input_pdf, tmp_path, "paper")
    second = paper_audit.create_run_workspace(input_pdf, tmp_path, "paper")
    root_report = tmp_path / "paper.audit.md"
    root_report.write_text("report", encoding="utf-8")

    outcome_path = paper_audit.record_run_workspace_artifacts(first, "complete", [root_report], meta={"artifact_type": "complete"})

    assert first["run_id"] != second["run_id"]
    assert Path(first["run_dir"]).is_dir()
    assert Path(second["run_dir"]).is_dir()
    assert (Path(first["artifacts_dir"]) / "paper.audit.md").read_text(encoding="utf-8") == "report"
    payload = json.loads(outcome_path.read_text(encoding="utf-8"))
    assert payload["outcome"] == "complete"
    assert payload["root_shortcuts"] == [str(root_report)]
    assert payload["workspace_artifacts"] == [str(Path(first["artifacts_dir"]) / "paper.audit.md")]


def test_audit_artifact_paths_normalize_explicit_output(tmp_path):
    output = tmp_path / "custom.audit.md"

    md_path, html_path, json_path = paper_audit.audit_artifact_paths(
        tmp_path / "paper.pdf",
        artifact_type="limited",
        output_path=output,
    )

    assert md_path == tmp_path / "custom.limited.md"
    assert html_path == tmp_path / "custom.limited.html"
    assert json_path == tmp_path / "custom.limited.json"


def test_explicit_relative_output_paths_are_cwd_relative(monkeypatch, tmp_path):
    args = types.SimpleNamespace(output="Test_paper2/test_paper2_audit")
    monkeypatch.chdir(tmp_path)

    output_base = paper_audit.explicit_output_path_from_args(args)
    md_path, html_path, json_path = paper_audit.audit_artifact_paths(
        Path("Test_paper2"),
        artifact_type="complete",
        output_path=output_base,
    )
    failed_kwargs = paper_audit._failed_artifact_options(Path("Test_paper2"), Path("Test_paper2"), args)

    assert md_path == tmp_path / "Test_paper2/test_paper2_audit.audit.md"
    assert html_path == tmp_path / "Test_paper2/test_paper2_audit.audit.html"
    assert json_path == tmp_path / "Test_paper2/test_paper2_audit.audit.json"
    assert failed_kwargs == {"output_dir": tmp_path / "Test_paper2", "output_stem": "test_paper2_audit"}


def test_audit_resources_extracts_and_checks_code_and_deployed_urls(monkeypatch):
    text = (
        "Code available at https://github.com/2951121599/streamlit\\_PTC2. "
        "The web links were https://ptc-normal.streamlit.app/ and htps://ptcmetastasize.streamlit.app/."
    )
    calls = []

    def fake_verify(resource, timeout=10):
        calls.append(resource["url"])
        if resource["url"].startswith("htps://"):
            return {"status": "malformed", "problem": "malformed_url"}
        return {"status": "available", "http_status": 200, "problem": ""}

    monkeypatch.setattr(paper_audit, "verify_resource_availability", fake_verify)

    audit = paper_audit.audit_resources(text, online=True, timeout=3, cache={})

    assert audit["resource_count"] == 3
    assert audit["online_checked"] == 3
    urls = [item["url"] for item in audit["resources"]]
    assert "https://github.com/2951121599/streamlit_PTC2" in urls
    assert "https://ptc-normal.streamlit.app/" in urls
    assert "htps://ptcmetastasize.streamlit.app/" in urls
    assert any(issue["status"] == "malformed" for issue in audit["issues"])
    assert calls == urls


def test_resource_audit_renders_markdown_and_html_sections():
    audit = {
        "status": "needs_review",
        "resource_count": 1,
        "online_enabled": True,
        "online_checked": 1,
        "note": "note",
        "issues": [{"index": 1, "status": "unavailable"}],
        "resources": [{
            "url": "https://ptc-normal.streamlit.app/",
            "type": "deployed_resource",
            "context": "web calculator",
            "availability": {"status": "unavailable", "problem": "not_found"},
        }],
    }

    markdown = "\n".join(paper_audit.format_resource_audit_markdown(audit))
    rendered = paper_audit.format_resource_audit_html(audit)

    assert "代码仓库与在线资源可用性校检" in markdown
    assert "https://ptc-normal.streamlit.app/" in markdown
    assert "不可访问" in markdown
    assert "代码仓库与在线资源可用性校检" in rendered
    assert '<a href="https://ptc-normal.streamlit.app/"' in rendered


def test_audit_limited_reasons_track_user_limited_flags():
    args = types.SimpleNamespace(
        no_mineru=True,
        no_reference_online=True,
        no_resource_online=True,
        no_image_semantic=True,
        no_image_detector=False,
        llm_cache_only=True,
    )
    meta = {
        "reference_count": 2,
        "resource_audit": {"resource_count": 1},
        "image_audit": {"image_count": 1},
        "llm_partial_report": True,
        "llm_coverage": "1/2",
        "llm_failed_chunks": [2],
    }

    reasons = paper_audit.audit_limited_reasons(args, meta, has_pdf_input=True)

    assert any("禁用MinerU" in reason for reason in reasons)
    assert any("参考文献在线核验" in reason for reason in reasons)
    assert any("在线资源可用性校检" in reason for reason in reasons)
    assert any("图像语义分析" in reason for reason in reasons)
    assert any("cache-only" in reason for reason in reasons)
    assert any("LLM分块覆盖不足" in reason for reason in reasons)


def test_audit_limited_reasons_include_user_limits_even_when_coverage_is_full():
    args = types.SimpleNamespace(
        no_mineru=False,
        no_reference_online=False,
        reference_online_limit=10,
        image_audit_limit=10,
        no_image_semantic=False,
        image_semantic_limit=10,
        no_image_detector=False,
        image_detector_limit=10,
        llm_cache_only=False,
    )
    meta = {
        "reference_count": 2,
        "reference_audit": {"reference_count": 2, "online_checked": 2},
        "image_audit": {"image_count": 2, "semantic_checked": 2, "detector_checked": 2},
    }

    reasons = paper_audit.audit_limited_reasons(args, meta)

    assert any("参考文献在线核验上限" in reason for reason in reasons)
    assert any("图像审查上限" in reason for reason in reasons)
    assert any("图像语义分析上限" in reason for reason in reasons)
    assert any("imagedetector检测上限" in reason for reason in reasons)


def test_coverage_blocking_failure_detects_service_wide_reference_error():
    meta = {
        "reference_audit": {
            "reference_count": 2,
            "online_enabled": True,
            "online_checked": 2,
            "references": [
                {"online": {"online_status": "error"}},
                {"online": {"online_status": "error"}},
            ],
        }
    }

    capability, message, details = paper_audit.coverage_blocking_failure(meta)

    assert capability == "reference_lookup"
    assert "全部失败" in message
    assert details["reference_count"] == 2


def test_coverage_blocking_failure_detects_service_wide_resource_error():
    meta = {
        "resource_audit": {
            "resource_count": 2,
            "online_enabled": True,
            "online_checked": 2,
            "resources": [
                {"availability": {"status": "error"}},
                {"availability": {"status": "error"}},
            ],
        }
    }

    capability, message, details = paper_audit.coverage_blocking_failure(meta)

    assert capability == "resource_availability"
    assert "全部失败" in message
    assert details["resource_count"] == 2


def test_coverage_blocking_failure_detects_service_wide_image_detector_error():
    meta = {
        "image_audit": {
            "image_count": 2,
            "detector_enabled": True,
            "detector_checked": 2,
            "images": [
                {"detector": {"status": "error"}},
                {"detector": {"status": "error"}},
            ],
        }
    }

    capability, message, details = paper_audit.coverage_blocking_failure(meta)

    assert capability == "image_detector"
    assert "全部失败" in message
    assert details["image_count"] == 2


def test_report_headers_state_complete_or_limited(tmp_path):
    stat = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }
    report = {"summary": "ok", "risk_level": "低", "detection_score": 0, "checks": [], "conclusion": "ok"}

    complete = paper_audit.format_report(report, tmp_path / "paper.pdf", {"artifact_type": "complete"}, stat)
    limited = paper_audit.format_report(
        report,
        tmp_path / "paper.pdf",
        {"artifact_type": "limited", "limited_reasons": ["用户关闭参考文献在线核验。"]},
        stat,
    )

    assert "**产物类型**: 完整审查 (complete)" in complete
    assert "**产物类型**: 范围受限审查 (limited)" in limited
    assert "用户关闭参考文献在线核验" in limited


def test_reports_include_review_overview_and_internal_evidence_links(tmp_path):
    stat = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }
    report = {
        "summary": "needs review",
        "risk_level": "中",
        "detection_score": 62,
        "score_breakdown": {"red_flags": 1, "evidence_warnings": 1, "extraction_warnings": 0},
        "checks": [
            {
                "category": "数据与结果",
                "item": "样本量",
                "verdict": "⚠️可疑",
                "source_text": "Methods n=42, Results n=24",
                "reason": "样本量前后不一致",
            }
        ],
        "conclusion": "manual review required",
    }
    meta = {
        "artifact_type": "complete",
        "artifact_paths": {
            "markdown": str(tmp_path / "paper.audit.md"),
            "html": str(tmp_path / "paper.audit.html"),
            "json": str(tmp_path / "paper.audit.json"),
        },
    }

    markdown = paper_audit.format_report(report, tmp_path / "paper.pdf", meta, stat)
    html = paper_audit.format_html_report(report, tmp_path / "paper.pdf", meta, stat)

    assert "## 复核概览" in markdown
    assert "| 报告类型 | 完整审查 (complete) |" in markdown
    assert "[数据与结果 / 样本量](#check-1)" in markdown
    assert 'id="review-overview"' in html
    assert 'href="#check-1"' in html
    assert 'id="check-1"' in html


def test_limited_report_includes_limitation_panel(tmp_path):
    stat = {
        "benford_deviation": None,
        "benford_status": None,
        "p_value_count": 0,
        "p_value_abnormal": 0,
        "sd_count": 0,
        "number_count": 0,
    }
    report = {"summary": "ok", "risk_level": "低", "detection_score": 0, "checks": [], "conclusion": "ok"}
    meta = {
        "artifact_type": "limited",
        "limited_reasons": ["用户关闭参考文献在线核验。"],
        "reference_audit": {"status": "skipped"},
    }

    markdown = paper_audit.format_report(report, tmp_path / "paper.pdf", meta, stat)
    html = paper_audit.format_html_report(report, tmp_path / "paper.pdf", meta, stat)

    assert "### 范围限制面板" in markdown
    assert "用户关闭参考文献在线核验" in markdown
    assert 'id="limitation-panel"' in html
    assert "已完成审查" in html


def test_failed_audit_markdown_includes_required_diagnostics(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="mineru",
        error_class="missing_required_config",
        message="MINERU_TOKEN is missing",
        fix_hints=["在 config.py 中配置 MINERU_TOKEN", "确认 MinerU 网络可达"],
        completed_stages=["runtime_config_loaded"],
        retry_command="python paper_audit.py sample.pdf --json",
        details={"field": "MINERU_TOKEN"},
        created_at="2026-05-28 12:00:00",
    )

    rendered = paper_audit.format_failed_audit_markdown(failure, tmp_path / "sample.pdf")

    assert "未生成完整审查报告" in rendered
    assert "## 失败恢复面板" in rendered
    assert "**完整审查报告已生成**: 否" in rendered
    assert "`mineru`" in rendered
    assert "`missing_required_config`" in rendered
    assert "在 config.py 中配置 MINERU_TOKEN" in rendered
    assert "runtime_config_loaded" in rendered
    assert "python paper_audit.py sample.pdf --json" in rendered
    assert '"field": "MINERU_TOKEN"' in rendered


def test_failed_audit_html_uses_recovery_panel_without_risk_overview(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="input_extraction",
        error_class="missing_optional_dependency",
        message="读取 .docx 文件需要安装可选依赖 python-docx。",
        fix_hints=["运行 `python3 -m pip install python-docx` 后重试。"],
        completed_stages=["init"],
        retry_command="python paper_audit.py paper.docx --json",
        details={"resume_dir": str(tmp_path / ".paper.paper_audit_resume")},
        created_at="2026-05-28 12:00:00",
    )

    rendered = paper_audit.format_failed_audit_html(failure, tmp_path / "paper.docx")

    assert "失败恢复面板" in rendered
    assert 'id="failed-diagnostics"' in rendered
    assert "python3 -m pip install python-docx" in rendered
    assert "复核优先级" not in rendered
    assert "证据风险分" not in rendered


def test_failed_audit_payload_serializes_stable_shape(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="text_llm",
        error_class="provider_unavailable",
        message="LLM provider timed out",
        fix_hints=["检查第三方服务状态后重试"],
        completed_stages=["mineru_extract_complete"],
        retry_command="python paper_audit.py paper.pdf --json",
        created_at="2026-05-28 12:00:00",
    )

    payload = paper_audit.failed_audit_payload(failure, tmp_path / "paper.pdf", meta={"run_id": "abc"})

    assert payload["report_type"] == "failed"
    assert payload["complete_report_generated"] is False
    assert payload["failure"]["capability"] == "text_llm"
    assert payload["failure"]["error_class"] == "provider_unavailable"
    assert payload["failure"]["fix_hints"] == ["检查第三方服务状态后重试"]
    assert payload["failure"]["completed_stages"] == ["mineru_extract_complete"]
    assert payload["failure"]["retry_command"] == "python paper_audit.py paper.pdf --json"
    assert payload["meta"]["run_id"] == "abc"
    assert payload["meta"]["runtime"]["future_year_basis"] == "utc_year"
    assert json.loads(json.dumps(payload, ensure_ascii=False))["report_type"] == "failed"


def test_failed_audit_payload_promotes_completed_audits(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="image_semantic",
        error_class="provider_unavailable",
        message="image semantic provider failed",
        created_at="2026-05-28 12:00:00",
    )
    reference_audit = {"reference_count": 2, "online_checked": 2, "references": []}
    resource_audit = {"resource_count": 1, "online_checked": 1, "resources": []}

    payload = paper_audit.failed_audit_payload(
        failure,
        tmp_path / "paper.pdf",
        meta={"reference_audit": reference_audit, "resource_audit": resource_audit},
    )

    assert payload["reference_audit"] == reference_audit
    assert payload["resource_audit"] == resource_audit


def test_failed_audit_markdown_includes_completed_audit_sections(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="image_semantic",
        error_class="provider_unavailable",
        message="image semantic provider failed",
        created_at="2026-05-28 12:00:00",
    )
    meta = {
        "reference_audit": {
            "status": "ok",
            "reference_count": 2,
            "doi_count": 1,
            "year_count": 2,
            "online_enabled": True,
            "online_checked": 2,
            "issues": [],
            "references": [],
        },
        "resource_audit": {
            "status": "needs_review",
            "resource_count": 1,
            "online_enabled": True,
            "online_checked": 1,
            "resources": [
                {
                    "type": "code_repository",
                    "url": "https://github.com/example/repo",
                    "availability": {"status": "available"},
                    "context": "Code available at https://github.com/example/repo",
                }
            ],
            "issues": [],
        },
    }

    rendered = paper_audit.format_failed_audit_markdown(failure, tmp_path / "paper.pdf", meta=meta)

    assert "已完成校检摘要" in rendered
    assert "参考文献真实性/可核验性校检" in rendered
    assert "代码仓库与在线资源可用性校检" in rendered
    assert "https://github.com/example/repo" in rendered


def test_save_failed_audit_diagnostics_writes_md_and_json(tmp_path):
    failure = paper_audit.AuditFailure(
        capability="image_semantic",
        error_class="provider_auth_failed",
        message="image semantic provider rejected the request",
        fix_hints=["检查图像语义分析服务 API Key"],
        completed_stages=["reference_audit_complete"],
        retry_command="python paper_audit.py input.pdf --json",
        created_at="2026-05-28 12:00:00",
    )
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4")

    md_path, json_path = paper_audit.save_failed_audit_diagnostics(failure, input_pdf)

    assert md_path == tmp_path / "input.failed.md"
    assert json_path == tmp_path / "input.failed.json"
    assert (tmp_path / "input.failed.html").exists()
    assert "未生成完整审查报告" in md_path.read_text(encoding="utf-8")
    assert "断点续跑命令" in (tmp_path / "input.failed.html").read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report_type"] == "failed"
    assert payload["complete_report_generated"] is False
    assert payload["failure"]["capability"] == "image_semantic"


def test_find_project_files_skips_generated_outputs(tmp_path):
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "paper_reference.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "audit_report.audit.md").write_text("generated", encoding="utf-8")
    (tmp_path / "audit_report.failed.md").write_text("generated", encoding="utf-8")
    (tmp_path / "reference_audit_full.md").write_text("generated", encoding="utf-8")
    (tmp_path / "reference_audit_full.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sample.paper_audit.log").write_text("log", encoding="utf-8")
    (tmp_path / "paper.abc123.mineru_url.txt").write_text("https://example.invalid/mineru.zip", encoding="utf-8")
    (tmp_path / "paper.abc123.mineru.zip").write_bytes(b"zip")
    resume_dir = tmp_path / ".tmp.paper_audit_resume"
    resume_dir.mkdir()
    (resume_dir / "cached.md").write_text("cached", encoding="utf-8")

    categories, files = paper_audit.find_project_files(Path(tmp_path))

    assert [p.name for p in files] == ["paper.pdf", "paper_reference.pdf"]
    assert categories["main_paper"].name == "paper.pdf"
    assert not categories["references"]
    assert [p.name for p in categories["other"]] == ["paper_reference.pdf"]


def test_render_evidence_html_converts_markdown_table():
    source = "| A | B |\n| --- | --- |\n| 1 | 2 |"

    rendered = paper_audit.render_evidence_html(source)

    assert '<table class="data-table">' in rendered
    assert "<th>A</th>" in rendered
    assert "<td>1</td>" in rendered


def test_render_evidence_html_hides_mineru_markers():
    source = "\n".join([
        "[[TABLE_START page=1 id=1]]",
        "[[EXTRACTION_NOTE]] table noise [[/EXTRACTION_NOTE]]",
        "| A | B |",
        "| --- | --- |",
        "| 1 | 2 |",
        "[[TABLE_END]]",
    ])

    rendered = paper_audit.render_evidence_html(source)

    assert "[[TABLE_START" not in rendered
    assert "EXTRACTION_NOTE" not in rendered
    assert '<table class="data-table">' in rendered


def test_render_evidence_html_handles_unclosed_mineru_table_marker():
    source = "[[TABLE_START page=5 id=4]]\n| A | B |\n| --- | --- |\n| 1 | 2 |"

    rendered = paper_audit.render_evidence_html(source)

    assert "[[TABLE_START" not in rendered
    assert '<table class="data-table">' in rendered


def test_render_evidence_html_converts_escaped_html_cells():
    source = "&lt;tr&gt;&lt;td&gt;Dose&lt;/td&gt;&lt;td&gt;10&lt;/td&gt;&lt;/tr&gt;"

    rendered = paper_audit.render_evidence_html(source)

    assert '<table class="data-table">' in rendered
    assert "&lt;td&gt;" not in rendered
    assert "<td>Dose</td>" in rendered


def test_render_evidence_html_collapses_large_tables():
    rows = ["| A | B |", "| --- | --- |"] + [f"| {i} | {i * 2} |" for i in range(20)]

    rendered = paper_audit.render_evidence_html("\n".join(rows))

    assert '<details class="data-table-details">' in rendered
    assert "查看完整表格" in rendered


def test_render_evidence_html_escapes_plain_text():
    rendered = paper_audit.render_evidence_html("plain <script>alert(1)</script>")

    assert "&lt;script&gt;" in rendered
    assert "<script>" not in rendered


def test_render_evidence_summary_strips_escaped_html_cells():
    summary = paper_audit.render_evidence_summary_html("&lt;tr&gt;&lt;td&gt;Dose&lt;/td&gt;&lt;td&gt;10&lt;/td&gt;&lt;/tr&gt;")

    assert "含表格" in summary
    assert "&lt;td&gt;" not in summary
    assert "Dose 10" in summary


def test_check_reason_sanitizes_nested_json_and_table_markup():
    check = {
        "detail": '{"summary":"ok","checks":[{"reason":"[[TABLE_START page=1]] <td>noise</td> 需人工核对原PDF。"}]}'
    }

    reason = paper_audit._check_reason(check)

    assert "[[TABLE_START" not in reason
    assert "<td>" not in reason
    assert "表格原文已在证据区渲染" in reason


def test_format_html_report_sorts_checks_and_uses_collapsible_details():
    report = {
        "summary": "ok",
        "risk_level": "中",
        "detection_score": 50,
        "score_breakdown": {"red_flags": 1, "evidence_warnings": 1, "extraction_warnings": 0, "stat_adjustments": []},
        "checks": [
            {"category": "B", "item": "minor", "verdict": "⚠️疑点", "source_text": "minor", "detail": "minor reason"},
            {"category": "A", "item": "major", "verdict": "🚩红旗", "source_text": "| A | B |\n| --- | --- |\n| 1 | 2 |", "detail": "major reason"},
        ],
        "conclusion": "done",
    }
    stat = {
        "benford_deviation": 0,
        "benford_status": None,
        "p_value_abnormal": 0,
        "p_value_count": 0,
        "sd_count": 0,
        "number_count": 0,
    }

    rendered = paper_audit.format_html_report(report, "paper.pdf", {}, stat)

    assert rendered.index("major") < rendered.index("minor")
    assert '<details class="detail-card"' in rendered
    assert "Paper Audit / Veritas" in rendered
    assert "score-panel" in rendered
    assert "查看详情" in rendered
    assert "含表格，见下方逐条详细分析" in rendered
    assert "[[TABLE_START" not in rendered
    assert "生成 PubPeer Comment" in rendered
    assert "生成期刊 Letter" in rendered
    assert 'id="draft-language"' in rendered
    assert "English" in rendered
    assert "paper-audit-action-context" in rendered
    assert "127.0.0.1:8765" in rendered
    assert "--serve-report-actions" in rendered
    assert 'id="followup-title"' in rendered
    assert 'id="draft-tone"' in rendered
    assert 'id="followup-evidence-list"' in rendered
    assert 'id="manual-review-confirmation"' in rendered
    assert "http://127.0.0.1:8765/followups" in rendered
    assert "证据型疑点 1" in rendered


def test_web_action_panel_uses_report_action_port():
    rendered = paper_audit.format_web_action_panel_html(
        {"summary": "ok", "risk_level": "中", "detection_score": 50, "checks": [], "conclusion": "done"},
        "paper.pdf",
        {"report_actions": {"host": "127.0.0.1", "port": 9123}},
        {"number_count": 0},
    )

    assert "http://127.0.0.1:9123" in rendered
    assert "http://127.0.0.1:9123/generate" in rendered
    assert "http://127.0.0.1:9123/followups" in rendered
    assert "127.0.0.1:8765" not in rendered


def test_web_action_context_script_contains_parseable_json():
    rendered = paper_audit.format_web_action_panel_html(
        {
            "summary": "quoted \" summary",
            "risk_level": "中",
            "detection_score": 50,
            "checks": [],
            "conclusion": "safe </script><script>alert(1)</script>",
        },
        "paper.pdf",
        {"report_actions": {"host": "127.0.0.1", "port": 9123}},
        {"number_count": 0},
    )
    marker = '<script id="paper-audit-action-context" type="application/json">'
    context_text = rendered.split(marker, 1)[1].split("</script>", 1)[0]

    context = json.loads(context_text)

    assert context["paper"] == "paper.pdf"
    assert context["summary"] == 'quoted " summary'
    assert context["conclusion"] == "safe </script><script>alert(1)</script>"
    assert "&quot;" not in context_text
    assert "</script>" not in context_text.lower()


def test_ensure_report_action_service_reuses_existing(monkeypatch, tmp_path):
    popen_calls = []
    monkeypatch.setattr(
        paper_audit,
        "report_action_service_health",
        lambda **kwargs: {"ok": True, "model": "configured-model"},
    )
    monkeypatch.setattr(paper_audit.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))

    result = paper_audit.ensure_report_action_service(port=9001, log_path=tmp_path / "report_actions.log")

    assert result["ok"] is True
    assert result["status"] == "already_running"
    assert result["url"] == "http://127.0.0.1:9001"
    assert popen_calls == []


def test_ensure_report_action_service_starts_background_process(monkeypatch, tmp_path):
    health_calls = []
    popen_calls = []

    def fake_health(**kwargs):
        health_calls.append(kwargs)
        return {"ok": True, "model": "configured-model"} if len(health_calls) >= 2 else None

    class DummyProcess:
        pid = 4321
        returncode = None

        def poll(self):
            return None

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return DummyProcess()

    monkeypatch.setattr(paper_audit, "report_action_service_health", fake_health)
    monkeypatch.setattr(paper_audit.subprocess, "Popen", fake_popen)

    result = paper_audit.ensure_report_action_service(port=9002, log_path=tmp_path / "report_actions.log", startup_timeout=0.2)

    assert result["ok"] is True
    assert result["status"] == "started"
    assert result["pid"] == 4321
    command = popen_calls[0][0][0]
    assert command[:2] == [sys.executable, str(paper_audit.Path(__file__).resolve().parents[1] / "paper_audit.py")]
    assert "--serve-report-actions" in command
    assert "--report-actions-port" in command
    assert "9002" in command
    assert popen_calls[0][1]["stdin"] == subprocess.DEVNULL
    assert popen_calls[0][1]["start_new_session"] is True


def _wait_for_test(predicate, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_web_runner_page_contains_workbench_controls():
    rendered = paper_audit.render_web_runner_page()

    assert "Veritas Web Runner" in rendered
    assert 'id="inputDropZone"' in rendered
    assert 'id="inputPath"' in rendered
    assert 'id="pickFileBtn"' in rendered
    assert 'id="pickDirectoryBtn"' in rendered
    assert 'id="outputPath"' in rendered
    assert 'id="pickOutputBtn"' in rendered
    assert 'id="inputPath" type="text" autocomplete="off" readonly' in rendered
    assert 'id="outputPath" type="text" autocomplete="off" readonly' in rendered
    assert 'id="fresh"' in rendered
    assert 'id="startBtn"' in rendered
    assert 'id="cancelBtn"' in rendered
    assert 'id="currentOutput"' in rendered
    assert 'id="runFeedback"' in rendered
    assert 'id="reportPanel"' in rendered
    assert 'id="reportState"' in rendered
    assert 'id="reportType"' in rendered
    assert 'id="reportRisk"' in rendered
    assert 'id="reportFolder"' in rendered
    assert 'id="reportSummary"' in rendered
    assert 'id="currentActions"' in rendered
    assert 'id="log"' in rendered
    assert 'id="runs"' in rendered
    assert "droppedPathFromDataTransfer" in rendered
    assert "droppedPathFromTransferText" in rendered
    assert "droppedPathFromUriText" in rendered
    assert "localPathFromFileUri" in rendered
    assert "text/uri-list" in rendered
    assert "file://" in rendered
    assert "applyDroppedPath" in rendered
    assert "defaultOutputStemForInput" in rendered
    assert "renderCurrentRun" in rendered
    assert "renderReportPanel" in rendered
    assert "reportSummaryFallback" in rendered
    assert "setFeedback" in rendered
    assert "startPayloadFromForm" in rendered
    assert "dataset.userSelected === 'true'" in rendered
    assert "currentArtifactActions" in rendered
    assert "retryRun" in rendered
    assert "startRunWithPayload" in rendered
    assert "escapeHtml" in rendered
    assert "/api/pick-path" in rendered
    assert "webkitGetAsEntry" in rendered
    assert "event.preventDefault()" in rendered


def test_web_runner_default_output_stem_uses_input_parent_and_timestamp(tmp_path):
    input_path = tmp_path / "Project Alpha" / "paper.v1.pdf"

    output = paper_audit.web_runner_default_output_stem(input_path, timestamp="20260605-153000")

    assert output == str(tmp_path / "Project Alpha" / "paper.v1_20260605-153000" / "audit_report")


def test_pick_local_path_uses_dialog_runner_without_browsing_http(tmp_path):
    selected = tmp_path / "paper.pdf"

    result = paper_audit.pick_local_path("input_file", dialog_runner=lambda mode: selected)
    unsupported = paper_audit.pick_local_path("unsupported", dialog_runner=lambda mode: selected)
    canceled = paper_audit.pick_local_path("output_directory", dialog_runner=lambda mode: "")

    assert result == {"ok": True, "mode": "input_file", "path": str(selected)}
    assert unsupported["error"] == "unsupported_picker_mode"
    assert canceled["error"] == "canceled"


def test_dropped_local_path_from_uri_text_prefers_file_uri():
    payload = "# comment\nfile:///home/haozhao/2026-040896_%E7%A8%BF%E4%BB%B6%E5%85%A8%E6%96%87C.docx\nhttps://example.test/file.docx"

    resolved = paper_audit.dropped_local_path_from_uri_text(payload)
    ignored = paper_audit.dropped_local_path_from_uri_text("https://example.test/file.docx\nplain-name.docx")

    assert resolved == "/home/haozhao/2026-040896_稿件全文C.docx"
    assert ignored == ""


def test_resolve_web_runner_input_path_finds_unique_basename(tmp_path):
    project_dir = tmp_path / "Documents" / "Project"
    project_dir.mkdir(parents=True)
    paper_path = project_dir / "paper.docx"
    paper_path.write_text("paper", encoding="utf-8")

    resolved = paper_audit.resolve_web_runner_input_path("paper.docx", search_roots=[tmp_path])

    assert resolved["ok"] is True
    assert resolved["path"] == str(paper_path.resolve())
    assert resolved["resolved_from"] == "paper.docx"


def test_resolve_web_runner_input_path_rejects_missing_basename(tmp_path):
    resolved = paper_audit.resolve_web_runner_input_path("missing.docx", search_roots=[tmp_path])

    assert resolved["ok"] is False
    assert resolved["error"] == "input_path_not_found"


def test_resolve_web_runner_input_path_rejects_ambiguous_basename(tmp_path):
    first = tmp_path / "Downloads" / "paper.docx"
    second = tmp_path / "Documents" / "paper.docx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    resolved = paper_audit.resolve_web_runner_input_path("paper.docx", search_roots=[tmp_path])

    assert resolved["ok"] is False
    assert resolved["error"] == "ambiguous_input_path"
    assert sorted(Path(item).parent.name for item in resolved["candidates"]) == ["Documents", "Downloads"]


def test_resolve_web_runner_input_path_preserves_explicit_missing_path(tmp_path):
    explicit = tmp_path / "missing" / "paper.docx"

    resolved = paper_audit.resolve_web_runner_input_path(str(explicit), search_roots=[tmp_path])

    assert resolved == {"ok": True, "path": str(explicit)}


def test_resolve_web_runner_input_path_preserves_dot_slash_missing_path(tmp_path, monkeypatch):
    other = tmp_path / "Downloads" / "paper.docx"
    other.parent.mkdir(parents=True)
    other.write_text("paper", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    resolved = paper_audit.resolve_web_runner_input_path("./paper.docx", search_roots=[tmp_path])

    assert resolved == {"ok": True, "path": str(Path("./paper.docx"))}


def test_resolve_web_runner_input_path_matches_literal_basename_with_brackets(tmp_path):
    paper_path = tmp_path / "nested" / "paper[1].docx"
    paper_path.parent.mkdir(parents=True)
    paper_path.write_text("paper", encoding="utf-8")

    resolved = paper_audit.resolve_web_runner_input_path("paper[1].docx", search_roots=[tmp_path])

    assert resolved["ok"] is True
    assert resolved["path"] == str(paper_path.resolve())
    assert resolved["resolved_from"] == "paper[1].docx"


def test_resolve_web_runner_input_path_does_not_treat_question_mark_as_glob(tmp_path):
    wildcard_name = tmp_path / "nested" / "paper?.docx"
    plain_name = tmp_path / "nested" / "paper1.docx"
    wildcard_name.parent.mkdir(parents=True)
    wildcard_name.write_text("wild", encoding="utf-8")
    plain_name.write_text("plain", encoding="utf-8")

    resolved = paper_audit.resolve_web_runner_input_path("paper?.docx", search_roots=[tmp_path])

    assert resolved["ok"] is True
    assert resolved["path"] == str(wildcard_name.resolve())
    assert resolved["resolved_from"] == "paper?.docx"


def test_resolve_web_runner_input_path_does_not_match_glob_pattern_to_different_name(tmp_path):
    plain_name = tmp_path / "nested" / "paper1.docx"
    plain_name.parent.mkdir(parents=True)
    plain_name.write_text("plain", encoding="utf-8")

    resolved = paper_audit.resolve_web_runner_input_path("paper?.docx", search_roots=[tmp_path])

    assert resolved["ok"] is False
    assert resolved["error"] == "input_path_not_found"


def test_web_runner_common_search_roots_keeps_home_nonrecursive(tmp_path):
    home = tmp_path / "home"
    cwd = tmp_path / "repo"
    nested_home = home / "unlisted" / "paper.docx"
    desktop_file = home / "Desktop" / "paper.docx"
    cwd_file = cwd / "deep" / "paper.docx"
    nested_home.parent.mkdir(parents=True)
    desktop_file.parent.mkdir(parents=True)
    cwd_file.parent.mkdir(parents=True)
    nested_home.write_text("home", encoding="utf-8")
    desktop_file.write_text("desktop", encoding="utf-8")
    cwd_file.write_text("cwd", encoding="utf-8")

    roots = paper_audit._web_runner_common_search_roots(cwd=cwd, home=home)
    resolved = paper_audit.resolve_web_runner_input_path("paper.docx", search_roots=roots)

    assert resolved["ok"] is False
    assert resolved["error"] == "ambiguous_input_path"
    assert sorted(Path(item).parent.name for item in resolved["candidates"]) == ["Desktop", "deep"]
    assert str(nested_home) not in resolved["candidates"]


def test_web_runner_config_status_does_not_expose_api_keys(monkeypatch):
    cfg = paper_audit.default_runtime_config()
    cfg.text_llm.api_key = "secret-llm-key"
    cfg.mineru.api_key = "secret-mineru-key"
    cfg.image_semantic.api_key = "secret-vision-key"
    monkeypatch.setattr(paper_audit, "load_runtime_config", lambda verbose=False: cfg)

    status = paper_audit.web_runner_config_status()
    rendered = json.dumps(status, ensure_ascii=False)

    assert status["capabilities"]["text_llm"]["api_key_configured"] is True
    assert "secret-llm-key" not in rendered
    assert "secret-mineru-key" not in rendered
    assert "secret-vision-key" not in rendered


def test_web_runner_cors_headers_preserve_report_action_compatibility():
    headers = paper_audit.web_runner_cors_headers()

    assert headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in headers["Access-Control-Allow-Methods"]
    assert headers["Access-Control-Allow-Headers"] == "Content-Type"


def test_web_runner_start_run_spawns_existing_cli(monkeypatch, tmp_path):
    input_path = tmp_path / "paper.pdf"
    input_path.write_text("paper", encoding="utf-8")
    popen_calls = []

    class DummyProcess:
        pid = 2468

        def __init__(self):
            self.stdout = io.StringIO("line one\nline two\n")
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return DummyProcess()

    monkeypatch.setattr(paper_audit.subprocess, "Popen", fake_popen)
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    response, status = state.start_run(str(input_path), output=str(tmp_path / "out"), fresh=True)

    assert status == 200
    run_id = response["run"]["id"]
    command = popen_calls[0][0][0]
    assert command[:3] == [sys.executable, str(paper_audit.Path(__file__).resolve().parents[1] / "paper_audit.py"), str(input_path)]
    assert "--json" in command
    assert "--no-open" in command
    assert "-o" in command
    assert str(tmp_path / "out") in command
    assert "--fresh" in command
    assert popen_calls[0][1]["stdin"] == subprocess.DEVNULL
    assert popen_calls[0][1]["stderr"] == subprocess.STDOUT
    _wait_for_test(lambda: state.get_run(run_id)["status"] == "succeeded")
    logs = state.logs_since(run_id, 0)
    assert logs["lines"] == ["line one", "line two"]


def test_web_runner_start_run_defaults_output_stem(monkeypatch, tmp_path):
    input_path = tmp_path / "Project Alpha"
    input_path.mkdir()
    popen_calls = []

    class DummyProcess:
        pid = 2469

        def __init__(self):
            self.stdout = io.StringIO("")
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(paper_audit, "_web_runner_timestamp", lambda: "20260605-153000")
    monkeypatch.setattr(paper_audit.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)) or DummyProcess())
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    response, status = state.start_run(str(input_path))

    expected_output = str(tmp_path / "Project Alpha_20260605-153000" / "audit_report")
    assert status == 200
    assert response["run"]["output"] == expected_output
    command = popen_calls[0][0][0]
    assert "-o" in command
    assert expected_output in command
    assert (tmp_path / "Project Alpha_20260605-153000").is_dir()


def test_web_runner_start_run_resolves_basename_before_spawning(monkeypatch, tmp_path):
    search_root = tmp_path / "Downloads"
    search_root.mkdir()
    input_path = search_root / "paper.docx"
    input_path.write_text("paper", encoding="utf-8")
    popen_calls = []

    class DummyProcess:
        pid = 2470

        def __init__(self):
            self.stdout = io.StringIO("")
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(paper_audit, "_web_runner_common_search_roots", lambda: [tmp_path])
    monkeypatch.setattr(paper_audit, "_web_runner_timestamp", lambda: "20260605-153000")
    monkeypatch.setattr(paper_audit.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)) or DummyProcess())
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    response, status = state.start_run("paper.docx")

    expected_output = str(search_root / "paper_20260605-153000" / "audit_report")
    assert status == 200
    assert response["run"]["input_path"] == str(input_path.resolve())
    assert response["run"]["output"] == expected_output
    command = popen_calls[0][0][0]
    assert command[:3] == [sys.executable, str(paper_audit.Path(__file__).resolve().parents[1] / "paper_audit.py"), str(input_path.resolve())]
    assert expected_output in command


def test_web_runner_start_run_rejects_unresolved_basename_without_spawning(monkeypatch, tmp_path):
    popen_calls = []

    monkeypatch.setattr(paper_audit, "_web_runner_common_search_roots", lambda: [tmp_path])
    monkeypatch.setattr(paper_audit.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    response, status = state.start_run("missing.docx")

    assert status == 400
    assert response["error"] == "input_path_not_found"
    assert popen_calls == []


def test_web_runner_start_run_rejects_ambiguous_basename_without_spawning(monkeypatch, tmp_path):
    first = tmp_path / "one" / "paper.docx"
    second = tmp_path / "two" / "paper.docx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    popen_calls = []

    monkeypatch.setattr(paper_audit, "_web_runner_common_search_roots", lambda: [tmp_path])
    monkeypatch.setattr(paper_audit.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    response, status = state.start_run("paper.docx")

    assert status == 409
    assert response["error"] == "ambiguous_input_path"
    assert len(response["candidates"]) == 2
    assert popen_calls == []


def test_web_runner_rejects_second_active_run_and_can_cancel(monkeypatch, tmp_path):
    input_path = tmp_path / "paper.pdf"
    input_path.write_text("paper", encoding="utf-8")
    processes = []

    class HangingProcess:
        pid = 1357

        def __init__(self):
            self.stdout = None
            self.returncode = None
            self.terminated = False
            self.done = threading.Event()

        def wait(self, timeout=None):
            if timeout is None:
                self.done.wait(1)
            elif not self.done.wait(timeout):
                raise subprocess.TimeoutExpired("paper_audit.py", timeout)
            if self.returncode is None:
                self.returncode = -15 if self.terminated else 0
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.done.set()

        def kill(self):
            self.returncode = -9
            self.done.set()

    def fake_popen(*args, **kwargs):
        process = HangingProcess()
        processes.append(process)
        return process

    monkeypatch.setattr(paper_audit.subprocess, "Popen", fake_popen)
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")

    first, first_status = state.start_run(str(input_path))
    second, second_status = state.start_run(str(input_path))

    assert first_status == 200
    assert second_status == 409
    assert second["error"] == "busy"
    cancel_response, cancel_status = state.cancel_run(first["run"]["id"])
    assert cancel_status == 200
    assert cancel_response["ok"] is True
    assert processes[0].terminated is True
    _wait_for_test(lambda: state.get_run(first["run"]["id"])["status"] == "canceled")
    assert "断点续作缓存" in state.get_run(first["run"]["id"])["message"]


def test_web_runner_artifact_targets_are_recorded_allowlist_only(tmp_path):
    input_path = tmp_path / "paper.pdf"
    input_path.write_text("paper", encoding="utf-8")
    html_path = tmp_path / "paper.audit.html"
    md_path = tmp_path / "paper.audit.md"
    json_path = tmp_path / "paper.audit.json"
    secret_path = tmp_path / "secret.txt"
    html_path.write_text("<html>report</html>", encoding="utf-8")
    md_path.write_text("# report", encoding="utf-8")
    json_path.write_text(
        json.dumps({"report_type": "complete", "llm_report": {"summary": "ok", "risk_level": "低"}}),
        encoding="utf-8",
    )
    secret_path.write_text("secret", encoding="utf-8")
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")
    state.runs["run-1"] = {
        "id": "run-1",
        "input_path": str(input_path),
        "output": "",
        "status": "succeeded",
        "started_at": "2026-06-05T00:00:00",
        "logs": [],
        "artifacts": {},
    }

    run = state.discover_artifacts("run-1")
    html_target, html_error = state.artifact_target("run-1", "html")
    unknown_target, unknown_error = state.artifact_target("run-1", "secret")

    assert run["report_type"] == "complete"
    assert run["summary"]["summary"] == "ok"
    assert run["summary"]["risk_level"] == "低"
    assert run["summary"]["report_type"] == "complete"
    assert html_error == ""
    assert html_target == html_path.resolve()
    assert unknown_target is None
    assert unknown_error == "unknown_artifact"
    assert str(secret_path.resolve()) not in json.dumps(run, ensure_ascii=False)


def test_web_runner_limited_artifact_summary_is_exposed(tmp_path):
    input_path = tmp_path / "paper.pdf"
    input_path.write_text("paper", encoding="utf-8")
    html_path = tmp_path / "paper.limited.html"
    md_path = tmp_path / "paper.limited.md"
    json_path = tmp_path / "paper.limited.json"
    html_path.write_text("<html>limited</html>", encoding="utf-8")
    md_path.write_text("# limited", encoding="utf-8")
    json_path.write_text(
        json.dumps({"report_type": "limited", "llm_report": {"summary": "scope limited", "risk_level": "中"}}),
        encoding="utf-8",
    )
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")
    state.runs["run-1"] = {
        "id": "run-1",
        "input_path": str(input_path),
        "output": "",
        "status": "succeeded",
        "started_at": "2026-06-05T00:00:00",
        "logs": [],
        "artifacts": {},
    }

    run = state.discover_artifacts("run-1")

    assert run["report_type"] == "limited"
    assert run["artifacts"]["html"] == str(html_path.resolve())
    assert run["artifacts"]["markdown"] == str(md_path.resolve())
    assert run["summary"]["summary"] == "scope limited"
    assert run["summary"]["risk_level"] == "中"
    assert run["summary"]["report_type"] == "limited"


def test_web_runner_failed_artifact_summary_is_exposed(tmp_path):
    input_path = tmp_path / "paper.pdf"
    input_path.write_text("paper", encoding="utf-8")
    html_path = tmp_path / "paper.failed.html"
    md_path = tmp_path / "paper.failed.md"
    json_path = tmp_path / "paper.failed.json"
    html_path.write_text("<html>failed</html>", encoding="utf-8")
    md_path.write_text("# failed", encoding="utf-8")
    json_path.write_text(
        json.dumps({
            "report_type": "failed",
            "complete_report_generated": False,
            "failure": {
                "capability": "text_llm",
                "error_class": "missing_required_config",
                "message": "缺少LLM配置",
                "fix_hints": ["配置API key"],
                "completed_stages": ["stage1_extract"],
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    state = paper_audit.WebRunnerState(history_path=tmp_path / "runs.json")
    state.runs["run-1"] = {
        "id": "run-1",
        "input_path": str(input_path),
        "output": "",
        "status": "failed",
        "started_at": "2026-06-05T00:00:00",
        "logs": [],
        "artifacts": {},
    }

    run = state.discover_artifacts("run-1")

    assert run["report_type"] == "failed"
    assert run["artifacts"]["html"] == str(html_path.resolve())
    assert run["summary"]["report_type"] == "failed"
    assert run["summary"]["risk_level"] == "failed"
    assert run["summary"]["failure_capability"] == "text_llm"
    assert run["summary"]["failure_error"] == "missing_required_config"
    assert run["summary"]["summary"] == "缺少LLM配置"
    assert run["summary"]["complete_report_generated"] is False


def test_desktop_gui_start_run_reuses_web_runner_state():
    class FakeState:
        def __init__(self):
            self.calls = []

        def start_run(self, input_path, output=None, fresh=False):
            self.calls.append({"input_path": input_path, "output": output, "fresh": fresh})
            return {"ok": True, "run": {"id": "run-1"}}, 200

    state = FakeState()

    result, status = paper_audit.desktop_gui_start_run(state, "/tmp/paper.pdf", "", True)

    assert status == 200
    assert result["run"]["id"] == "run-1"
    assert state.calls == [{"input_path": "/tmp/paper.pdf", "output": None, "fresh": True}]


def test_desktop_gui_run_summary_exposes_report_outputs_without_extra_keys():
    run = {
        "status": "succeeded",
        "input_path": "/tmp/paper.pdf",
        "output": "/tmp/out/audit_report",
        "report_type": "complete",
        "message": "审查完成",
        "summary": {"report_type": "complete", "risk_level": "低", "summary": "ok"},
        "artifacts": {
            "html": "/tmp/out/audit_report.audit.html",
            "markdown": "/tmp/out/audit_report.audit.md",
            "json": "/tmp/out/audit_report.audit.json",
            "folder": "/tmp/out",
            "secret": "/tmp/secret.txt",
        },
    }

    summary = paper_audit.desktop_gui_run_summary(run)

    assert summary["status"] == "succeeded"
    assert summary["status_label"] == "已完成"
    assert summary["report_type"] == "complete"
    assert summary["report_type_label"] == "完整报告"
    assert summary["risk_level"] == "低"
    assert summary["risk_label"] == "低"
    assert summary["summary"] == "ok"
    assert summary["artifacts"] == {
        "html": "/tmp/out/audit_report.audit.html",
        "markdown": "/tmp/out/audit_report.audit.md",
        "json": "/tmp/out/audit_report.audit.json",
        "folder": "/tmp/out",
    }


def test_desktop_gui_run_summary_translates_failed_state_for_display():
    summary = paper_audit.desktop_gui_run_summary({
        "status": "failed",
        "message": "审查失败",
        "summary": {
            "report_type": "failed",
            "risk_level": "failed",
            "summary": "文本LLM认证失败，请检查LLM_API_KEY。",
        },
    })

    assert summary["status_label"] == "需处理"
    assert summary["report_type_label"] == "诊断报告"
    assert summary["risk_label"] == "暂无评分"
    assert summary["summary"] == "文本LLM认证失败，请检查LLM_API_KEY。"


def test_desktop_gui_progress_from_log_line_parses_stage_progress():
    progress = paper_audit.desktop_gui_progress_from_log_line("📊 [████░░] 2/5  40.0% 阶段2/5 本地统计检测完成")

    assert progress == {
        "current": 2,
        "total": 5,
        "percent": 40.0,
        "label": "阶段 2/5 · 本地统计完成",
    }
    assert paper_audit.desktop_gui_progress_from_log_line("普通日志") is None


def test_desktop_gui_config_snapshot_compacts_status_without_secrets():
    snapshot = paper_audit.desktop_gui_config_snapshot({
        "ok": False,
        "capabilities": {
            "text_llm": {"ok": True, "api_key_configured": True, "model": "private-model"},
            "mineru": {"ok": False, "missing": ["api_key"]},
            "image_semantic": {"ok": True},
            "reference_lookup": {"ok": True},
            "image_detector": {"ok": False, "missing": ["base_url"]},
        },
        "optional_dependencies": {"python_docx": True, "openpyxl": False},
    })

    assert snapshot["summary"] == "4/7 正常 · 待配置"
    assert snapshot["rows"] == [
        {"label": "LLM", "status": "正常", "ok": True},
        {"label": "MinerU", "status": "配置", "ok": False},
        {"label": "图像语义", "status": "正常", "ok": True},
        {"label": "参考核验", "status": "正常", "ok": True},
        {"label": "图像检测", "status": "配置", "ok": False},
        {"label": "DOCX", "status": "正常", "ok": True},
        {"label": "Excel", "status": "缺失", "ok": False},
    ]
    assert "private-model" not in repr(snapshot)
    assert "api_key" not in repr(snapshot)


def test_desktop_gui_config_snapshot_uses_real_llm_preflight_status():
    config = {
        "ok": True,
        "capabilities": {
            "text_llm": {"ok": True, "api_key_configured": True, "model": "private-model"},
            "mineru": {"ok": True},
            "image_semantic": {"ok": True},
            "reference_lookup": {"ok": True},
            "image_detector": {"ok": True},
        },
        "optional_dependencies": {"python_docx": True, "openpyxl": True},
    }

    success = paper_audit.desktop_gui_config_snapshot(
        config,
        preflight_results={"text_llm": paper_audit.PreflightResult("text_llm", True, details={"model": "private-model"})},
    )
    failure = paper_audit.desktop_gui_config_snapshot(
        config,
        preflight_results={"text_llm": paper_audit.PreflightResult("text_llm", False, "provider_unavailable", "down")},
    )

    assert success["rows"][0] == {"label": "LLM", "status": "可达", "ok": True}
    assert failure["rows"][0] == {"label": "LLM", "status": "不可达", "ok": False}
    assert "private-model" not in repr(success)


def test_desktop_gui_checked_config_snapshot_runs_injected_llm_preflight(monkeypatch):
    cfg = paper_audit.default_runtime_config()
    cfg.text_llm.api_key = "secret-llm-key"
    cfg.text_llm.api_url = "https://llm.example.test/v1/chat/completions"
    cfg.text_llm.model = "model-x"
    cfg.mineru.api_key = "mineru-token"
    cfg.image_semantic.api_key = "vision-key"
    calls = []

    monkeypatch.setattr(paper_audit, "load_runtime_config", lambda verbose=False: cfg)
    monkeypatch.setattr(paper_audit, "apply_runtime_config", lambda runtime_config: calls.append(runtime_config))

    snapshot = paper_audit.desktop_gui_checked_config_snapshot(
        llm_preflight_runner=lambda: paper_audit.PreflightResult("text_llm", True, details={"model": "model-x"}),
        mineru_preflight_runner=lambda: paper_audit.PreflightResult("mineru", True),
    )

    assert calls == [cfg]
    assert snapshot["rows"][0] == {"label": "LLM", "status": "可达", "ok": True}
    assert snapshot["rows"][1] == {"label": "MinerU", "status": "可达", "ok": True}
    assert "secret-llm-key" not in repr(snapshot)


def test_desktop_gui_write_llm_config_creates_persistent_config(tmp_path):
    config_path = tmp_path / "config.py"

    written = paper_audit.desktop_gui_write_llm_config(
        "sk-test",
        "https://llm.example.test/v1/chat/completions",
        "model-x",
        config_path=config_path,
    )

    text = written.read_text(encoding="utf-8")
    assert 'LLM_API_KEY = "sk-test"' in text
    assert 'LLM_API_URL = "https://llm.example.test/v1/chat/completions"' in text
    assert 'LLM_MODEL = "model-x"' in text


def test_desktop_gui_write_llm_config_preserves_unrelated_config(tmp_path):
    config_path = tmp_path / "config.py"
    config_path.write_text(
        "\n".join([
            'MINERU_TOKEN = "mineru-token"',
            'LLM_API_KEY = "old-key"',
            'LLM_API_URL = "https://old.example.test"',
            'LLM_MODEL = "old-model"',
            'IMAGE_SEMANTIC_API_KEY = "vision-key"',
        ]),
        encoding="utf-8",
    )

    paper_audit.desktop_gui_write_llm_config("new-key", "https://new.example.test", "new-model", config_path=config_path)

    text = config_path.read_text(encoding="utf-8")
    assert 'MINERU_TOKEN = "mineru-token"' in text
    assert 'IMAGE_SEMANTIC_API_KEY = "vision-key"' in text
    assert 'LLM_API_KEY = "new-key"' in text
    assert 'LLM_API_URL = "https://new.example.test"' in text
    assert 'LLM_MODEL = "new-model"' in text
    assert "old-key" not in text


def test_desktop_gui_render_config_snapshot_updates_read_only_rows():
    class FakeVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

    class FakeLabel:
        def __init__(self):
            self.style = ""

        def configure(self, **kwargs):
            self.style = kwargs.get("style", self.style)

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.config_summary_var = FakeVar()
    app.config_row_vars = [(FakeVar(), FakeVar(), FakeLabel()), (FakeVar(), FakeVar(), FakeLabel())]

    app._render_config_snapshot({
        "summary": "1/2 正常",
        "rows": [
            {"label": "LLM", "status": "正常", "ok": True},
            {"label": "MinerU", "status": "配置", "ok": False},
        ],
    })

    assert app.config_summary_var.value == "1/2 正常"
    assert app.config_row_vars[0][0].value == "LLM"
    assert app.config_row_vars[0][1].value == "正常"
    assert app.config_row_vars[0][2].style == "ConfigOk.TLabel"
    assert app.config_row_vars[1][0].value == "MinerU"
    assert app.config_row_vars[1][1].value == "配置"
    assert app.config_row_vars[1][2].style == "ConfigWarn.TLabel"


def test_desktop_gui_path_pickers_set_input_and_output_stem(tmp_path):
    selected_file = tmp_path / "paper.pdf"
    selected_file.write_text("paper", encoding="utf-8")
    selected_input_dir = tmp_path / "paper_project"
    selected_input_dir.mkdir()
    selected_output_dir = tmp_path / "reports"

    class FakeVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

    class FakeDialog:
        def __init__(self):
            self.directory_calls = []

        def askopenfilename(self, title=""):
            assert title == "选择材料文件"
            return str(selected_file)

        def askdirectory(self, title="", mustexist=False):
            self.directory_calls.append({"title": title, "mustexist": mustexist})
            if title == "选择材料目录":
                return str(selected_input_dir)
            if title == "选择报告目录":
                return str(selected_output_dir)
            raise AssertionError(f"unexpected directory picker title: {title}")

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.input_var = FakeVar()
    app.output_var = FakeVar()
    app.filedialog = FakeDialog()

    app.choose_file()
    assert app.input_var.value == str(selected_file)

    app.choose_directory()
    assert app.input_var.value == str(selected_input_dir)

    app.choose_output_directory()
    assert app.output_var.value == str(selected_output_dir / "audit_report")
    assert app.filedialog.directory_calls == [
        {"title": "选择材料目录", "mustexist": True},
        {"title": "选择报告目录", "mustexist": False},
    ]


def test_desktop_gui_path_buttons_show_compact_selected_paths(tmp_path):
    selected_file = tmp_path / "paper.pdf"
    selected_output = tmp_path / "reports" / "audit_report"

    class FakeVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.input_var = FakeVar()
    app.output_var = FakeVar()
    app.input_display_var = FakeVar()
    app.output_display_var = FakeVar()

    app._set_input_path(selected_file)
    app._set_output_path(selected_output)
    app.clear_output()

    assert app.input_var.value == str(selected_file)
    assert app.input_display_var.value.endswith("paper.pdf")
    assert app.output_var.value == ""
    assert app.output_display_var.value == "选择报告目录"


def test_desktop_gui_drop_handlers_update_input_and_output_paths(tmp_path):
    input_path = tmp_path / "paper.docx"
    output_dir = tmp_path / "reports"
    input_path.write_text("paper", encoding="utf-8")
    output_dir.mkdir()

    class FakeVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

    class FakeTk:
        def splitlist(self, raw):
            return [raw]

    class FakeRoot:
        tk = FakeTk()

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.root = FakeRoot()
    app.input_var = FakeVar()
    app.output_var = FakeVar()
    app.input_display_var = FakeVar()
    app.output_display_var = FakeVar()

    app._handle_input_drop(str(input_path))
    app._handle_output_drop(str(output_dir))

    assert app.input_var.value == str(input_path)
    assert app.output_var.value == str(output_dir / "audit_report")
    assert app.input_display_var.value.endswith("paper.docx")
    assert app.output_display_var.value.endswith("reports")


def test_desktop_gui_log_text_returns_to_read_only_after_append():
    class FakeState:
        def logs_since(self, run_id, offset):
            return {"offset": 1, "lines": ["📊 [████░░] 2/5  40.0% 阶段2/5 本地统计检测完成"]}

    class FakeText:
        def __init__(self):
            self.states = []
            self.contents = []

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.states.append(kwargs["state"])

        def insert(self, *args):
            self.contents.append(args[1])

        def see(self, *args):
            pass

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    class FakeVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.state = FakeState()
    app.log_offset = 0
    app.log_text = FakeText()
    app.tk = FakeTk()
    app.progress_var = FakeVar()
    app.stage_var = FakeVar()

    app._append_logs_since("run-1")

    assert app.log_text.contents == ["📊 [████░░] 2/5  40.0% 阶段2/5 本地统计检测完成\n"]
    assert app.log_text.states == [FakeTk.NORMAL, FakeTk.DISABLED]
    assert app.progress_var.value == 40.0
    assert app.stage_var.value == "阶段 2/5 · 本地统计完成"


def test_desktop_gui_artifact_preview_formats_supported_report_files(tmp_path):
    html_path = tmp_path / "report.html"
    markdown_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"
    html_path.write_text("<html><style>.x{}</style><body><h1>标题</h1><p>内容&nbsp;A</p><script>x()</script></body></html>", encoding="utf-8")
    markdown_path.write_text("# 标题\n\n正文", encoding="utf-8")
    json_path.write_text('{"risk": "低", "items": [1]}', encoding="utf-8")

    assert "标题\n内容 A" in paper_audit.desktop_gui_artifact_preview(html_path, "html")
    assert paper_audit.desktop_gui_artifact_preview(markdown_path, "markdown") == "# 标题\n\n正文"
    assert paper_audit.desktop_gui_artifact_preview(json_path, "json") == '{\n  "risk": "低",\n  "items": [\n    1\n  ]\n}'


def test_desktop_gui_open_artifact_renders_reports_in_log_and_opens_folder(tmp_path):
    report_path = tmp_path / "report.audit.md"
    report_path.write_text("# 报告", encoding="utf-8")
    opened = []

    class FakeText:
        def __init__(self):
            self.states = []
            self.deleted = []
            self.inserted = []
            self.seen = []

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.states.append(kwargs["state"])

        def delete(self, *args):
            self.deleted.append(args)

        def insert(self, *args):
            self.inserted.append(args)

        def see(self, *args):
            self.seen.append(args)

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    class FakeVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.tk = FakeTk()
    app.log_text = FakeText()
    app.log_title_var = FakeVar()
    app.artifact_paths = {"markdown": str(report_path), "folder": str(tmp_path)}
    app.opener = opened.append

    app.open_artifact("markdown")
    app.open_artifact("folder")

    assert app.log_title_var.value == "报告预览 · Markdown"
    assert app.log_text.inserted == [(FakeTk.END, "# 报告")]
    assert app.log_text.states == [FakeTk.NORMAL, FakeTk.DISABLED]
    assert opened == [str(tmp_path)]


def test_desktop_gui_followup_context_uses_recorded_json_artifact(tmp_path):
    json_path = tmp_path / "audit_report.audit.json"
    html_path = tmp_path / "audit_report.audit.html"
    json_path.write_text(
        json.dumps({
            "report_type": "complete",
            "llm_report": {
                "summary": "需要人工复核",
                "risk_level": "中",
                "checks": [{
                    "category": "图像",
                    "item": "Figure 1",
                    "verdict": "🚩红旗",
                    "evidence": "Figure 1 has duplicated regions.",
                    "reason": "图像区域高度相似。",
                    "confidence": 0.9,
                }],
            },
            "stat_result": {"number_count": 3},
            "meta": {
                "paper_identity": {"title": "Paper title", "journal": "Journal", "authors": ["Alice"]},
                "artifact_paths": {"html": str(html_path), "json": str(json_path)},
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    run = {
        "status": "succeeded",
        "input_path": str(tmp_path / "paper.pdf"),
        "artifacts": {"json": str(json_path), "html": str(html_path), "folder": str(tmp_path)},
    }

    context = paper_audit.desktop_gui_followup_context(run)

    assert context["artifact_type"] == "complete"
    assert context["paper_identity"]["title"] == "Paper title"
    assert context["artifact_paths"]["html"] == str(html_path)
    assert context["followups_dir"] == str(tmp_path / "followups")
    assert context["top_issues"][0]["item"] == "Figure 1"


def test_desktop_gui_generate_followup_draft_reuses_formal_followup_writer(monkeypatch, tmp_path):
    captured = {}
    json_path = tmp_path / "audit_report.audit.json"
    json_path.write_text(
        json.dumps({
            "report_type": "complete",
            "llm_report": {
                "summary": "ok",
                "risk_level": "中",
                "checks": [{"category": "数据", "item": "Table 1", "verdict": "🚩红旗", "reason": "异常"}],
            },
            "meta": {"paper_identity": {"title": "Confirmed title"}},
            "stat_result": {},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    def fake_generate(kind, context, language="zh", tone=None, timeout=None):
        captured["kind"] = kind
        captured["context"] = context
        captured["language"] = language
        captured["tone"] = tone
        return "这是 PubPeer 草稿。"

    monkeypatch.setattr(paper_audit, "generate_followup_draft", fake_generate)

    result = paper_audit.desktop_gui_generate_followup_draft(
        "pubpeer_comment",
        {"status": "succeeded", "input_path": str(tmp_path / "paper.pdf"), "artifacts": {"json": str(json_path)}},
    )

    assert result["ok"] is True
    assert result["text"] == "这是 PubPeer 草稿。"
    assert captured["kind"] == "pubpeer_comment"
    assert captured["language"] == "zh"
    assert captured["context"]["paper_identity"]["title"] == "Confirmed title"
    assert Path(result["paths"]["draft_path"]).name == "pubpeer_comment.zh.md"


def test_desktop_gui_followup_context_blocks_failed_json_artifact(tmp_path):
    json_path = tmp_path / "audit_report.failed.json"
    json_path.write_text(json.dumps({"report_type": "failed", "failure": {"message": "缺少配置"}}, ensure_ascii=False), encoding="utf-8")

    try:
        paper_audit.desktop_gui_followup_context({"status": "failed", "artifacts": {"json": str(json_path)}})
    except ValueError as exc:
        assert "failed_report_followup_blocked" in str(exc)
    else:
        raise AssertionError("failed GUI reports must not generate follow-up drafts")


def test_desktop_gui_render_run_enables_followup_buttons_for_success_json():
    class FakeVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class FakeButton:
        def __init__(self):
            self.state = None

        def configure(self, **kwargs):
            self.state = kwargs.get("state", self.state)

    class FakeTk:
        NORMAL = "normal"
        DISABLED = "disabled"

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.tk = FakeTk()
    app.status_var = FakeVar()
    app.report_type_var = FakeVar()
    app.risk_var = FakeVar()
    app.summary_var = FakeVar()
    app.stage_var = FakeVar()
    app.progress_var = FakeVar()
    app.artifact_buttons = {"json": FakeButton()}
    app.followup_buttons = {"pubpeer_comment": FakeButton(), "journal_letter": FakeButton()}

    app.render_run({"status": "succeeded", "artifacts": {"json": "/tmp/report.audit.json"}, "summary": {"report_type": "complete"}})

    assert app.followup_buttons["pubpeer_comment"].state == FakeTk.NORMAL
    assert app.followup_buttons["journal_letter"].state == FakeTk.NORMAL

    app.render_run({"status": "failed", "artifacts": {"json": "/tmp/report.failed.json"}, "summary": {"report_type": "failed"}})

    assert app.followup_buttons["pubpeer_comment"].state == FakeTk.DISABLED
    assert app.followup_buttons["journal_letter"].state == FakeTk.DISABLED


def test_desktop_gui_auto_previews_successful_html_report_once(tmp_path):
    report_path = tmp_path / "report.audit.html"
    report_path.write_text("<h1>完整报告</h1>", encoding="utf-8")

    class FakeVar:
        def get(self):
            return True

        def set(self, value):
            self.value = value

    class FakeText:
        def __init__(self):
            self.inserted = []

        def configure(self, **kwargs):
            pass

        def delete(self, *args):
            pass

        def insert(self, *args):
            self.inserted.append(args)

        def see(self, *args):
            pass

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    class FakeMessageBox:
        def showerror(self, *args, **kwargs):
            raise AssertionError("auto-preview success should not show an error")

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.tk = FakeTk()
    app.log_text = FakeText()
    app.log_title_var = FakeVar()
    app.auto_open_var = FakeVar()
    app.auto_opened_run_ids = set()
    app.messagebox = FakeMessageBox()
    run = {"id": "run-1", "status": "succeeded", "artifacts": {"html": str(report_path)}}

    app._maybe_auto_open_completed_report(run)
    app._maybe_auto_open_completed_report(run)

    assert app.log_title_var.value == "报告预览 · HTML"
    assert app.log_text.inserted == [(FakeTk.END, "完整报告")]


def test_desktop_gui_auto_open_can_be_disabled():
    opened = []

    class FakeVar:
        def get(self):
            return False

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.auto_open_var = FakeVar()
    app.auto_opened_run_ids = set()
    app.opener = opened.append
    app.messagebox = None

    app._maybe_auto_open_completed_report({"id": "run-1", "status": "succeeded", "artifacts": {"html": "/tmp/report.audit.html"}})

    assert opened == []


def test_desktop_gui_does_not_auto_open_failed_report():
    opened = []

    class FakeVar:
        def get(self):
            return True

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.auto_open_var = FakeVar()
    app.auto_opened_run_ids = set()
    app.opener = opened.append
    app.messagebox = None

    app._maybe_auto_open_completed_report({"id": "run-1", "status": "failed", "artifacts": {"html": "/tmp/report.failed.html"}})

    assert opened == []


def test_desktop_gui_poll_success_discovers_artifacts_and_auto_opens_html(tmp_path):
    class FakeState:
        def __init__(self):
            self.discover_calls = []
            self.report_path = None
            self.run = {
                "id": "run-1",
                "status": "succeeded",
                "input_path": "/tmp/paper.pdf",
                "artifacts": {},
                "summary": {},
            }

        def logs_since(self, run_id, offset):
            return {"offset": 0, "lines": []}

        def get_run(self, run_id):
            return dict(self.run)

        def discover_artifacts(self, run_id):
            self.discover_calls.append(run_id)
            self.run = {
                **self.run,
                "artifacts": {"html": self.report_path, "folder": "/tmp"},
                "summary": {"report_type": "complete", "risk_level": "低", "summary": "ok"},
            }
            return dict(self.run)

    class FakeVar:
        def __init__(self, value=None):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeButton:
        def __init__(self):
            self.state = None

        def configure(self, **kwargs):
            self.state = kwargs.get("state", self.state)

    class FakeText:
        def __init__(self):
            self.lines = []
            self.seen = []
            self.deleted = []
            self.states = []

        def configure(self, **kwargs):
            if "state" in kwargs:
                self.states.append(kwargs["state"])

        def delete(self, *args, **kwargs):
            self.deleted.append(args)

        def insert(self, *args, **kwargs):
            self.lines.append(args)

        def see(self, *args, **kwargs):
            self.seen.append(args)

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    report_path = tmp_path / "report.audit.html"
    report_path.write_text("<h1>完整报告</h1>", encoding="utf-8")
    app.active_run_id = "run-1"
    app.log_offset = 0
    app.state = FakeState()
    app.state.report_path = str(report_path)
    app.tk = FakeTk()
    app.log_text = FakeText()
    app.log_title_var = FakeVar()
    app.status_var = FakeVar()
    app.report_type_var = FakeVar()
    app.risk_var = FakeVar()
    app.summary_var = FakeVar()
    app.auto_open_var = FakeVar(True)
    app.auto_opened_run_ids = set()
    app.artifact_paths = {}
    app.artifact_buttons = {"html": FakeButton(), "markdown": FakeButton(), "json": FakeButton(), "folder": FakeButton()}
    app.start_button = FakeButton()
    app.cancel_button = FakeButton()
    app.retry_button = FakeButton()
    app.messagebox = None

    app.poll_run()

    assert app.state.discover_calls == ["run-1"]
    assert app.log_title_var.value == "报告预览 · HTML"
    assert (FakeTk.END, "完整报告") in app.log_text.lines
    assert app.active_run_id is None
    assert app.status_var.value == "已完成"
    assert app.report_type_var.value == "完整报告"
    assert app.risk_var.value == "低"
    assert app.summary_var.value == "ok"
    assert app.artifact_buttons["html"].state == FakeTk.NORMAL
    assert app.artifact_buttons["folder"].state == FakeTk.NORMAL


def test_desktop_gui_poll_drains_terminal_logs_before_stopping():
    class FakeState:
        def __init__(self):
            self.calls = 0

        def logs_since(self, run_id, offset):
            self.calls += 1
            if self.calls == 1:
                return {"offset": 1, "lines": ["first"]}
            return {"offset": 3, "lines": ["second", "third"]}

        def get_run(self, run_id):
            return {"id": run_id, "status": "failed", "input_path": "/tmp/paper.pdf", "artifacts": {}, "summary": {}}

        def discover_artifacts(self, run_id):
            return {"id": run_id, "status": "failed", "input_path": "/tmp/paper.pdf", "artifacts": {}, "summary": {}}

    class FakeVar:
        def __init__(self, value=None):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    class FakeButton:
        def configure(self, **kwargs):
            pass

    class FakeText:
        def __init__(self):
            self.contents = []

        def insert(self, *args):
            self.contents.append(args[1])

        def see(self, *args):
            pass

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.active_run_id = "run-1"
    app.log_offset = 0
    app.state = FakeState()
    app.tk = FakeTk()
    app.log_text = FakeText()
    app.status_var = FakeVar()
    app.report_type_var = FakeVar()
    app.risk_var = FakeVar()
    app.summary_var = FakeVar()
    app.auto_open_var = FakeVar(True)
    app.auto_opened_run_ids = set()
    app.artifact_paths = {}
    app.artifact_buttons = {"html": FakeButton(), "markdown": FakeButton(), "json": FakeButton(), "folder": FakeButton()}
    app.start_button = FakeButton()
    app.cancel_button = FakeButton()
    app.retry_button = FakeButton()
    app.opener = lambda path: None
    app.messagebox = None

    app.poll_run()

    assert app.log_text.contents == ["first\n", "second\n", "third\n"]
    assert app.log_offset == 3
    assert app.active_run_id is None


def test_desktop_gui_refresh_runs_shows_latest_completed_run_logs():
    class FakeState:
        def list_runs(self):
            return [{"id": "run-1", "status": "failed", "input_path": "/tmp/paper.pdf", "artifacts": {}, "summary": {}}]

        def logs_since(self, run_id, offset):
            return {"offset": 2, "lines": ["line one", "line two"]}

    class FakeVar:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    class FakeButton:
        def __init__(self):
            self.state = None

        def configure(self, **kwargs):
            self.state = kwargs.get("state", self.state)

    class FakeText:
        def __init__(self):
            self.contents = []
            self.deleted = False

        def delete(self, *args):
            self.deleted = True

        def insert(self, *args):
            self.contents.append(args[1])

        def see(self, *args):
            pass

    class FakeTk:
        END = "end"
        NORMAL = "normal"
        DISABLED = "disabled"

    app = paper_audit.DesktopGuiApp.__new__(paper_audit.DesktopGuiApp)
    app.active_run_id = None
    app.log_offset = 99
    app.state = FakeState()
    app.tk = FakeTk()
    app.log_text = FakeText()
    app.status_var = FakeVar()
    app.report_type_var = FakeVar()
    app.risk_var = FakeVar()
    app.summary_var = FakeVar()
    app.artifact_buttons = {"html": FakeButton(), "markdown": FakeButton(), "json": FakeButton(), "folder": FakeButton()}
    app.retry_button = FakeButton()

    app.refresh_runs()

    assert app.log_text.deleted is True
    assert app.log_text.contents == ["line one\n", "line two\n"]
    assert app.log_offset == 2
    assert app.status_var.value == "需处理"
    assert app.retry_button.state == FakeTk.NORMAL


def test_report_action_context_cleans_reference_issue_text():
    context = paper_audit._report_action_context(
        {"summary": "ok", "risk_level": "中", "detection_score": 50, "checks": [], "conclusion": "done"},
        "paper.pdf",
        {
            "reference_audit": {
                "reference_count": 1,
                "online_checked": 1,
                "issues": [{
                    "index": 1,
                    "issues": ["missing_doi"],
                    "text": "[[EXTRACTION_NOTE]]noise[[/EXTRACTION_NOTE]]\n[[BLOCK type=text]]Smith J. Journal. 2020.[[/BLOCK]]",
                }],
            }
        },
        {"number_count": 0, "p_value_count": 0, "p_value_abnormal": 0},
    )

    text = context["references"]["issues"][0]["text"]
    assert "Smith J." in text
    assert "EXTRACTION_NOTE" not in text
    assert "[[BLOCK" not in text


def test_report_action_context_includes_paper_identity():
    context = paper_audit._report_action_context(
        {"summary": "ok", "risk_level": "中", "detection_score": 50, "checks": [], "conclusion": "done"},
        "paper.pdf",
        {
            "paper_identity": {
                "title": "A precise article title",
                "journal": "Journal of Reproducible Checks",
                "authors": ["Alice Zhang", "Bob Smith"],
            }
        },
        {"number_count": 0},
    )

    assert context["paper_identity"]["title"] == "A precise article title"
    assert context["paper_identity"]["journal"] == "Journal of Reproducible Checks"
    assert context["paper_identity"]["authors"] == ["Alice Zhang", "Bob Smith"]


def test_extract_paper_identity_uses_front_matter():
    text = """
    A precise article title about reproducible biomarkers
    Alice Zhang, Bob Smith, Carol Li
    Journal of Reproducible Checks

    Abstract
    This paper reports results.
    """

    identity = paper_audit.extract_paper_identity(text)

    assert identity["title"] == "A precise article title about reproducible biomarkers"
    assert identity["journal"] == "Journal of Reproducible Checks"
    assert identity["authors"][:2] == ["Alice Zhang", "Bob Smith"]


def test_build_followup_prompt_uses_requested_kind_and_context():
    context = {
        "paper_identity": {
            "title": "A precise article title",
            "journal": "Journal X",
            "authors": ["Alice Zhang"],
        },
        "summary": "发现一个疑点",
        "top_issues": [{"item": "p值", "reason": "p值异常"}],
    }

    pubpeer_messages = paper_audit.build_followup_prompt("pubpeer_comment", context, language="zh")
    letter_messages = paper_audit.build_followup_prompt("journal_letter", context, language="en")

    assert "PubPeer comment" in pubpeer_messages[1]["content"]
    assert "letter to the journal editor" in letter_messages[1]["content"]
    assert "请使用简体中文" in pubpeer_messages[1]["content"]
    assert "Based on my reading and understanding of this article" in letter_messages[1]["content"]
    assert "paper_identity.title" in pubpeer_messages[1]["content"]
    assert "journal name" in pubpeer_messages[1]["content"]
    assert "author information" in pubpeer_messages[1]["content"]
    assert "发现一个疑点" in pubpeer_messages[1]["content"]


def test_build_followup_generation_context_blocks_failed_report():
    try:
        paper_audit.build_followup_generation_context({"artifact_type": "failed"})
    except ValueError as exc:
        assert "failed_report_followup_blocked" in str(exc)
    else:
        raise AssertionError("expected failed reports to block follow-up generation")


def test_build_followup_prompt_includes_tone_scope_and_user_concerns():
    context = paper_audit.build_followup_generation_context(
        {
            "artifact_type": "limited",
            "limited_reasons": ["图像语义分析未覆盖全部图片"],
            "paper_identity": {
                "title": "Original title",
                "journal": "Journal X",
                "authors": ["Alice Zhang"],
            },
            "top_issues": [{"id": "a", "category": "数据", "item": "p值", "verdict": "🚩红旗", "reason": "p值异常"}],
        },
        identity={"title": "Confirmed title", "journal": "Confirmed Journal", "authors": "Alice Zhang, Bob Smith", "doi": "10.1/test", "year": "2024"},
        selected_issues=[{"id": "a", "category": "数据", "item": "p值", "verdict": "🚩红旗", "reason": "p值异常"}],
        custom_concerns=["图2图注与正文描述不一致"],
        tone="firm",
    )

    messages = paper_audit.build_followup_prompt("pubpeer_comment", context, language="en")
    content = messages[1]["content"]

    assert "Confirmed title" in content
    assert "Confirmed Journal" in content
    assert "selected_issues" in content
    assert "source=user_added" in content
    assert "limited" in content
    assert "firm" in content
    assert "图2图注与正文描述不一致" in content


def test_generate_and_save_followup_draft_persists_formal_artifacts(monkeypatch, tmp_path):
    captured = {}

    def fake_generate(kind, context, language="zh", tone=None, timeout=None):
        captured["kind"] = kind
        captured["context"] = context
        captured["language"] = language
        captured["tone"] = tone
        return "基于对这篇文章的阅读和理解，我注意到以下问题。"

    monkeypatch.setattr(paper_audit, "generate_followup_draft", fake_generate)
    context = {
        "artifact_type": "complete",
        "followups_dir": str(tmp_path / "followups"),
        "paper_identity": {"title": "Original", "journal": "Journal", "authors": ["Alice"]},
        "top_issues": [{"id": "issue-1", "category": "数据", "item": "异常", "verdict": "🚩红旗", "reason": "异常"}],
    }

    result = paper_audit.generate_and_save_followup_draft(
        "pubpeer_comment",
        context,
        language="zh",
        identity={"title": "Confirmed", "journal": "Confirmed Journal", "authors": ["Alice", "Bob"], "doi": "10.1/test", "year": "2024"},
        selected_issues=context["top_issues"],
        custom_concerns=["人工补充问题"],
        tone="standard",
        disclaimer_confirmed=True,
    )

    followups_dir = tmp_path / "followups"
    identity_payload = json.loads((followups_dir / "article_identity.json").read_text(encoding="utf-8"))
    log_payload = json.loads((followups_dir / "followup_generation_log.json").read_text(encoding="utf-8"))

    assert result["paths"]["draft_path"].endswith("pubpeer_comment.zh.md")
    assert (followups_dir / "pubpeer_comment.zh.md").read_text(encoding="utf-8").startswith("基于对这篇文章")
    assert identity_payload["title"] == "Confirmed"
    assert identity_payload["journal"] == "Confirmed Journal"
    assert identity_payload["language"] == "zh"
    assert log_payload[-1]["kind"] == "pubpeer_comment"
    assert log_payload[-1]["tone"] == "standard"
    assert captured["context"]["custom_concerns"][0]["source"] == "user_added"
    assert captured["context"]["selected_issues"][0]["id"] == "issue-1"


def test_generate_and_save_followup_requires_manual_confirmation(tmp_path):
    try:
        paper_audit.generate_and_save_followup_draft(
            "journal_letter",
            {"artifact_type": "complete", "followups_dir": str(tmp_path / "followups")},
            disclaimer_confirmed=False,
        )
    except ValueError as exc:
        assert "manual_review_confirmation_required" in str(exc)
    else:
        raise AssertionError("expected manual confirmation to be required")


def test_load_existing_followups_reads_saved_files(tmp_path):
    followups_dir = tmp_path / "followups"
    followups_dir.mkdir()
    (followups_dir / "pubpeer_comment.en.md").write_text("Existing PubPeer draft", encoding="utf-8")
    (followups_dir / "article_identity.json").write_text(json.dumps({"title": "Confirmed"}, ensure_ascii=False), encoding="utf-8")

    loaded = paper_audit.load_existing_followups({"followups_dir": str(followups_dir)}, language="en")

    assert loaded["ok"] is True
    assert loaded["identity"]["title"] == "Confirmed"
    assert loaded["drafts"]["pubpeer_comment"]["text"] == "Existing PubPeer draft"
    assert "journal_letter" not in loaded["drafts"]
