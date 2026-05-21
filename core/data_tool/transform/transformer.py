import jellyfish
import pandas as pd

from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


def _stringify(series: pd.Series) -> pd.Series:
    """
    Converts a pandas Series to a string type, filling any missing values with an empty string.

    Args:
        series (pd.Series): The series to be converted.

    Returns:
        pd.Series: The converted series.
    """
    return series.fillna("").astype(str)


def _date_parse(series: pd.Series, fmt: str) -> pd.Series:
    """
    Converts a pandas Series to a datetime type, using the given format.

    Args:
        series (pd.Series): The series to be converted.
        fmt (str): The format string to use for conversion.

    Returns:
        pd.Series: The converted series.
    """
    return pd.to_datetime(series, format=fmt, errors="coerce")


def _year(series: pd.Series) -> pd.Series:
    """
    Returns a pandas Series containing the year extracted from a datetime series.

    Args:
        series (pd.Series): The datetime series to extract the year from.

    Returns:
        pd.Series: A series containing the year extracted from the input series.
    """
    return series.dt.year.fillna("").astype(str)


def _month(series: pd.Series) -> pd.Series:
    """
    Returns a pandas Series containing the month extracted from a datetime series.

    Args:
        series (pd.Series): The datetime series to extract the month from.

    Returns:
        pd.Series: A series containing the month extracted from the input series.
    """
    return series.dt.month.fillna("").astype(str)


TRANSFORM_REGISTRY = {
    "stringify": _stringify,
    "year": _year,
    "month": _month,
}


def apply_transform(df: pd.DataFrame, spec: dict) -> pd.Series:
    """
    Applies a transform to a pandas Series.

    Args:
        df (pd.DataFrame): The DataFrame containing the column to be transformed.
        spec (dict): A dictionary containing the transform name and source column.

    Returns:
        pd.Series: The transformed series.

    Raises:
        KeyError: If the source column is not found in the DataFrame.
        ValueError: If the transform name is not recognized.

    """
    source_col = spec["from"]
    transform_name = spec["transform"]

    if source_col not in df.columns:
        logger.error("Transform failed. Column '%s' not found.", source_col)
        raise KeyError(f"Column not found: {source_col}")

    series = df[source_col]
    logger.debug("Applying transform '%s' on column '%s'", transform_name, source_col)

    # date_parse(fmt)
    if transform_name.startswith("date_parse"):
        fmt = transform_name[transform_name.find("(") + 1 : transform_name.find(")")]
        return _date_parse(series, fmt)

    if transform_name in TRANSFORM_REGISTRY:
        return TRANSFORM_REGISTRY[transform_name](series)

    logger.error("Unknown transform requested: %s", transform_name)
    raise ValueError(f"Unknown transform: {transform_name}")


def resolve_part(
    df: pd.DataFrame, part: str, schema: dict, derived_cols: list[str]
) -> pd.Series:
    """
    Resolves a DSL part into a pandas Series.

    Args:
        df (pd.DataFrame): The DataFrame containing the columns to resolve.
        part (str): The DSL part to resolve.
        schema (dict): A dictionary mapping column names to their corresponding positions.
        derived_cols (list[str]): A list of derived column names.

    Returns:
        pd.Series: The resolved pandas Series.

    Raises:
        ValueError: If the DSL part is invalid.

    """
    logger.debug("Resolving DSL part: %s", part)

    if ":" in part:
        op, val = part.split(":", 1)

        # soundex:name
        if op == "soundex":
            col = schema[val]
            logger.debug("Applying soundex on column '%s'", col)
            return df[col].fillna("").apply(lambda x: jellyfish.soundex(x) if x else "")

        # name:3 -> first 3 chars
        if val.isdigit():
            col = schema[op]
            logger.debug("Taking first %s chars from column '%s'", val, col)
            return df[col].fillna("").str[: int(val)]

        logger.error("Invalid DSL part: %s", part)
        raise ValueError(f"Invalid DSL part: {part}")

    # Derived field or special column
    if part in derived_cols or part.lower() == "masked_id":
        return df[part].fillna("").astype(str)

    # Base schema field
    col = schema[part]
    return df[col].fillna("").astype(str)


def get_derived_fields(
    df: pd.DataFrame, tokenizer_schema: dict, derived_specs: dict
) -> pd.DataFrame:
    """
    Generates derived fields from the given dataframe based on the given tokenizer schema and derived field specifications.

    Args:
        df (pd.DataFrame): The dataframe to generate derived fields from.
        tokenizer_schema (dict): The tokenizer schema.
        derived_specs (dict): The derived field specifications.

    Returns:
        pd.DataFrame: The dataframe with the generated derived fields.

    Notes:
        1. If no derived fields are configured, the original dataframe is returned.
        2. The derived field specifications are in the format {"field_name": {"from": "source_column", "transform": "transformDSL"}}.
        3. The derived fields are generated by applying the transform DSL to the source column.
    """
    if not derived_specs:
        logger.info("No derived fields configured.")
        return df

    logger.info("Generating %d derived fields", len(derived_specs))

    for field_name, spec in derived_specs.items():
        source_key = spec["from"]
        source_col = tokenizer_schema.get(source_key, source_key)

        local_spec = {"from": source_col, "transform": spec["transform"]}

        logger.debug("Creating derived field '%s' from '%s'", field_name, source_col)
        df[field_name] = apply_transform(df, local_spec)

    logger.info("Derived fields generation completed.")
    return df
