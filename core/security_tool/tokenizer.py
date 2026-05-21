import os
from pathlib import Path

import pandas as pd

from core.observe.logger_factory.logging_util import get_logger
from core.security.crypto.engine import hmac_token
from core.utils.utils import _generate_run_suffix, _new_uuid
from data.deidentification.data_loader import _load_crosswalk, _persist_crosswalk
from data.deidentification.transformer import resolve_part

logger = get_logger(__name__)


def token_enabled(token_cfg: dict, global_cfg: dict, client: str) -> bool:
    """
    Checks if a token is enabled for a given client.

    Args:
        token_cfg (dict): Token configuration
        global_cfg (dict): Global configuration
        client (str): Client name

    Returns:
        bool: Whether the token is enabled for the client
    """
    client_cfg = global_cfg["clients"][client.upper()]

    version_enabled = token_cfg["version"] in client_cfg["enabled_versions"]
    family_enabled = token_cfg["family"] in client_cfg["feature_flags"]

    enabled = version_enabled and family_enabled

    logger.debug(
        "Token '%s' v%s (family=%s) enabled=%s",
        token_cfg["name"],
        token_cfg["version"],
        token_cfg["family"],
        enabled,
    )

    return enabled


def get_masked_id(
    df: pd.DataFrame,
    tokenizer_schema: dict,
    token_length: int,
    path: Path,
) -> pd.DataFrame:
    """
    Generates a masked ID for each record in the given dataframe.

    Args:
        df (pd.DataFrame): Input dataframe
        tokenizer_schema (dict): Tokenizer schema
        token_length (int): Length of the token
        path (Path): Path to the directory containing the crosswalk file

    Returns:
        pd.DataFrame: Dataframe with the generated masked IDs

    Notes:
        1. Loads the existing crosswalk file
        2. Identifies new masked IDs and generates new token IDs
        3. Maps the PATID to the new token ID
        4. Persists the updated crosswalk file
    """
    crosswalk_path = path / "masked_id_crosswalk.csv"

    k_mask = os.getenv("K_MASK").encode()

    logger.info("Generating masked_id for %d records", len(df))

    # Ensure id column
    df = df.copy()
    df["id"] = df[tokenizer_schema["id"]].astype(str)

    df["masked_id"] = df["id"].apply(
        lambda x: hmac_token(k_mask, "MASK", x, length=token_length)
    )

    # Load existing crosswalk
    cw_df = _load_crosswalk(crosswalk_path)
    existing_map = dict(zip(cw_df["masked_id"], cw_df["tokenid"]))

    # Identify new masked_ids
    incoming_ids = set(df["masked_id"].unique())
    missing_ids = incoming_ids - set(existing_map.keys())

    if missing_ids:
        logger.info("Creating %d new tokenid's for unseen masked_ids", len(missing_ids))
        # new_map = {mid: uuid.uuid4().hex for mid in missing_ids}
        new_map = {mid: _new_uuid() for mid in missing_ids}
        existing_map.update(new_map)
    else:
        logger.debug("No new masked_ids detected.")

    # Map PATID
    df["tokenid"] = df["masked_id"].map(existing_map)

    # Persist updated crosswalk
    updated_cw = pd.concat(
        [cw_df, df[["id", "masked_id", "tokenid"]]],
        ignore_index=True,
    ).drop_duplicates(subset=["masked_id"])

    _persist_crosswalk(updated_cw, crosswalk_path)

    logger.info("Masked ID processing completed.")
    return df


def _build_raw_token_series(
    df: pd.DataFrame,
    parts_cfg: list[str],
    schema: dict,
    derived_fields: dict,
) -> pd.Series:
    """
    Builds a raw token series from a given dataframe and tokenizer configuration.

    Args:
        df (pd.DataFrame): Dataframe to build token series from
        parts_cfg (list[str]): List of parts to include in the token series
        schema (dict): Tokenizer schema
        derived_fields (dict): Derived fields configuration

    Returns:
        pd.Series: The raw token series
    """
    parts = [resolve_part(df, p, schema, derived_fields) for p in parts_cfg]

    raw = parts[0]
    for p in parts[1:]:
        raw = raw + p

    return raw


def build_tokens(
    df: pd.DataFrame,
    cfg: dict,
    path: Path,
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """
    Builds token series for a given dataframe and tokenizer configuration.

    Args:
        df (pd.DataFrame): Dataframe to build token series from
        cfg (dict): Tokenizer configuration
        path (Path): Path to output token files

    Returns:
        tuple[pd.DataFrame, list[pd.DataFrame]]: Tuple containing the updated dataframe and a list of token dataframes
    """
    client = cfg["client"]
    schema = cfg["tokenizer_schema"]
    derived_fields = cfg.get("derived_fields", {})
    token_length = cfg["token_length"]

    k_deriv = os.getenv(f"K_DERIVE_{client.upper()}").encode()

    token_frames = []
    enabled_count = 0

    logger.info("Building tokens for client '%s'", client)

    for token_cfg in cfg["tokens_cfg"]:
        if not token_enabled(token_cfg, cfg, client):
            logger.debug("Skipping token '%s' (disabled)", token_cfg["name"])
            continue

        enabled_count += 1

        logger.debug(
            "Processing token '%s' v%s", token_cfg["name"], token_cfg["version"]
        )

        raw_series = _build_raw_token_series(
            df, token_cfg["parts"], schema, derived_fields
        )

        enc_series = raw_series.apply(
            lambda x: hmac_token(k_deriv, client, x, length=token_length)
        )

        token_df = df[["tokenid"]].assign(
            token_name=token_cfg["name"],
            token_version=token_cfg["version"],
            token_family=token_cfg["family"],
            token_hash=enc_series,
        )

        token_frames.append(token_df)

    logger.info(
        "Token generation completed. Enabled tokens: %d, Output sets: %d",
        enabled_count,
        len(token_frames),
    )
    _write_tokens(
        token_frames,
        path,
        cfg.get("token_file_prefix", "TOKEN"),
        cfg.get("file_format", "csv"),
    )
    logger.info("Tokenization stage complete (token_sets=%d)", len(token_frames))

    return df


def mask_phi_data(
    df: pd.DataFrame,
    schema: dict,
    derived_keys: dict,
    path: Path,
    file_prefix: str,
    file_format: str,
) -> pd.DataFrame:
    """
    Applies binary PHI masking to a given dataframe.

    Args:
        df (pd.DataFrame): DataFrame to apply PHI masking to
        schema (dict): Tokenizer schema
        derived_keys (dict): Derived fields configuration
        path (Path): Path to output masked PHI data
        file_prefix (str): Prefix for output file
        file_format (str): File format for output file

    Returns:
        pd.DataFrame: DataFrame with PHI masking applied
    """
    df = df.copy()

    phi_cols = list(schema.values())

    logger.info("Applying binary PHI masking for %d columns", len(phi_cols))

    # Binary presence mask
    df[phi_cols] = df.reindex(columns=phi_cols).notna().astype(int)

    # Replace DOB with year
    if "dob_year" in df.columns:
        df[schema["dob"]] = df["dob_year"]
        logger.debug("DOB replaced with dob_year")

    # Drop sensitive / intermediate columns
    drop_cols = list(derived_keys.keys())
    drop_cols += ["masked_id", schema["id"]]

    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    logger.info("PHI masking completed. Remaining columns: %d", len(df.columns))

    _write_mask_phi_data(df, path, file_prefix, file_format)
    return df


def _write_mask_phi_data(
    df, output_dir: Path, file_prefix: str, file_format: str
) -> Path:
    """
    Writes the given DataFrame to a file in the given output directory with a generated suffix and file format.

    Args:
        df (pd.DataFrame): DataFrame to write to file
        output_dir (Path): Output directory to write file to
        file_prefix (str): Prefix for output file
        file_format (str): File format for output file

    Returns:
        Path: Path to the written file
    """
    if df.empty:
        logger.warning("No token frames generated. Skipping token file write.")
        return None

    suffix = _generate_run_suffix()

    output_path = output_dir / f"{file_prefix}_{suffix}.{file_format}"
    logger.info(f"Writing phi file -> {output_path} (rows={df.shape[0]})")

    df.to_csv(output_path, sep="|", index=False)
    return output_path


def _write_tokens(
    token_frames, output_dir: Path, file_prefix: str, file_format: str
) -> Path:
    """
    Writes the given token frames to a file in the given output directory with a generated suffix and file format.

    Args:
        token_frames (list[pd.DataFrame]): List of token frames to write to file
        output_dir (Path): Output directory to write file to
        file_prefix (str): Prefix for output file
        file_format (str): File format for output file

    Returns:
        Path: Path to the written file
    """
    if not token_frames:
        logger.warning("No token frames generated. Skipping token file write.")
        return None

    suffix = _generate_run_suffix()

    output_path = output_dir / f"{file_prefix}_{suffix}.{file_format}"
    combined = pd.concat(token_frames, ignore_index=True)

    logger.info(
        "Writing token file -> %s (rows=%d)",
        output_path,
        len(combined),
    )

    combined.to_csv(output_path, sep="|", index=False)
    return output_path
