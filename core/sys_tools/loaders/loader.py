import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def load_sql_files(path: Union[str, Path]):
    """Loads SQL files from a given path.

    Args:
        path (Union[str, Path]): Path to a file or directory containing SQL files.

    Raises:
        FileNotFoundError: If the given path does not exist.
        ValueError: If no SQL files are found in the given path.

    Returns:
        list[Path]: A list of Paths pointing to the SQL files found in the given path.

    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    sql_files = _collect_sql_files(path)
    if not sql_files:
        raise ValueError(f"No SQL files found in: {path}")
    logger.debug(f"Found {len(sql_files)} SQL files to process")
    return sql_files


def _collect_sql_files(path: Path) -> list[Path]:
    """Collects SQL files from a given path.

    This function checks if the given path is a file or directory, and if it is a directory, it processes all .sql files found in it (in a sorted order for consistent execution). If the given path is a file, it checks if the file has a .sql or .txt extension and raises an error if not. Finally, it logs the number of found SQL files and returns them.

    Args:
        path (Path): Path to a file or directory containing SQL files.

    Returns:
        list[Path]: A list of Paths pointing to the SQL files found in the given path.

    Raises:
        FileNotFoundError: If the given path does not exist.
        ValueError: If the given path is not a file or directory, or if no SQL files are found in the given path.
    """
    sql_files = []

    if path.is_dir():
        # Process all .sql files in directory (sorted for consistent execution order)
        sql_files = sorted(path.glob("*.sql"))
        # Also check for .txt files with SQL content
        sql_files.extend(sorted(path.glob("*.txt")))
    elif path.is_file():
        if path.suffix.lower() not in [".sql", ".txt"]:
            raise ValueError("Only .sql or .txt files are supported")
        sql_files = [path]
    else:
        raise ValueError("Path must be a file or directory")

    logger.debug(f"Found {len(sql_files)} SQL files to process")
    return sql_files
