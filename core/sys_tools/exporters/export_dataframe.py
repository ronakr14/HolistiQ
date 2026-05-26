from pathlib import Path
from custom_logger.logging_util import get_logger
from core.sys_tools.directory_utils import ensure_dir

import pandas as pd

logger = get_logger(__name__)


def dataframe_to_file(
    df: pd.DataFrame, filepath: Path, file_format: str, seperator: str
):
    """
    Writes a pandas DataFrame to a file based on the given file format.

    Args:
        df (pd.DataFrame): DataFrame to write to file
        filename (Path): Path to the file to write
        file_format (str): File format to write (e.g. "csv")
        seperator (str): Seperator to use when writing the file

    Raises:
        ValueError: If the file format is not supported
    """
    ensure_dir(filepath)
    if file_format == "csv":
        df.to_csv(f"{filepath}.{file_format}", index=False, sep=seperator)
    else:
        logger.error("Unsupported file format: %s", file_format)
        raise ValueError(f"Unsupported file format: {file_format}")