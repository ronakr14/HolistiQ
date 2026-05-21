from dataclasses import dataclass


@dataclass
class DataGenerationConfig:
    """Configuration for data generation parameters."""

    columns: int = 1
    rows: int = 1
    distribution: str = "uniform"
    file_format: str = "csv"
    destination_folder: str = ".output"
    chunk_size: int = 10000
    datatype_dict: dict[str, int] = {"int4": 0}
