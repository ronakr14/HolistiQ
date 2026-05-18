
import uuid

from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def new_uuid():
    """
    Generates a new UUID4 and returns it as a string.
    """
    _id = str(uuid.uuid4()).upper()
    logger.debug(f"Generating new UUID: {_id}")
    return _id
