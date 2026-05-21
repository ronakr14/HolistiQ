"""
Reads the HOLISTIQ_CLI environment variable and returns
the matching adapter instance. Defaults to argparse.

Supported values (case-insensitive):
    HOLISTIQ_CLI=argparse   → ArgparseAdapter  (default)
    HOLISTIQ_CLI=typer      → TyperAdapter  # TODO

Switching at runtime:
    HOLISTIQ_CLI=typer holistiq run
    export HOLISTIQ_CLI=typer && holistiq run
"""

from __future__ import annotations

import os

from core.cli_tool.base import BaseCLIAdapter

_SUPPORTED = ("argparse",)


def get_adapter() -> BaseCLIAdapter:
    backend = os.environ.get("HOLISTIQ_CLI", "argparse").lower().strip()

    if backend not in _SUPPORTED:
        raise ValueError(
            f"Unknown CLI backend '{backend}'. "
            f"Set HOLISTIQ_CLI env variable to one of: {', '.join(_SUPPORTED)}"
        )

    from core.cli_tool.argparse_adapter import ArgparseAdapter

    return ArgparseAdapter()
