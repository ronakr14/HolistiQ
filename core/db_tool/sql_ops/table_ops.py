import logging
from pathlib import Path
from typing import Optional, Union

from sqlalchemy import Engine, inspect

from libs.encryptors.safe_string import SafeConnectionString
from libs.sql_ops.core.executor import QueryExecutor
from libs.sql_ops.schema_ops import create_schema

logger = logging.getLogger(__name__)
DDL_DIR = Path(r"D:\HolistiQ\scripts\SQL\holistiq\testops")


def create_table_from_ddl(
    executor: QueryExecutor,
    table_name: str,
    schema_name: str,
    dialect: str,
    ddl_dir: Optional[Path] = None,
):
    """
    Creates a table from a DDL script.

    Args:
        executor (QueryExecutor): The executor to use for the query.
        table_name (str): The name of the table to create.
        schema_name (str): The name of the schema to create the table in.
        dialect (str): The dialect of the database.
        ddl_dir (Optional[Path], optional): The directory where the DDL script is located. Defaults to None.

    Raises:
        FileNotFoundError: If the DDL script is not found.
    """
    ddl_dir = ddl_dir if ddl_dir else DDL_DIR
    ddl_file = ddl_dir / f"{table_name}.sql"

    if not ddl_file.exists():
        raise FileNotFoundError(f"DDL script not found: {ddl_file}")

    ddl_sql = ddl_file.read_text(encoding="utf-8")

    # If SQLite → strip schema name
    if dialect == "sqlite":
        ddl_sql = ddl_sql.replace(f"{schema_name}.", "")

    executor.execute_sync(ddl_sql)
    executor.dispose()


def verify_table_presence(
    db_conn: Union[str, "SafeConnectionString", "Engine"],
    table_name: str,
    schema_name: Optional[str] = None,
    ddl_dir: Optional[Path] = None,
):
    """
    Checks if a table exists in the given database.

    Args:
        db_conn (Union[str, "SafeConnectionString", "Engine"]): The database connection string or a pre-initialized SQLAlchemy Engine.
        table_name (str): The name of the table to check.
        schema_name (Optional[str], optional): The name of the schema to check in. Defaults to None.
        ddl_dir (Optional[Path], optional): The directory where the DDL script is located. Defaults to None.

    Raises:
        FileNotFoundError: If the DDL script is not found.

    Returns:
        bool: True if the table exists, False otherwise.
    """
    executor = QueryExecutor(db_conn=db_conn)
    db_engine = executor.db_engine
    dialect = str(db_engine.dialect.name).lower()
    inspector = inspect(db_engine)

    if dialect == "sqlite":
        # SQLite: no schema support
        tables = inspector.get_table_names()
        table_exists = table_name in tables
    else:
        # Postgres, MySQL, etc.
        schemas = inspector.get_schema_names()
        if schema_name not in schemas:
            create_schema(executor, schema_name, dialect)
        tables = inspector.get_table_names(schema=schema_name)
        table_exists = table_name in tables

    if not table_exists:
        logger.warning(
            f"Table '{schema_name}.{table_name}' not found. Creating from DDL script."
        )
        create_table_from_ddl(executor, table_name, schema_name, dialect, ddl_dir)
    else:
        logger.debug(f"Table '{schema_name}.{table_name}' already exists.")
