"""CLI boundary for the paper audit command."""


def main(*args, **kwargs):
    from .legacy import main as legacy_main

    return legacy_main(*args, **kwargs)

__all__ = ["main"]
