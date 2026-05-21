from pathlib import Path
from core.infrastructure.observability.logging.logging_util import get_logger

import pandas as pd

logger = get_logger(__name__)


def load_csv_to_df(file_path: Path) -> pd.DataFrame:
    """
    Reads a file into a pandas DataFrame based on the given file format.

    Args:
        file_path (Path): Path to the file to read

    Returns:
        pd.DataFrame: DataFrame containing the read data

    Raises:
        ValueError: If the file format is not supported
    """
    logger.info("Reading file: %s", file_path.name)

    return pd.read_csv(file_path, dtype=str)