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


def get_weekdays_until(start_date: str) -> list[str]:
    """
    Return a list of weekday dates from start_date until today.

    :param start_date: a date string in the format "%d/%m/%Y"
    :return: a list of dates in the format "%Y-%m-%d"
    :raises ValueError: if start_date is in the future
    """
    logger.debug(f"Extracting days until {start_date}")
    _start_date = datetime.strptime(start_date, "%d-%b-%Y").date()
    today = date.today()
    try:
        if _start_date > today:
            raise ValueError("Start date must not be in the future.")
    except ValueError as e:
        logger.exception(e)
        return None

    delta = today - _start_date
    days = [
        (_start_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        for i in range(delta.days)
        if (_start_date + timedelta(days=i + 1)).weekday() < 5  # Mon=0, Sun=6
    ]
    return days