import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file operations for data generation."""

    SUPPORTED_FORMATS = {
        "csv": (",", False),
        "tsv": ("\t", False),
        "ttxt": ("\t", False),
        "psv": ("|", False),
        "ptxt": ("|", False),
        "parquet": (None, True),
    }

    @classmethod
    def merge_csv_files(cls, temp_directory: str, output_path: str) -> None:
        """Merge temporary CSV files into a single file."""
        with open(output_path, "w") as target:
            temp_files = sorted(os.listdir(temp_directory))
            for i, temp_file in enumerate(temp_files):
                temp_file_path = os.path.join(temp_directory, temp_file)
                with open(temp_file_path, "r") as temp:
                    if i == 0:
                        target.write(temp.read())
                    else:
                        temp.readline()  # Skip header
                        target.write(temp.read())
        logger.info(f"Merged files into {output_path}")

    @classmethod
    def convert_to_format(
        cls, csv_path: str, target_format: str, destination_folder: str
    ) -> str:
        """Convert CSV file to target format."""
        base_path = csv_path.rsplit(".", 1)[0]

        if target_format not in cls.SUPPORTED_FORMATS:
            logger.warning(f"Unsupported format {target_format}, keeping CSV")
            return csv_path

        df = pd.read_csv(csv_path)

        if target_format == "parquet":
            output_path = f"{base_path}.parquet"
            df.to_parquet(output_path, engine="pyarrow", compression="snappy")
        else:
            separator, _ = cls.SUPPORTED_FORMATS[target_format]
            extension = "txt" if target_format in ["ttxt", "ptxt"] else target_format
            output_path = f"{base_path}.{extension}"
            df.to_csv(output_path, sep=separator, index=False)

        # Remove original CSV if conversion was successful
        if target_format != "csv":
            os.remove(csv_path)
            logger.info(f"Removed {csv_path} after converting to {target_format}")

        logger.info(f"Created {output_path}")
        return output_path
