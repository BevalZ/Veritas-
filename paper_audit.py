"""Compatibility entry point for the Veritas paper audit CLI.

The implementation lives in :mod:`veritas.legacy` while this module preserves
the historical ``python paper_audit.py`` and ``import paper_audit`` surfaces.
"""
import sys as _sys

from veritas import legacy as _legacy


if __name__ == "__main__":
    raise SystemExit(_legacy.main())


_sys.modules[__name__] = _legacy
