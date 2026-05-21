from pathlib import Path
from typing import Union

from core.infra.observe.logging.logging_util import get_logger

logger = get_logger(__name__)


def ensure_dir(path: Union[str, Path]) -> None:
    logger.debug(f"Ensuring directory: {path}")
    Path(path).mkdir(parents=True, exist_ok=True)
