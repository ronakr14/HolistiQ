import logging

from libs.sql_ops.core.db_connector import get_db_conn as get_all_db_conn

logger = logging.getLogger(__name__)


def get_db_conn(config: dict):
    """
    Retrieves a database connection based on the provided configuration.

    Args:
        config (dict): A dictionary containing configuration for the test warehouse database.

    Returns:
        Any: A database connection object based on the provided configuration.
    """

    all_conn = get_all_db_conn(config=config)
    return all_conn[f"{config['sqlops']['conn']}_conn"]
