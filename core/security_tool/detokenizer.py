import numpy as np
import pandas as pd

from core.observe.logger_factory.logging_util import get_logger
from core.utils.utils import _new_uuid, now_ts

logger = get_logger(__name__)


def build_token_rows(token_df: pd.DataFrame, cfg: dict):
    """
    Builds a dataframe of token rows from a given token dataframe

    Args:
        token_df (pd.DataFrame): The dataframe of tokens
        cfg (dict): The configuration dictionary

    Returns:
        pd.DataFrame: The dataframe of token rows
    """
    tdetoken = token_df[cfg["detokenizer_schema"]["process_cols"]].copy()
    tdetoken["create_date"] = now_ts()
    tdetoken["leadingtoken"] = None
    tdetoken["alt_tokenid"] = None
    tdetoken["ismapped"] = 0
    tdetoken["detokenid"] = None
    tdetoken["selectedtokenorder"] = None

    return tdetoken


def apply_token_config(tdetoken, tokencfg):
    """
    Applies the token configuration to the token dataframe

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens
        tokencfg (pd.DataFrame): The token configuration dataframe

    Returns:
        pd.DataFrame: The dataframe of tokens with the token configuration applied
    """
    tokencfg = tokencfg[["name"]].rename(columns={"name": "token_name"})
    tokencfg["order"] = tokencfg["token_name"].str.extract(r"_(\d+)$").astype(int)
    tokencfg = tokencfg.sort_values("order").reset_index(drop=True)
    order_map = tokencfg.set_index("token_name")["order"]
    tdetoken["selectedtokenorder"] = tdetoken["token_name"].map(order_map)
    return tdetoken


def clean_invalid_tokens(tdetoken):
    """
    Cleans the invalid tokens in the token dataframe

    The function takes a dataframe of tokens and returns a new dataframe
    with the invalid tokens removed.

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens

    Returns:
        pd.DataFrame: The dataframe of tokens with the invalid tokens removed
    """
    mask = tdetoken["token_hash"].str.contains("XXX", case=False, na=False)
    tdetoken.loc[mask, "token_hash"] = None
    return tdetoken


def remove_do_not_merge(tdetoken, donotmerge):
    """
    Removes the tokens that are not meant to be merged from the token dataframe.

    The function takes a dataframe of tokens and a dataframe of tokens that are not meant to be merged.
    It returns a new dataframe with the tokens that are not meant to be merged removed.

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens
        donotmerge (pd.DataFrame): The dataframe of tokens that are not meant to be merged

    Returns:
        pd.DataFrame: The dataframe of tokens with the tokens that are not meant to be merged removed
    """
    donot = set(donotmerge["tokenid"].astype(str))
    return tdetoken[~tdetoken["tokenid"].isin(donot)].reset_index(drop=True)


def update_create_date_from_crosswalk(tdetoken, token_crosswalk):
    """
    Updates the create date of the token dataframe from the crosswalk dataframe

    This function takes a dataframe of tokens and a dataframe of crosswalk data.
    It updates the create date of the token dataframe from the crosswalk dataframe.
    If the token is not found in the crosswalk dataframe, the create date is not updated.

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens
        token_crosswalk (pd.DataFrame): The dataframe of crosswalk data

    Returns:
        pd.DataFrame: The dataframe of tokens with the create date updated
    """
    scw_map = token_crosswalk.set_index("tokenid")["startdate"].to_dict()

    tdetoken["create_date"] = tdetoken.apply(
        lambda r: scw_map.get(r["tokenid"], r["create_date"]), axis=1
    )
    return tdetoken


def valid_mask(tdetoken):
    """
    Returns a boolean mask of valid tokens in the token dataframe

    A valid token is one that has a non-NA token hash, is not equal to "missing token" (case-insensitive), and does not contain "XXX" (case-insensitive)

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens

    Returns:
        pd.Series: A boolean mask of valid tokens in the token dataframe
    """
    valid_mask = (
        tdetoken["token_hash"].notna()
        & (tdetoken["token_hash"].str.lower() != "missing token")
        & (~tdetoken["token_hash"].str.contains("XXX", case=False, na=False))
    )

    valid = tdetoken[valid_mask].copy()
    return valid


def derive_alt_tokenid(tdetoken):
    """
    Derives alternative token IDs from the token dataframe.

    The function takes a dataframe of tokens and returns a new dataframe with an additional column "alt_tokenid".
    The "alt_tokenid" column is derived by sorting the valid tokens by their token hash, create date, and token ID in descending order.
    Then, for each group of tokens with the same token hash, the first token ID is taken as the alternative token ID.
    If the token is not valid or does not have a selected token order, its alternative token ID is not updated.

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens

    Returns:
        pd.DataFrame: The dataframe of tokens with the alternative token ID column
    """
    valid = valid_mask(tdetoken)
    valid = valid.sort_values(
        ["token_hash", "create_date", "tokenid"], ascending=[True, True, False]
    )

    first = valid.groupby("token_hash", sort=False).first().reset_index()
    first_map = first.set_index(["token_hash", "selectedtokenorder"])[
        "tokenid"
    ].to_dict()

    def pick_alt(row):
        """
        Picks an alternative token ID from the first_map dictionary.

        If the row's token hash is NaN, it returns the row's alternative token ID.
        If the row's token hash and selected token order has a matching candidate
        in the first_map dictionary and the candidate is not the same as the row's
        token ID, it returns the candidate.
        Otherwise, it returns the row's alternative token ID.
        """
        key = (row["token_hash"], row["selectedtokenorder"])
        candidate = first_map.get(key)
        if pd.isna(row["token_hash"]):
            return row["alt_tokenid"]
        if candidate and candidate != row["tokenid"]:
            return candidate
        return row["alt_tokenid"]

    tdetoken["alt_tokenid"] = tdetoken.apply(pick_alt, axis=1)
    return tdetoken


def select_best_token_per_tokenid(tdetoken):
    """
    Selects the best token per token ID from the given dataframe.

    The best token is defined as the token with the lowest selected token order, the earliest create date, and the lowest alternative token ID.
    If a token does not have a selected token order, it is given a selected token order of 999999.
    If a token does not have an alternative token ID, it is given an alternative token ID of NaN.
    The tokens are sorted by the token ID, alternative token ID string, selected token order, and create date in ascending order.
    The first token in each group of tokens with the same token ID is selected as the best token.
    The best tokens are returned in a new dataframe with the columns "alt_key", "alt_key_str", "sel_order_f", and "rownum_for_best" dropped.

    Args:
        tdetoken (pd.DataFrame): The dataframe of tokens

    Returns:
        pd.DataFrame: The dataframe of best tokens per token ID
    """
    tdetoken = valid_mask(tdetoken)
    tdetoken["alt_key"] = tdetoken["alt_tokenid"].apply(
        lambda x: (1, "") if pd.isna(x) else (0, str(x))
    )
    tdetoken["alt_key_str"] = tdetoken["alt_key"].apply(lambda t: f"{t[0]}_{t[1]}")
    tdetoken["sel_order_f"] = tdetoken["selectedtokenorder"].fillna(999999)

    tdetoken = tdetoken.sort_values(
        ["tokenid", "alt_key_str", "sel_order_f", "create_date"]
    )

    tdetoken["rownum_for_best"] = tdetoken.groupby("tokenid").cumcount() + 1

    finall = tdetoken[
        tdetoken["token_hash"].notna() & (tdetoken["rownum_for_best"] == 1)
    ].copy()

    return finall.drop(
        columns=["alt_key", "alt_key_str", "sel_order_f", "rownum_for_best"]
    )


def resolve_detokenid(finall, token_crosswalk):
    """
    Resolves the de-tokenized ID for each token in the given dataframe.

    The function takes a dataframe of tokens and a dataframe of crosswalk data.
    It resolves the de-tokenized ID for each token by first looking up the alternative token ID in the crosswalk dataframe.
    If the alternative token ID is not found, it looks up the token ID in the crosswalk dataframe.
    If neither the alternative token ID nor the token ID is found, it generates a new UUID for the de-tokenized ID.

    Args:
        finall (pd.DataFrame): The dataframe of tokens
        token_crosswalk (pd.DataFrame): The dataframe of crosswalk data

    Returns:
        pd.DataFrame: The dataframe of tokens with the resolved de-tokenized ID
    """
    scw_map = token_crosswalk.set_index("tokenid")["detokenid"].to_dict()

    finall["detokenid"] = finall.apply(
        lambda r: scw_map.get(r["alt_tokenid"], r["detokenid"]), axis=1
    )

    finall["detokenid"] = finall.apply(
        lambda r: (
            scw_map.get(r["tokenid"], r["detokenid"])
            if pd.isna(r["detokenid"])
            else r["detokenid"]
        ),
        axis=1,
    )

    mask = finall["detokenid"].isna() & finall["alt_tokenid"].isna()
    finall.loc[mask, "detokenid"] = [_new_uuid() for _ in range(mask.sum())]

    pid_to_detoken = (
        finall.dropna(subset=["detokenid"]).set_index("tokenid")["detokenid"].to_dict()
    )

    def propagate(row):
        """
        Propagates the de-tokenized ID from the token dataframe to the token dataframe with resolved de-tokenized IDs.

        If the row's de-tokenized ID is NaN, it looks up the alternative token ID in the pid_to_detoken dictionary.
        If the alternative token ID is found, it returns the de-tokenized ID associated with the alternative token ID.
        Otherwise, it returns the row's de-tokenized ID.
        """
        if pd.isna(row["detokenid"]):
            return pid_to_detoken.get(row["alt_tokenid"], row["detokenid"])
        return row["detokenid"]

    finall["detokenid"] = finall.apply(propagate, axis=1)
    return finall


def identify_missing_token(tdetoken, tdetoken_finall, token_crosswalk, donotmerge):
    """
    Identifies the missing tokens in the de-tokenized data.

    The function first identifies the tokens with missing token hashes.
    It then filters out the tokens that are not present in either the token crosswalk or the final token dataframe.
    Finally, it combines the missing tokens from the de-tokenized data with the missing tokens from the do not merge dataframe and returns a dataframe with the missing tokens and their corresponding de-tokenized IDs.

    Args:
        tdetoken (pd.DataFrame): The de-tokenized data
        tdetoken_finall (pd.DataFrame): The final token dataframe with resolved de-tokenized IDs
        token_crosswalk (pd.DataFrame): The token crosswalk dataframe
        donotmerge (pd.DataFrame): The do not merge dataframe

    Returns:
        pd.DataFrame: A dataframe with the missing tokens and their corresponding de-tokenized IDs
    """
    cond_missing = (
        tdetoken["token_hash"].isna()
        | tdetoken["token_hash"].str.lower().eq("missing token")
        | tdetoken["token_hash"].str.contains("xxx", case=False, na=False)
    )

    scw_pids = set(token_crosswalk["tokenid"].astype(str))
    finall_pids = set(tdetoken_finall["tokenid"].astype(str))

    missing_from_tdetoken = set(tdetoken.loc[cond_missing, "tokenid"].astype(str))
    part1 = [
        pid
        for pid in missing_from_tdetoken
        if pid not in scw_pids and pid not in finall_pids
    ]

    if "enddate" in donotmerge.columns:
        sd = donotmerge.copy()
        sd["enddate"] = pd.to_datetime(sd["enddate"])
        part2 = sd[sd["enddate"].isna()]["tokenid"].astype(str).tolist()
    else:
        part2 = donotmerge["tokenid"].astype(str).tolist()

    missing_union = set(part1) | set(part2)
    return pd.DataFrame(
        {
            "tokenid": list(missing_union),
            "detokenid": [_new_uuid() for _ in range(len(missing_union))],
        }
    )


def build_new_detokenid_mapping(tdetoken_finall):
    """
    Builds a new mapping from the token dataframe with resolved de-tokenized IDs.

    The function groups the tokens by their alternative token ID, token hash, and selected token order.
    It then aggregates the de-tokenized IDs by taking the maximum de-tokenized ID for each group.
    Finally, it renames the de-tokenized ID column and returns the new mapping.

    Args:
        tdetoken_finall (pd.DataFrame): The token dataframe with resolved de-tokenized IDs

    Returns:
        pd.DataFrame: The new mapping from the token dataframe with resolved de-tokenized IDs
    """
    group_cols = ["alt_tokenid", "token_hash", "selectedtokenorder"]
    agg = (
        tdetoken_finall.groupby(group_cols, dropna=False)
        .agg({"detokenid": lambda s: s.dropna().max() if s.notna().any() else None})
        .reset_index()
    )
    new_detokenid = agg.rename(columns={"detokenid": "detokenid"})
    return new_detokenid


def upsert_detoken_crosswalk(detoken_crosswalk, new_detokenid):
    """
    Upersts new de-tokenized IDs from the given dataframe into the existing crosswalk dataframe.

    Args:
        detoken_crosswalk (pd.DataFrame): The existing crosswalk dataframe
        new_detokenid (pd.DataFrame): The dataframe of new de-tokenized IDs

    Returns:
        pd.DataFrame: The updated crosswalk dataframe with the new de-tokenized IDs
    """
    existing_ids = set(detoken_crosswalk["detokenid"].astype(str))
    to_insert_sc = new_detokenid[
        ["detokenid", "token_hash", "selectedtokenorder"]
    ].drop_duplicates()

    to_insert_sc = to_insert_sc[
        ~to_insert_sc["detokenid"].astype(str).isin(existing_ids)
    ]
    # append to crosswalk
    if not to_insert_sc.empty:
        to_insert_sc = to_insert_sc.rename(
            columns={
                "detokenid": "detokenid",
                "token_hash": "token_hash",
                "selectedtokenorder": "token_order",
            }
        )
        detoken_crosswalk = pd.concat(
            [detoken_crosswalk, to_insert_sc], ignore_index=True
        )

    return detoken_crosswalk


def upsert_token_crosswalk(token_crosswalk, new_detokenid, tdetoken_finall):
    """
    Upersts new de-tokenized IDs from the given dataframe into the existing token crosswalk dataframe.

    Args:
        token_crosswalk (pd.DataFrame): The existing token crosswalk dataframe
        new_detokenid (pd.DataFrame): The dataframe of new de-tokenized IDs
        tdetoken_finall (pd.DataFrame): The token dataframe with resolved de-tokenized IDs

    Returns:
        pd.DataFrame: The updated token crosswalk dataframe with the new de-tokenized IDs
    """
    sc_existing = set(
        (
            token_crosswalk["tokenid"].astype(str)
            + "||"
            + token_crosswalk["detokenid"].astype(str)
        )
    )
    joins = tdetoken_finall.merge(
        new_detokenid[["detokenid"]],
        left_on="detokenid",
        right_on="detokenid",
        how="inner",
    )
    to_insert_sp = joins[["tokenid", "detokenid"]].drop_duplicates()

    to_insert_sp = to_insert_sp[
        ~(
            to_insert_sp["tokenid"].astype(str)
            + "||"
            + to_insert_sp["detokenid"].astype(str)
        ).isin(sc_existing)
    ]
    to_insert_sp["startdate"] = now_ts()
    if not to_insert_sp.empty:
        token_crosswalk = pd.concat(
            [
                token_crosswalk,
                to_insert_sp.rename(
                    columns={"tokenid": "tokenid", "detokenid": "detokenid"}
                ),
            ],
            ignore_index=True,
        )

    return token_crosswalk


def insert_missing_tokens(missing_token, detoken_crosswalk, token_crosswalk):
    """
    Inserts missing tokens into the detokenized crosswalk and token crosswalk dataframes.

    The function first identifies the missing tokens that are not present in the detokenized crosswalk.
    It then inserts these missing tokens into the detokenized crosswalk dataframe.
    Finally, it inserts the missing tokens into the token crosswalk dataframe.

    Args:
        missing_token (pd.DataFrame): Dataframe containing the missing tokens
        detoken_crosswalk (pd.DataFrame): Dataframe containing the detokenized crosswalk data
        token_crosswalk (pd.DataFrame): Dataframe containing the token crosswalk data

    Returns:
        tuple: A tuple containing the updated detokenized crosswalk dataframe and the updated token crosswalk dataframe
    """
    missing_existing_ids = set(detoken_crosswalk["detokenid"].astype(str))
    to_insert_missing_sc = missing_token[
        ~missing_token["detokenid"].astype(str).isin(missing_existing_ids)
    ].copy()
    if not to_insert_missing_sc.empty:
        to_insert_missing_sc = to_insert_missing_sc.assign(
            token="missing token", tokenorder=np.nan
        ).rename(columns={"detokenid": "detokenid"})
        detoken_crosswalk = pd.concat(
            [
                detoken_crosswalk,
                to_insert_missing_sc[["detoken_id", "token_hash", "token_order"]],
            ],
            ignore_index=True,
        )

    sp_existing = set(
        (
            token_crosswalk["tokenid"].astype(str)
            + "||"
            + token_crosswalk["detokenid"].astype(str)
        )
    )
    to_insert_missing_sp = missing_token.copy()
    to_insert_missing_sp = to_insert_missing_sp[
        ~(
            to_insert_missing_sp["tokenid"].astype(str)
            + "||"
            + to_insert_missing_sp["detokenid"].astype(str)
        ).isin(sp_existing)
    ]
    to_insert_missing_sp["startdate"] = now_ts()
    if not to_insert_missing_sp.empty:
        token_crosswalk = pd.concat(
            [
                token_crosswalk,
                to_insert_missing_sp[["tokenid", "detokenid", "startdate"]],
            ],
            ignore_index=True,
        )

    return detoken_crosswalk, token_crosswalk


def close_old_detokenid_records(token_crosswalk):
    """
    Closes old de-tokenized ID records in the token crosswalk dataframe by setting their end date to the current timestamp if they do not have an end date.

    Args:
        token_crosswalk (pd.DataFrame): The token crosswalk dataframe

    Returns:
        pd.DataFrame: The updated token crosswalk dataframe with the old de-tokenized ID records closed
    """
    if "startdate" in token_crosswalk.columns:
        scw2 = token_crosswalk.copy()
        scw2["startdate"] = pd.to_datetime(scw2["startdate"])
        scw2 = scw2.sort_values(["tokenid", "startdate"], ascending=[True, False])

        scw2["rnk"] = scw2.groupby("tokenid").cumcount() + 1
        mask_r = (scw2["rnk"] > 1) & scw2["enddate"].isna()
        scw2.loc[mask_r, "enddate"] = now_ts()

        token_crosswalk = scw2.drop(columns=["rnk"])

    return token_crosswalk


def update_merge_history(merge_history, token_crosswalk):
    """
    Updates the merge history dataframe by adding new de-tokenized IDs to the merge history.

    Args:
        merge_history (pd.DataFrame): The merge history dataframe
        token_crosswalk (pd.DataFrame): The token crosswalk dataframe

    Returns:
        pd.DataFrame: The updated merge history dataframe with the new de-tokenized IDs
    """

    ended = token_crosswalk[token_crosswalk["enddate"].notna()][
        ["tokenid", "detokenid", "enddate"]
    ].copy()
    ended = ended.rename(columns={"detokenid": "old_detokenid", "enddate": "merge_dt"})

    hist_keys = set(
        (
            merge_history["tokenid"].astype(str)
            + "||"
            + merge_history["old_detokenid"].astype(str)
            + "||"
            + merge_history["merge_dt"].astype(str)
        )
    )
    to_hist = ended[
        ~(
            ended["tokenid"].astype(str)
            + "||"
            + ended["old_detokenid"].astype(str)
            + "||"
            + ended["merge_dt"].astype(str)
        ).isin(hist_keys)
    ].copy()
    to_hist["new_detokenid"] = None
    merge_history = pd.concat(
        [
            merge_history,
            to_hist[["tokenid", "old_detokenid", "new_detokenid", "merge_dt"]],
        ],
        ignore_index=True,
    )

    current_sc = token_crosswalk[token_crosswalk["enddate"].isna()][
        ["tokenid", "detokenid"]
    ].copy()
    cur_map = current_sc.set_index("tokenid")["detokenid"].to_dict()
    merge_history["new_detokenid"] = merge_history.apply(
        lambda r: cur_map.get(r["tokenid"], r["new_detokenid"]), axis=1
    )
    merge_history["new_detokenid"] = (
        merge_history["tokenid"].map(cur_map).fillna(merge_history["new_detokenid"])
    )


def update_patient_id_table(final_crosswalk, token_crosswalk):
    """
    Updates the patient ID table by assigning new patient IDs to the de-tokenized IDs
    in the token crosswalk dataframe based on the existing mapping in the final crosswalk dataframe.

    Args:
        final_crosswalk (pd.DataFrame): The final crosswalk dataframe
        token_crosswalk (pd.DataFrame): The token crosswalk dataframe

    Returns:
        pd.DataFrame: The updated patient ID table with the new patient IDs
    """
    token_crosswalk = token_crosswalk.copy()
    existing_map = dict(zip(final_crosswalk["detokenid"], final_crosswalk["id"]))

    def get_id(detokenid):
        if detokenid not in existing_map:
            if existing_map:
                existing_map[detokenid] = max(existing_map.values()) + 1
            else:
                existing_map[detokenid] = 1
        return existing_map[detokenid]

    token_crosswalk["id"] = token_crosswalk["detokenid"].map(get_id)
    df = token_crosswalk[["detokenid", "id"]]
    df = pd.concat([df, final_crosswalk], ignore_index=True).drop_duplicates()
    return df
