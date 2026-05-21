import sys
from itertools import zip_longest
from typing import Any, Dict, Iterator, List, Optional, Union

from libs.mixers.logger_mixin import get_logger

logger = get_logger("Row Col", component="Utils")


def columns_to_rows(
    data: Dict[str, List[Any]],
    fill_missing: Optional[Any] = None,
    strict_length: bool = True,
) -> List[Dict[str, Any]]:
    """
    Convert column data to row data.

    Args:
        data (Dict[str, List[Any]]): Dictionary of columns
        fill_missing (Optional[Any], optional): Value to fill in for missing data
        strict_length (bool, optional): Enforce consistent lengths across columns

    Raises:
        TypeError: If data is not a dictionary or values are not lists/tuples
        ValueError: If column lengths are inconsistent and strict_length is True

    Returns:
        List[Dict[str, Any]]: List of row dictionaries
    """
    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary")

    if not data:
        logger.debug("Empty data provided, returning empty list")
        return []

    logger.debug(f"Converting {len(data)} columns to rows")

    # Validate input data
    column_lengths = {}
    for key, values in data.items():
        if not isinstance(values, (list, tuple)):
            raise TypeError(
                f"Column '{key}' must be a list or tuple, got {type(values)}"
            )
        column_lengths[key] = len(values)

    # Check for consistent lengths
    lengths = set(column_lengths.values())
    if len(lengths) > 1:
        if strict_length:
            raise ValueError(
                f"Columns have mismatched lengths: {column_lengths}. "
                f"Set strict_length=False to pad with fill_missing value."
            )
        else:
            logger.warning(f"Columns have different lengths: {column_lengths}")

    keys = list(data.keys())

    # Use zip_longest for handling different lengths
    if strict_length or len(lengths) == 1:
        rows = zip(*[data[key] for key in keys])
    else:
        rows = zip_longest(*[data[key] for key in keys], fillvalue=fill_missing)

    result = [dict(zip(keys, row)) for row in rows]

    logger.info(f"Converted {len(data)} columns to {len(result)} rows")
    return result


def rows_to_columns(
    rows: List[Dict[str, Any]],
    default_value: Optional[Any] = None,
    preserve_order: bool = True,
) -> Dict[str, List[Any]]:
    """
    Convert row data to column data.

    Args:
        rows (List[Dict[str, Any]]): List of row dictionaries
        default_value (Optional[Any], optional): Value to use for missing data
        preserve_order (bool, optional): Preserve order of first row's keys

    Raises:
        TypeError: If rows is not a list or row values are not dictionaries

    Returns:
        Dict[str, List[Any]]: Dictionary of columns
    """
    if not isinstance(rows, list):
        raise TypeError("Rows must be a list")

    if not rows:
        logger.debug("Empty rows provided, returning empty dict")
        return {}

    logger.debug(f"Converting {len(rows)} rows to columns")

    # Validate input data
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"Row {i} must be a dictionary, got {type(row)}")

    # Collect all unique keys
    if preserve_order:
        # Use first row's order, then add any additional keys
        all_keys = list(rows[0].keys()) if rows else []
        for row in rows[1:]:
            for key in row.keys():
                if key not in all_keys:
                    all_keys.append(key)
    else:
        all_keys = list(set().union(*(row.keys() for row in rows)))

    # Build columns
    columns = {}
    for key in all_keys:
        columns[key] = [row.get(key, default_value) for row in rows]

    logger.info(f"Converted {len(rows)} rows to {len(columns)} columns")
    return columns


def transpose_table(
    table: Union[List[List[Any]], List[Dict[str, Any]], Dict[str, List[Any]]]
) -> Union[List[List[Any]], Dict[str, List[Any]]]:
    """
    Transpose a table of data from one format to another.

    Args:
        table (Union[List[List[Any]], List[Dict[str, Any]], Dict[str, List[Any]]]): Table data to transpose

    Returns:
        Union[List[List[Any]], Dict[str, List[Any]]]: Transposed table data

    Supports transposing from Dict of lists to List of dicts, List of dicts to Dict of lists, and List of lists to List of lists (traditional transpose).
    """
    if isinstance(table, dict):
        # Dict of lists -> List of dicts -> List of lists
        rows = columns_to_rows(table)
        return [[row[key] for key in table.keys()] for row in rows]

    elif isinstance(table, list) and table:
        if isinstance(table[0], dict):
            # List of dicts -> Dict of lists
            return rows_to_columns(table)
        elif isinstance(table[0], (list, tuple)):
            # List of lists -> List of lists (traditional transpose)
            return list(map(list, zip(*table)))

    return table


def validate_table_structure(
    data: Union[Dict[str, List[Any]], List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Validate the structure of a table of data.

    Args:
        data (Union[Dict[str, List[Any]], List[Dict[str, Any]]]): Table data to validate

    Returns:
        Dict[str, Any]: Validation info

    Validates the structure of the table by checking for consistent column lengths,
    analyzing column types and missing values, and flagging any issues.

    Supported formats are a dictionary of lists (columns) and a list of dictionaries (rows).
    """

    info = {
        "format": None,
        "num_columns": 0,
        "num_rows": 0,
        "column_names": [],
        "column_types": {},
        "missing_values": {},
        "is_valid": True,
        "issues": [],
    }

    try:
        if isinstance(data, dict):
            info["format"] = "columns"
            info["column_names"] = list(data.keys())
            info["num_columns"] = len(data)

            if data:
                lengths = [len(values) for values in data.values()]
                info["num_rows"] = lengths[0] if lengths else 0

                # Check for consistent lengths
                if len(set(lengths)) > 1:
                    info["is_valid"] = False
                    info["issues"].append(
                        f"Inconsistent column lengths: {dict(zip(data.keys(), lengths))}"
                    )

                # Analyze column types and missing values
                for col_name, values in data.items():
                    if values:
                        types = set(type(v).__name__ for v in values if v is not None)
                        info["column_types"][col_name] = list(types)
                        info["missing_values"][col_name] = sum(
                            1 for v in values if v is None
                        )

        elif isinstance(data, list) and data:
            info["format"] = "rows"
            info["num_rows"] = len(data)

            if isinstance(data[0], dict):
                all_keys = set()
                for row in data:
                    all_keys.update(row.keys())

                info["column_names"] = list(all_keys)
                info["num_columns"] = len(all_keys)

                # Check for consistent keys
                for i, row in enumerate(data):
                    missing_keys = all_keys - set(row.keys())
                    if missing_keys:
                        info["issues"].append(f"Row {i} missing keys: {missing_keys}")

    except Exception as e:
        info["is_valid"] = False
        info["issues"].append(f"Validation error: {e}")

    return info


def optimize_memory_usage(
    data: Dict[str, List[Any]], compress_strings: bool = True
) -> Dict[str, List[Any]]:
    """
    Optimize memory usage for a table of column data.

    Args:
        data (Dict[str, List[Any]]): Column data to optimize
        compress_strings (bool, optional): Whether to intern strings to save memory. Defaults to True.

    Returns:
        Dict[str, List[Any]]: Optimized column data

    Optimizes memory usage by copying column data and interning strings if necessary.
    """
    logger.debug("Optimizing memory usage for column data")

    optimized_data = {}

    for col_name, values in data.items():
        if compress_strings and values and isinstance(values[0], str):
            # Intern strings to save memory
            optimized_values = [
                sys.intern(v) if isinstance(v, str) else v for v in values
            ]
            optimized_data[col_name] = optimized_values
        else:
            optimized_data[col_name] = values.copy()

    return optimized_data


def batch_convert_columns_to_rows(
    data: Dict[str, List[Any]], batch_size: int = 1000
) -> Iterator[List[Dict[str, Any]]]:
    """
    Convert column data to row data in batches.

    Args:
        data (Dict[str, List[Any]]): Column data to convert
        batch_size (int, optional): Batch size for conversion. Defaults to 1000.

    Yields:
        Iterator[List[Dict[str, Any]]]: Batches of converted row data

    Converts column data to row data in batches, yielding each batch as it is converted.
    This can be useful for large datasets that do not fit into memory.
    """
    if not data:
        return

    keys = list(data.keys())
    num_rows = len(next(iter(data.values())))

    logger.info(f"Converting {num_rows} rows in batches of {batch_size}")

    for start_idx in range(0, num_rows, batch_size):
        end_idx = min(start_idx + batch_size, num_rows)

        batch_data = {key: data[key][start_idx:end_idx] for key in keys}

        batch_rows = columns_to_rows(batch_data)

        logger.debug(
            f"Converted batch {start_idx}-{end_idx-1} ({len(batch_rows)} rows)"
        )
        yield batch_rows
