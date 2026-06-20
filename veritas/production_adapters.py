"""Production audit capability adapters backed by legacy provider functions."""

from pathlib import Path
from typing import Callable

from .adapter_types import (
    AdapterResult,
    AuditAdapters,
    ImageDetectorAdapter,
    ImageSemanticAdapter,
    MinerUAdapter,
    ReferenceLookupAdapter,
    TextLLMAdapter,
)
from .preflight import preflight_mineru, preflight_text_llm


def _legacy_func(name: str) -> Callable:
    from . import legacy

    return getattr(legacy, name)


def _adapter_result_from_preflight(result) -> AdapterResult:
    if result.ok:
        return AdapterResult.success(result.to_dict(), details=result.details)
    return AdapterResult.failure(
        result.error_class or "preflight_failed",
        result.message or "preflight failed",
        result.details,
    )


class ProductionMinerUAdapter(MinerUAdapter):
    def __init__(self, preflight_func: Callable = None, extract_func: Callable = None):
        self.preflight_func = preflight_func or preflight_mineru
        self.extract_func = extract_func or _legacy_func("mineru_extract")

    def preflight(self) -> AdapterResult:
        return _adapter_result_from_preflight(self.preflight_func())

    def extract(self, file_path: Path, language="ch", output_dir=None) -> AdapterResult:
        text, meta = self.extract_func(file_path, language=language, output_dir=output_dir)
        if text:
            return AdapterResult.success({"text": text, "meta": meta or {}})
        meta = meta if isinstance(meta, dict) else {}
        return AdapterResult.failure(
            meta.get("error_class", "provider_error"),
            meta.get("error", "MinerU extraction failed"),
            meta,
        )


class ProductionTextLLMAdapter(TextLLMAdapter):
    def __init__(self, preflight_func: Callable = None, review_func: Callable = None):
        self.preflight_func = preflight_func or preflight_text_llm
        self.review_func = review_func or _legacy_func("call_llm")

    def preflight(self) -> AdapterResult:
        return _adapter_result_from_preflight(self.preflight_func())

    def review(self, text: str, chunk_info=None) -> AdapterResult:
        try:
            return AdapterResult.success(self.review_func(text, chunk_info=chunk_info))
        except Exception as e:
            return AdapterResult.failure("provider_error", str(e), {"chunk_info": chunk_info})


class ProductionReferenceLookupAdapter(ReferenceLookupAdapter):
    def __init__(self, audit_func: Callable = None):
        self.audit_func = audit_func or _legacy_func("audit_references")

    def audit(self, references_text: str, online=False, online_limit=50, timeout=10, cache=None) -> AdapterResult:
        try:
            return AdapterResult.success(
                self.audit_func(
                    references_text,
                    online=online,
                    online_limit=online_limit,
                    timeout=timeout,
                    cache=cache,
                )
            )
        except Exception as e:
            return AdapterResult.failure("provider_error", str(e), {"online": online})


class ProductionImageSemanticAdapter(ImageSemanticAdapter):
    def __init__(self, analyze_func: Callable = None):
        self.analyze_func = analyze_func or _legacy_func("call_glm_image_semantics")

    def analyze(self, image_path: str, timeout=45) -> AdapterResult:
        result = self.analyze_func(image_path, timeout=timeout)
        if isinstance(result, dict) and result.get("status") == "error":
            return AdapterResult.failure(
                result.get("reason") or "provider_error",
                result.get("error_message") or "image semantic analysis failed",
                result,
            )
        return AdapterResult.success(result)


class ProductionImageDetectorAdapter(ImageDetectorAdapter):
    def __init__(self, detect_func: Callable = None):
        self.detect_func = detect_func or _legacy_func("call_imagedetector")

    def detect(self, image_path: str, timeout=60) -> AdapterResult:
        result = self.detect_func(image_path, timeout=timeout)
        if isinstance(result, dict) and result.get("status") == "skipped":
            return AdapterResult.skipped(
                result.get("reason") or "skipped",
                result.get("summary") or "image detector skipped",
                result,
            )
        if isinstance(result, dict) and result.get("status") == "error":
            return AdapterResult.failure(
                result.get("reason") or "provider_error",
                result.get("summary") or "image detector failed",
                result,
            )
        return AdapterResult.success(result)


def default_audit_adapters() -> AuditAdapters:
    return AuditAdapters(
        mineru=ProductionMinerUAdapter(),
        text_llm=ProductionTextLLMAdapter(),
        reference_lookup=ProductionReferenceLookupAdapter(),
        image_semantic=ProductionImageSemanticAdapter(),
        image_detector=ProductionImageDetectorAdapter(),
    )


__all__ = [
    "ProductionMinerUAdapter",
    "ProductionTextLLMAdapter",
    "ProductionReferenceLookupAdapter",
    "ProductionImageSemanticAdapter",
    "ProductionImageDetectorAdapter",
    "default_audit_adapters",
]
