from pathlib import Path

import pandas as pd

from core.infrastructure.observability.logging.logging_util import get_logger
from core.utils.file_utils import generate_datetime_suffix, get_latest_file, move_file
from core.services.extraction.file_readers.csv_data import load_csv_to_df

logger = get_logger(__name__)


def validate_deid_rawdata_schema(
    df: pd.DataFrame, tokenizer_schema: dict, file_path: Path
) -> list[str]:
    """
    Validates the given DataFrame to ensure it has all columns required by the given tokenizer schema.

    Args:
        df (pd.DataFrame): DataFrame to validate
        tokenizer_schema (dict): Tokenizer schema
        file_path (Path): Path to the file being validated

    Returns:
        list[str]: List of extra columns found in the DataFrame

    Raises:
        KeyError: If the DataFrame is missing required columns
    """
    required_cols = set(tokenizer_schema.values())
    df_cols = set(df.columns)

    missing = required_cols - df_cols
    if missing:
        logger.error("File %s missing required columns: %s", file_path.name, missing)
        raise KeyError(f"{file_path.name} missing columns: {missing}")

    extra = df_cols - required_cols
    if extra:
        logger.info("File %s contains extra columns: %s", file_path.name, extra)

    logger.debug("Schema validation passed for %s", file_path.name)
    return list(extra)


def load_deid_raw_data(
    directory: str, tokenizer_schema: dict, file_format: str, archive: str = None
) -> pd.DataFrame:
    """
    Loads all raw files from a given directory and validates them against the given tokenizer schema.

    Args:
        directory (str): Directory to load files from
        tokenizer_schema (dict): Tokenizer schema
        file_format (str): File format to load (e.g. csv, json)
        archive (str, optional): Directory to archive loaded files to

    Returns:
        pd.DataFrame: Concatenated DataFrame containing all loaded and validated data
    """

    dir_path = Path(directory)

    required_cols = list(tokenizer_schema.values())
    dfs = []

    files = list(dir_path.glob(f"*.{file_format}"))
    if not files:
        logger.warning("No %s files found in %s", file_format, directory)
        return pd.DataFrame(columns=required_cols)

    logger.info("Found %d raw files in %s", len(files), directory)

    for file_path in files:
        df_tmp = load_csv_to_df(file_path, file_format)
        extra_cols = validate_deid_rawdata_schema(df_tmp, tokenizer_schema, file_path)

        selected_cols = required_cols + extra_cols
        dfs.append(df_tmp[selected_cols])
        if archive:
            archive_path = Path(archive) / generate_datetime_suffix() / file_path.name
            move_file(file_path, archive_path)

    combined_df = pd.concat(dfs, ignore_index=True)
    logger.info("Raw data loaded. Total rows: %d", len(combined_df))

    return combined_df


def _load_crosswalk(path: Path) -> pd.DataFrame:
    """
    Loads a crosswalk file from the given path and returns the associated DataFrame.

    Args:
        path (Path): Path to the crosswalk file

    Returns:
        pd.DataFrame: DataFrame containing the crosswalk data
    """
    crosswalk = {
        "masked_id_crosswalk": ["id", "masked_id", "tokenid"],
        "token_crosswalk": ["tokenid", "detokenid", "startdate", "enddate"],
        "detoken_crosswalk": ["detokenid", "token_hash", "token_order"],
        "donotmerge": ["tokenid", "insertdate"],
        "merge_history": ["tokenid", "old_detokenid", "new_detokenid", "merge_dt"],
        "final_crosswalk": ["detokenid", "id"],
    }

    filename = Path(path).stem

    if not path.exists():
        logger.warning(f"{filename} not found. Initializing new file: {path}")
        return pd.DataFrame(columns=crosswalk[filename])

    logger.info(f"Loading: {filename}")
    df = pd.read_csv(path, dtype=str, sep="|")
    return df[crosswalk[filename]].drop_duplicates()


def persist_crosswalk(crosswalk: dict, path: Path):
    """
    Persist the crosswalk data to the given path.

    Args:
        crosswalk (dict): Dictionary containing the crosswalk data
        path (Path): Path to persist the crosswalk data

    """
    for name, df in crosswalk.items():
        if (
            "crosswalk" in name.lower() or "merge_history" == name.lower()
        ) and df is not None:
            _persist_crosswalk(df, path / f"{name}.csv")


def _persist_crosswalk(crosswalk: pd.DataFrame, path: Path):
    """
    Persist the crosswalk data to the given path.

    Args:
        crosswalk (pd.DataFrame): DataFrame containing the crosswalk data
        path (Path): Path to persist the crosswalk data

    """
    filename = Path(path).stem
    logger.info(f"Persisting {filename} ({len(crosswalk)} records) -> {path}")
    crosswalk.to_csv(path, sep="|", index=False)


def load_deid_detokenized_data(paths: dict, token_file_prefix: str, token_cfg: dict):
    """
    Loads de-identified, detokenized data from the given paths and configuration.

    Args:
        paths (dict): Dictionary containing the paths to the output and master directories
        token_file_prefix (str): Prefix for the token file
        token_cfg (dict): Token configuration

    Returns:
        dict: Dictionary containing the loaded data for each file
    """
    token_file_path = get_latest_file(paths["output"], token_file_prefix)
    token = pd.read_csv(token_file_path, sep="|", dtype=str)
    tokencfg = pd.DataFrame(token_cfg)
    donotmerge = _load_crosswalk(paths["master"] / "donotmerge.csv")
    detoken_crosswalk = _load_crosswalk(paths["master"] / "detoken_crosswalk.csv")
    token_crosswalk = _load_crosswalk(paths["master"] / "token_crosswalk.csv")
    token_crosswalk["startdate"] = pd.to_datetime(token_crosswalk["startdate"])
    token_crosswalk["enddate"] = pd.to_datetime(token_crosswalk["enddate"])
    merge_history = _load_crosswalk(paths["master"] / "merge_history.csv")
    final_crosswalk = _load_crosswalk(paths["master"] / "final_crosswalk.csv")

    return {
        "token": token,
        "tokencfg": tokencfg,
        "donotmerge": donotmerge,
        "detoken_crosswalk": detoken_crosswalk,
        "token_crosswalk": token_crosswalk,
        "merge_history": merge_history,
        "final_crosswalk": final_crosswalk,
    }
