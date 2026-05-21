# this cleanup utility only works if logger is initialized before calling it.

from __future__ import annotations

import functools
import inspect
import sys
from datetime import datetime
from typing import Optional

from custom_logger.logging_util import get_logger
from utils.datetime_utils import get_time_diff_seconds, now_utc_ts

logger = get_logger(__name__)


def _exit_with_runtime_log(start_time: datetime, message: str, exit_code: int = 1):
    """
    Exits the application with a log message containing the total runtime.

    Args:
        start_time (datetime): the application start time
        message (str): The log message to be displayed.
        exit_code (int, optional): The exit code to use. Defaults to 1.
    """
    runtime = get_time_diff_seconds(start_time)
    full_message = f"{message} in {runtime:.2f}s"
    logger.info(full_message)
    sys.exit(exit_code)


def _cleanup(start_time: datetime, err: Optional[Exception] = None):
    message = "All operations completed"
    exit_code = 0
    if err:
        logger.exception(err)
        message = "Application stopped due to exception"
        exit_code = 1
    _exit_with_runtime_log(start_time=start_time, message=message, exit_code=exit_code)


def cleanup():
    """
    Decorator that wraps a synchronous or asynchronous entrypoint function
    with unified cleanup, logging, and process termination logic.

    Returns:
        Callable: A decorated function.
    """

    def decorator(fn):
        is_coro = inspect.iscoroutinefunction(fn)
        start_time: datetime = now_utc_ts()
        if is_coro:

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                try:
                    await fn(*args, **kwargs)
                    _cleanup(start_time)
                except Exception as err:
                    _cleanup(start_time=start_time, err=err)
                    raise

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):

                try:
                    fn(*args, **kwargs)
                    _cleanup(start_time)
                except Exception as err:
                    _cleanup(start_time=start_time, err=err)
                    # raise

            return sync_wrapper

    return decorator
