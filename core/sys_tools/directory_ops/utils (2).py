from pathlib import Path

from core.infrastructure.observability.logging.logging_util import get_logger
from core.utils.directory_utils import ensure_dir

logger = get_logger(__name__)


def resolve_deid_directories(base_dir: str, client: str) -> dict[str, Path]:
    """
    Resolves the directory structure for the given client.

    Args:
        base_dir (str): Base directory for the de-identification pipeline.
        client (str): Client name.

    Returns:
        dict[str, Path]: Dictionary containing the resolved directory structure. The keys are the names of the directories and the values are the Path objects pointing to the directories.

    Notes:
        1. The base directory is assumed to be the root directory for the de-identification pipeline.
        2. The directory structure is resolved by creating the required directories if they do not exist.
        3. The resolved directory structure is returned as a dictionary with the names of the directories as keys and the Path objects pointing to the directories as values.
    """
    base_path = Path(base_dir) / "deid" / client

    paths = {
        "base_dir": base_path,
        "raw": base_path / "raw",
        "master": base_path / "master",
        "archive": base_path / "archive",
        "output": base_path / "output",
    }

    for name, path in paths.items():
        ensure_dir(path=path)
        logger.debug("Directory ensured: %s -> %s", name, path)

    logger.info("Directory structure ready for client '%s'", client)
    return paths
