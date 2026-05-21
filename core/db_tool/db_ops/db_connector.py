import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError, OperationalError

from libs.encryptors.safe_string import SafeConnectionString
from libs.utils.dict_utils import dict_to_namespace

logger = logging.getLogger(__name__)
_CONNECTION_TEMPLATES = {
    "postgres": "postgresql://{user}:{password}@{host}:{port}/{dbname}",
    "sqlite": "sqlite:///{path}/{dbname}.db",
}


def get_db_conn(config: dict) -> Dict[str, Optional[Any]]:
    """
    Builds database connections based on the configuration provided.

    Args:
        config: dict - configuration containing database information

    Returns:
        Dict[str, Optional[Any]] - a dictionary containing database connections
    """
    config = dict_to_namespace(config)
    dbs = getattr(config, "db", None)

    if not _validate_db_cfg(dbs):
        return

    db_conn: Dict[str, Optional[Any]] = build_db_conn(dbs)
    return db_conn


def _validate_db_cfg(dbs: dict) -> bool:
    """
    Validates the database configuration provided.

    Args:
        dbs: dict - the database configuration

    Returns:
        bool - whether the database configuration is valid or not

    Raises:
        None
    """
    if dbs is None:
        logger.error("Database configuration is not provided.")
        return False
    return True


def build_db_conn(dbs: dict):
    """
    Builds database connections based on the configuration provided.

    Args:
        dbs: dict - the database configuration

    Returns:
        Dict[str, Optional[Any]] - a dictionary containing database connections

    Raises:
        None
    """

    db_conn = {}
    for db_key, db_cfg in vars(dbs).items():
        try:
            conn_params = _extract_connection_params(db_key, db_cfg)
            connection = _create_connection(db_cfg.type, conn_params)

            if connection is not None:
                db_conn[f"{db_key}_conn"] = connection

        except Exception as e:
            logger.error("Failed to create connection for %s: %s", db_key, e)
    return db_conn


def _extract_connection_params(db_key: str, db_cfg: Any) -> Dict[str, Optional[str]]:
    """
    Extracts connection parameters from the database configuration.

    Args:
        db_key (str): The key for the database configuration.
        db_cfg (Any): The database configuration.

    Returns:
        Dict[str, Optional[str]]: A dictionary containing the connection parameters.

    Notes:
        Loads environment variables using `load_dotenv()`.
        Retrieves the password from the environment variables with the key being
        "{db_key}_pass". If no password is found, an empty string is used.
        Extracts the user, password, host, port, dbname, and path from the database
        configuration.
    """
    load_dotenv()

    password = os.getenv(key=f"{db_key}_pass", default="")

    return {
        "user": getattr(db_cfg, "user", None),
        "password": quote_plus(password) if password else "",
        "host": getattr(db_cfg, "host", None),
        "port": (
            str(getattr(db_cfg, "port", "")) if getattr(db_cfg, "port", None) else None
        ),
        "dbname": getattr(db_cfg, "db", None),
        "path": getattr(db_cfg, "path", None),
    }


def _create_connection(
    db_type: str, conn_params: Dict[str, Optional[str]]
) -> Optional[Union[SafeConnectionString, str]]:
    """
    Creates a database connection string based on the provided DB type and connection parameters.

    Args:
        db_type (str): The type of database to connect to.
        conn_params (Dict[str, Optional[str]]): A dictionary containing the connection parameters.

    Returns:
        Optional[Union[SafeConnectionString, str]]: A connection string or None if the DB type is unsupported or an error occurs.

    Raises:
        KeyError: If a required connection parameter is missing.
        Exception: If an error occurs while creating the connection string.

    Notes:
        Supports "postgres" and "sqlite" DB types.
    """
    if db_type not in _CONNECTION_TEMPLATES:
        logger.error("Unsupported DB type: %s", db_type)
        return None

    try:
        template = _CONNECTION_TEMPLATES[db_type]
        conn_str = template.format(**conn_params)
        conn_str = _validate_connection(conn_str)
        return SafeConnectionString(conn_str) if db_type == "postgres" else conn_str

    except KeyError as e:
        logger.error("Missing required parameter for %s connection: %s", db_type, e)
        return None
    except Exception as e:
        logger.error("Error creating %s connection: %s", db_type, e)
        return None


def _validate_connection(conn_str: str):
    """
    Validates a database connection string by attempting to connect to the database.

    Args:
        conn_str (str): The connection string to validate.

    Returns:
        Optional[Engine]: The validated database engine or None if the connection string is invalid.

    Raises:
        ValueError: If the connection string is invalid.
        RuntimeError: If the connection to the database fails.

    Notes:
        Supports "postgres" and "sqlite" DB types.
    """
    try:
        url = make_url(conn_str)
        dialect = url.get_dialect().name

        logger.debug(f"Detected dialect: {dialect}")

        # --- Handle SQLite separately ---
        if dialect == "sqlite":
            db_path = url.database  # Path part of the connection string
            if db_path:
                db_file = Path(db_path)
                if not db_file.exists():
                    db_file.parent.mkdir(parents=True, exist_ok=True)
                    db_file.touch()
                    logger.info(f"SQLite DB created at: {db_file}")
            else:
                logger.warning("Using in-memory SQLite database.")
            return create_engine(conn_str)

        # --- Validate other DBs ---
        engine = create_engine(conn_str)
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            logger.info(f"Connection successful: {conn_str}")
            return engine
        except OperationalError as e:
            raise RuntimeError(f"Failed to connect to database: {conn_str}\n{e}") from e

    except ArgumentError as e:
        raise ValueError(f"Invalid connection string: {conn_str}") from e
