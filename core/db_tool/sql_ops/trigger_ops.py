import logging
from pathlib import Path
from typing import Optional, Union

from sqlalchemy import Engine

from libs.encryptors.safe_string import SafeConnectionString
from libs.sql_ops.core.executor import QueryExecutor

logger = logging.getLogger(__name__)
TRIGGER_DIR = Path(r"D:\HolistiQ\scripts\SQL\holistiq\testops")


def create_trigger_from_file(
    executor: QueryExecutor, trigger_name: str, trigger_dir: Optional[Path] = None
):
    """
    Creates a trigger from a SQL file.

    Args:
        executor (QueryExecutor): Query executor to use for executing the trigger creation.
        trigger_name (str): Name of the trigger to create.
        trigger_dir (Optional[Path]): Directory containing the SQL file of the trigger. Defaults to None.

    Raises:
        FileNotFoundError: If the SQL file for the trigger does not exist.
    """
    trigger_dir = trigger_dir if trigger_dir else TRIGGER_DIR
    trigger_file = trigger_dir / f"{trigger_name}.sql"

    if not trigger_file.exists():
        raise FileNotFoundError(f"Trigger script not found: {trigger_file}")

    trigger_sql = trigger_file.read_text(encoding="utf-8")

    executor.execute_sync(trigger_sql)
    executor.dispose()


def verify_trigger_presence(
    db_conn: Union[str, "SafeConnectionString", "Engine"], trigger_name: str
):
    """
    Verifies if a trigger exists in the database and creates it if it does not.

    Args:
        db_conn (Union[str, "SafeConnectionString", "Engine"]): Database connection string or a pre-initialized SQLAlchemy Engine.
        trigger_name (str): Name of the trigger to verify.

    Raises:
        None

    Returns:
        None
    """

    executor = QueryExecutor(db_conn=db_conn)
    db_engine = executor.db_engine
    dialect = str(db_engine.dialect.name).lower()
    query = ""

    if dialect == "sqlite":
        query = f"SELECT name FROM sqlite_master WHERE type='trigger' AND name='{trigger_name}';"

    result = executor.execute_sync(query)
    if result:
        logger.warning(f"Trigger {trigger_name} already exists in the database.")
        return

    logger.debug(f"Trigger {trigger_name} does not exist in the database.")
    create_trigger_from_file(executor=executor, trigger_name=trigger_name)
    logger.debug(f"Trigger {trigger_name} created in the database.")
