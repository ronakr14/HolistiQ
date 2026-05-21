import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataFileManager:
    """Manager for loading and caching reference data files."""

    def __init__(self, data_directory: str = "static"):
        """
        Initializes the DataFileManager with the given data directory.

        Args:
            data_directory (str, optional): Path to the data directory. Defaults to "static".
        """

        self.data_directory = Path(data_directory).resolve()
        self._cache: dict[str, pd.DataFrame] = {}

    def load_reference_data(
        self, filename: str, separator: str = "|"
    ) -> Optional[pd.DataFrame]:
        """
        Loads a reference data file from the data directory and caches it.

        Args:
            filename (str): Name of the reference data file.
            separator (str, optional): Separator used in the file. Defaults to "|".

        Returns:
            Optional[pd.DataFrame]: Loaded DataFrame if successful, None otherwise.
        """
        cache_key = f"{filename}_{separator}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        file_path = self.data_directory / filename

        if not file_path.exists():
            logger.warning(f"Reference file not found: {file_path}")
            return None

        try:
            df = pd.read_csv(file_path, sep=separator)
            self._cache[cache_key] = df
            logger.info(f"Loaded reference data: {filename}")
            return df
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return None

    def get_random_record(
        self, filename: str, separator: str = "|"
    ) -> Optional[pd.Series]:
        """
        Retrieves a random record from the given reference data file.

        Args:
            filename (str): Name of the reference data file.
            separator (str, optional): Separator used in the file. Defaults to "|".

        Returns:
            Optional[pd.Series]: A random record from the reference data file if successful, None otherwise.
        """
        df = self.load_reference_data(filename, separator)
        if df is not None and not df.empty:
            return df.sample(n=1).iloc[0]
        return None

    def clear_cache(self):
        """
        Clears the cache of loaded reference data files.

        This function is intended to be used when the program needs to free up memory or when the reference data files have changed.
        It will automatically be called when the program terminates.

        Returns:
            None
        """
        self._cache.clear()
