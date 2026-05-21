import datetime
import logging
from pathlib import Path
from typing import Union

from libs.sql_ops.core.executor import QueryExecutor
from libs.sql_ops.extractor import extract_sql_queries
from libs.sql_ops.loader import load_sql_files
from libs.sql_ops.sql_info import SQLInfo
from libs.sql_ops.utils import get_db_conn

logger = logging.getLogger(__name__)


def sql_executor(error: bool = False, config: dict = {}):
    """
    Execute SQL queries based on the given configuration.

    Parameters:
        error (bool): If True, will continue on exceptions. Defaults to False.
        config (dict): Configuration containing database connection string, pooling settings, and optional settings for dataframe conversion.

    Returns:
        None
    """
    if not config:
        logger.warning("No config provided, using default config")
        return


def sql_script_executor(path: Union[str, Path], error: bool = False, config: dict = {}):
    """
    Execute SQL scripts based on the given configuration.

    Parameters:
        path (Union[str, Path]): Path to the SQL scripts.
        error (bool): If True, will continue on exceptions. Defaults to False.
        config (dict): Configuration containing database connection string, pooling settings, and optional settings for dataframe conversion.

    Returns:
        None
    """
    if not config:
        logger.warning("No config provided, using default config")
        return

    execution_stats = {
        "total_queries": 0,
        "successful_queries": 0,
        "failed_queries": 0,
        "total_duration_ms": 0.0,
        "start_time": datetime.now(),
        "end_time": None,
    }
    logger.info(f"Starting SQL script execution for: {path}")
    files = load_sql_files(path)
    # result = executor.execute_file(files)
    execution_stats["total_files"] = len(files)
    all_results = []
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    for file in files:
        try:
            file_results, execution_stats = execute_file(
                file, error, config, execution_stats
            )
            all_results.extend(file_results)

        except Exception:
            logger.exception(f"Failed to process file {file}")

    # Finalize stats
    execution_stats["end_time"] = datetime.now()
    execution_stats["total_duration_ms"] = sum(
        r.duration_ms for r in all_results if r.duration_ms
    )


def execute_file(
    file_path: Path, config: dict, stats: dict, on_error: bool = False
) -> list[SQLInfo]:
    """
    Executes a SQL file using the provided configuration and query executor.

    Args:
        file_path (Path): The path to the SQL file to execute.
        config (dict): A dictionary containing the database configuration.
        stats (dict): A dictionary to store execution statistics.
        on_error (bool, optional): If True, will raise an exception if a query fails. Defaults to False.

    Returns:
        list[SQLInfo]: A list of SQLInfo objects containing the execution results of each query.
    """
    encoding = config["sqlops"]["encoding"]
    conn_str = get_db_conn(config)
    logger.info(f"Executing SQL file: {file_path.name}")
    queries = extract_sql_queries(file_path, encoding)
    results = []
    qb = QueryExecutor(db_conn=conn_str)

    for i, query in enumerate(queries):
        result = SQLInfo(query, file_path, i)

        try:
            result.start_time = datetime.now()
            # Execute query using the query executor
            execution_result = qb.execute_sync(query)

            result.end_time = datetime.now()
            result.success = True
            result.rows_affected = getattr(execution_result, "rowcount", None)
            result.result_data = execution_result  # type: ignore

            stats["successful_queries"] += 1
            logger.debug(
                f"Query {i+1} executed successfully ({result.duration_ms:.2f}ms)"
            )

        except Exception as e:
            result.end_time = datetime.now()
            result.success = False
            result.error_message = str(e)
            stats["failed_queries"] += 1

            logger.error(f"Query {i+1} failed: {e}")
            if not on_error:
                raise

        results.append(result)
        stats["total_queries"] += 1

    return results, stats
