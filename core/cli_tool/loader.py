"""
Plugin loader.

Imports every module inside the `plugins/` package so their
@register_command / @register_subcommand decorators fire and
self-register into the global registry.

You never need to touch this file when adding a new plugin —
just drop a .py file into holistiq/plugins/ and it's picked up.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def load_plugins(package_name: str = "core.cli_tool.plugins") -> None:
    """Import all modules in the plugins package."""
    package_path = Path(__file__).parent / "plugins"

    for module_info in pkgutil.iter_modules([str(package_path)]):
        module_name = f"{package_name}.{module_info.name}"
        importlib.import_module(module_name)
