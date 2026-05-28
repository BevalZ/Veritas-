"""External audit capability adapter boundary."""

from .legacy import (
    AdapterResult,
    AuditAdapters,
    ProductionImageDetectorAdapter,
    ProductionImageSemanticAdapter,
    ProductionMinerUAdapter,
    ProductionReferenceLookupAdapter,
    ProductionTextLLMAdapter,
    default_audit_adapters,
    fake_audit_adapters,
)

__all__ = [
    "AdapterResult",
    "AuditAdapters",
    "ProductionMinerUAdapter",
    "ProductionTextLLMAdapter",
    "ProductionReferenceLookupAdapter",
    "ProductionImageSemanticAdapter",
    "ProductionImageDetectorAdapter",
    "default_audit_adapters",
    "fake_audit_adapters",
]
