import logging

from libs.sql_ops.core.executor import QueryExecutor

logger = logging.getLogger(__name__)


def create_schema(query_executor: QueryExecutor, schema_name: str, dialect: str):
    """
    Creates a schema in the given database.

    Args:
        query_executor (QueryExecutor): A pre-initialized QueryExecutor.
        schema_name (str): The name of the schema to create.
        dialect (str): The dialect of the database to execute the query in.

    Returns:
        None
    """
    if dialect == "sqlite":
        logger.debug("SQLite does not support schemas; skipping schema creation.")
        return
    query = f"CREATE SCHEMA IF NOT EXISTS {schema_name}"
    query_executor.execute_sync(query=query)
