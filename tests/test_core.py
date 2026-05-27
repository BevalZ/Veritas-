import json
import subprocess
import sys
from pathlib import Path
import zipfile

import paper_audit


def test_extract_all_numbers_filters_years_and_small_noise():
    text = "In 2024, group A had 12.5 units, group B had 99, and page 3 showed 0.25."

    assert paper_audit.extract_all_numbers(text) == [12.5, 99.0, 0.25]


def test_local_stat_check_flags_abnormal_p_values_and_sample_conflict():
    result = paper_audit.local_stat_check("n=12, N=14, p=0.06, p < 0.001, SD=2.4")

    assert result["p_value_count"] == 2
    assert result["p_value_abnormal"] == 1
    assert "不同样本量" in result["number_consistency"]
    assert result["sd_count"] == 1


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


def test_split_references_from_text_removes_reference_tail():
    text = "Abstract\nBody with n=20.\n\nReferences\n1. Smith J. Journal X. 2020. doi:10.1000/abc\n2. Missing source"

    main_text, refs = paper_audit.split_references_from_text(text)

    assert "Body with n=20" in main_text
    assert "Smith J" not in main_text
    assert "Smith J" in refs


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


def test_verify_reference_online_reports_not_found_without_network_error(monkeypatch):
    ref = {"text": "Invented title. Imaginary Journal. 2021. doi:10.9999/notfound", "doi": "10.9999/notfound", "year": "2021"}

    monkeypatch.setattr(paper_audit, "lookup_crossref_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_openalex_reference", lambda _ref, timeout=10: [])
    monkeypatch.setattr(paper_audit, "lookup_pubmed_reference", lambda _ref, timeout=10: [])

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
        assert body["max_tokens"] == 800
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

    assert "未进入GLM优先队列" in summary
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
    assert "GLM语义理解" in html
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

    assert parsed["summary"] == "文本严重乱码"
    assert parsed["risk_level"] == "高"
    assert parsed["_partial_parse"] is True
    assert not parsed.get("parse_error")
    assert parsed["checks"][0]["verdict"] == "🚩红旗"


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
    assert "不再打开网页或要求手动上传" in result.stdout
    assert "--serve-report-actions" in result.stdout


def test_json_report_payload_shape_stays_stable(tmp_path):
    payload = {
        "llm_report": {"summary": "ok"},
        "stat_result": {"number_count": 1},
        "meta": {"llm_coverage": "1/1"},
    }

    assert json.loads(json.dumps(payload))["meta"]["llm_coverage"] == "1/1"


def test_find_project_files_skips_generated_outputs(tmp_path):
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "paper_reference.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "audit_report.audit.md").write_text("generated", encoding="utf-8")
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
    assert "paper-audit-action-context" in rendered
    assert "127.0.0.1:8765" in rendered
    assert "证据型疑点 1" in rendered


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


def test_build_followup_prompt_uses_requested_kind_and_context():
    context = {"summary": "发现一个疑点", "top_issues": [{"item": "p值", "reason": "p值异常"}]}

    pubpeer_messages = paper_audit.build_followup_prompt("pubpeer_comment", context)
    letter_messages = paper_audit.build_followup_prompt("journal_letter", context)

    assert "PubPeer comment" in pubpeer_messages[1]["content"]
    assert "letter to the journal editor" in letter_messages[1]["content"]
    assert "Use the main language" in pubpeer_messages[1]["content"]
    assert "发现一个疑点" in pubpeer_messages[1]["content"]
