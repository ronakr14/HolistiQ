from pathlib import Path

from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def _load_file_contents(path: Path, encoding: str = "utf-8") -> str:
    logger.debug(f"loading file from {path}")
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def load_txt(path: Path, encoding: str = "utf-8"):
    return _load_file_contents(path, encoding)
