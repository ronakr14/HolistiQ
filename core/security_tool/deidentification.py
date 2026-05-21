from core.config.loader import validate_load_config
from core.infrastructure.observability.logging.logging_util import get_logger
from data.deidentification.data_loader import (
    load_deid_detokenized_data,
    load_deid_raw_data,
    persist_crosswalk,
)
from data.deidentification.detokenizer import (
    apply_token_config,
    build_new_detokenid_mapping,
    build_token_rows,
    clean_invalid_tokens,
    close_old_detokenid_records,
    derive_alt_tokenid,
    identify_missing_token,
    insert_missing_tokens,
    remove_do_not_merge,
    resolve_detokenid,
    select_best_token_per_tokenid,
    update_create_date_from_crosswalk,
    update_merge_history,
    update_patient_id_table,
    upsert_detoken_crosswalk,
    upsert_token_crosswalk,
)
from data.deidentification.tokenizer import build_tokens, get_masked_id, mask_phi_data
from data.deidentification.transformer import get_derived_fields
from data.deidentification.utils import resolve_deid_directories

logger = get_logger(__name__)


def deidentify_data(ctx: dict):
    """
    Main entry point for the de-identification pipeline.

    Args:
        ctx (dict): Context containing configuration and input data.

    Returns:
        None

    Notes:
        1. Validates the configuration for the de-identification pipeline.
        2. Resolves the directory structure for the given client.
        3. Loads raw data from the input directory.
        4. Computes derived fields based on the tokenizer schema.
        5. Generates masked IDs and PATIDs.
        6. Builds tokens from the raw data.
        7. Masks PHI data from the tokens.
        8. Logs the number of rows and columns at each stage of the pipeline.
        9. Saves the de-identified data to the output directory.
    """
    logger.info("Starting de-identification pipeline")
    config = validate_load_config(ctx.config, "deid")["deid"]
    client = config["client"]
    logger.info(f"Configuration validated for client {client}")
    paths = resolve_deid_directories(config["data_path"], client)
    df = load_deid_raw_data(
        paths["raw"],
        config["tokenizer_schema"],
        config["file_format"],
        paths["archive"],
    )
    if df.empty:
        logger.warning("No input data found. Pipeline exiting early.")
        logger.info("rows_in: 0, rows_out: 0, token_file: None)")
    logger.info("Raw data loaded (rows=%d, cols=%d)", len(df), len(df.columns))
    df = get_derived_fields(
        df, config["tokenizer_schema"], config.get("derived_fields", {})
    )
    logger.info("Derived fields applied")
    df = get_masked_id(
        df, config["tokenizer_schema"], config["token_length"], paths["master"]
    )
    logger.info("Masked IDs and PATIDs generated")
    df = build_tokens(df, config, paths["output"])
    df = mask_phi_data(
        df,
        config["tokenizer_schema"],
        config.get("derived_fields", {}),
        paths["output"],
        config.get("masked_file_prefix", "deidentified"),
        config.get("file_format", "csv"),
    )
    logger.info("De-identification pipeline completed successfully")


def identify_data(ctx: dict):
    """
    Identifies PHI data in the de-identified data.

    The identification pipeline takes the de-identified data and identifies the PHI data.
    It does this by:

    1. loading the de-identified data.
    2. computing the invalid tokens.
    3. deriving the alternative token IDs.
    4. resolving the de-identified IDs.
    5. upserting the de-identified data.
    6. inserting the missing tokens.
    7. closing the old de-identified records.
    8. updating the merge history.
    9. updating the patient ID table.
    10. persisting the crosswalk data.

    Args:
        ctx (dict): The ctx object with the configuration and paths.

    Returns:
        None
    """
    logger.info("Starting identification pipeline")
    config = validate_load_config(ctx.config, "deid")["deid"]
    client = config["client"]
    logger.info(f"Configuration validated for client {client}")
    paths = resolve_deid_directories(config["data_path"], client)
    data = load_deid_detokenized_data(
        paths, config["token_file_prefix"], config["tokens_cfg"]
    )

    tdetoken = build_token_rows(data["token"], config)
    tdetoken = apply_token_config(tdetoken, data["tokencfg"])
    tdetoken = clean_invalid_tokens(tdetoken)
    tdetoken = remove_do_not_merge(tdetoken, data["donotmerge"])
    tdetoken = update_create_date_from_crosswalk(tdetoken, data["token_crosswalk"])
    tdetoken = derive_alt_tokenid(tdetoken)
    tdetoken_finall = select_best_token_per_tokenid(tdetoken)
    tdetoken_finall = resolve_detokenid(tdetoken_finall, data["token_crosswalk"])
    missing_token = identify_missing_token(
        tdetoken, tdetoken_finall, data["token_crosswalk"], data["donotmerge"]
    )
    new_detokenid = build_new_detokenid_mapping(tdetoken_finall)

    data["detoken_crosswalk"] = upsert_detoken_crosswalk(
        data["detoken_crosswalk"], new_detokenid
    )
    data["token_crosswalk"] = upsert_token_crosswalk(
        data["token_crosswalk"], new_detokenid, tdetoken_finall
    )

    data["detoken_crosswalk"], data["token_crosswalk"] = insert_missing_tokens(
        missing_token, data["detoken_crosswalk"], data["token_crosswalk"]
    )

    data["token_crosswalk"] = close_old_detokenid_records(data["token_crosswalk"])
    data["merge_history"] = update_merge_history(
        data["merge_history"], data["token_crosswalk"]
    )

    data["final_crosswalk"] = update_patient_id_table(
        data["final_crosswalk"], data["token_crosswalk"]
    )
    persist_crosswalk(data, paths["master"])
    logger.info("Identification pipeline completed successfully")
