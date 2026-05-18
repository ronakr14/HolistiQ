from datetime import datetime, timezone

from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def now_ts():
    """
    Return the current timestamp in UTC timezone.

    Returns:
        datetime: the current timestamp in UTC timezone
    """
    current_time = datetime.now(tz=timezone.utc)
    logger.debug(f"Current timestamp: {current_time}")
    return current_time


# def get_time_diff_seconds(starttime: datetime) -> float:
#     """
#     Calculate the time difference between two datetimes in seconds.

#     Args:
#         starttime (datetime): The start datetime.

#     Returns:
#         float: The time difference in seconds.
#     """
#     return (now_ts() - starttime).total_seconds()
