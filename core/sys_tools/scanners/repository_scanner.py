from pathlib import Path
from typing import Union

from custom_logger.logging_util import get_logger
from core.scanners.file_scanner import scan_file
from core.scanners.schema import FunctionMeta

logger = get_logger(__name__)


EXCLUDED_FILENAMES = {"__init__.py"}
EXCLUDED_PREFIXES = ("test_",)


def _should_exclude_file(path: Path) -> bool:
    name = path.name
    if name in EXCLUDED_FILENAMES:
        return True
    if any(name.startswith(p) for p in EXCLUDED_PREFIXES):
        return True
    return False


def _path_to_module(file_path: Path, root: Path) -> str:
    """
    Convert a file path relative to root into a dotted module string.
    e.g. root/pipelines/etl.py → pipelines.etl
    """
    relative = file_path.relative_to(root)
    parts = list(relative.parts)
    parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts)


def scan_repository(root: Union[Path, str]) -> dict[str, list[FunctionMeta]]:
    """
    Walk a repository from `root`, scan all eligible Python files.

    Returns a dict keyed by module path (e.g. "pipelines.etl") with a list
    of FunctionMeta objects found in that module.
    """
    root = Path(root).resolve()
    results: dict[str, list[FunctionMeta]] = {}

    for py_file in sorted(root.rglob("*.py")):
        if _should_exclude_file(py_file):
            logger.debug(f"Excluded: {py_file}")
            continue

        module = _path_to_module(py_file, root)
        functions = scan_file(py_file, module)

        if functions:
            results[module] = functions
            logger.debug(f"Scanned {module}: {len(functions)} function(s)")

    return results
