"""
scanner.py - AST-based static analysis of Python files.

Walks a repository, parses .py files without importing them,
and extracts function metadata: name, args, kwargs, type hints, docstrings.
"""

import ast
from pathlib import Path
from typing import Any, Optional

from custom_logger.logging_util import get_logger
from core.scanners.schema import ArgMeta, FunctionMeta

logger = get_logger(__name__)


def _resolve_annotation(node: Optional[ast.expr]) -> Optional[str]:
    """Convert an AST annotation node to a readable string."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _resolve_default(node: ast.expr) -> Any:
    """
    Safely evaluate a default value AST node.
    Falls back to the unparsed string representation if literal_eval fails.
    Handles complex defaults like `default=[]` or `default=SomeEnum.VALUE`.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        try:
            return ast.unparse(node)
        except Exception:
            return None


def _parse_arguments(
    func_def: ast.FunctionDef, source_lines: list[str]
) -> list[ArgMeta]:
    """
    Extract all arguments from a FunctionDef node.

    Rules:
    - self / cls are skipped (method receivers)
    - *args and **kwargs are marked is_variadic=True and excluded from CLI
    - Args without defaults → positional
    - Args with defaults → keyword (--flag)
    - Defaults in ast are right-aligned: last N args map to last N defaults
    """
    args: list[ArgMeta] = []
    all_args = func_def.args

    # Collect positional + keyword args (excludes *args, **kwargs)
    plain_args = all_args.args
    defaults = all_args.defaults  # Right-aligned to plain_args

    n = len(plain_args)
    n_defaults = len(defaults)
    default_offset = n - n_defaults  # Index from which defaults start

    for i, arg in enumerate(plain_args):
        if arg.arg in ("self", "cls"):
            continue

        has_default = i >= default_offset
        default_val = (
            _resolve_default(defaults[i - default_offset]) if has_default else None
        )

        args.append(
            ArgMeta(
                name=arg.arg,
                type_hint=_resolve_annotation(arg.annotation),
                default=default_val,
                is_kwarg=has_default,
                is_variadic=False,
            )
        )

    # keyword-only args (after *args)
    for i, arg in enumerate(all_args.kwonlyargs):
        kw_default = all_args.kw_defaults[i]
        default_val = _resolve_default(kw_default) if kw_default is not None else None
        args.append(
            ArgMeta(
                name=arg.arg,
                type_hint=_resolve_annotation(arg.annotation),
                default=default_val,
                is_kwarg=True,
                is_variadic=False,
            )
        )

    # Mark variadic args (skip in CLI generation)
    if all_args.vararg:
        args.append(ArgMeta(name=all_args.vararg.arg, is_variadic=True))
    if all_args.kwarg:
        args.append(ArgMeta(name=all_args.kwarg.arg, is_variadic=True))

    return args


# ---------------------------------------------------------------------------
# File Scanner
# ---------------------------------------------------------------------------


def scan_file(file_path: Path, module: str) -> list[FunctionMeta]:
    """
    Parse a single Python file and return FunctionMeta for each public function.

    Only top-level functions are scanned (not nested or class methods).
    Private functions (leading underscore) are excluded.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        logger.warning(f"Skipping {file_path}: {e}")
        return []

    source_lines = source.splitlines()
    functions: list[FunctionMeta] = []

    for node in ast.iter_child_nodes(tree):
        # Top-level functions only
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip private functions
        if node.name.startswith("_"):
            continue

        docstring = ast.get_docstring(node)
        args = _parse_arguments(node, source_lines)

        functions.append(
            FunctionMeta(
                name=node.name,
                module=module,
                file_path=file_path,
                args=args,
                docstring=docstring,
                source_lines=(node.lineno, node.end_lineno),
            )
        )

    return functions
