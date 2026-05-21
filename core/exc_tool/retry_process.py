# libs/utils/retry_utils.py

"""
A unified, extensible retry framework supporting **sync** and **async**
functions with:

- Exponential backoff (base_delay, backoff_factor, max_delay)
- Jitter strategies ("full", "uniform", or disabled)
- Retry on *exceptions* or *results*
- Retry attempt limits OR overall timeout budget
- Structured logging instrumentation
- Tenacity-like "before_sleep" hooks
- Pluggable stop conditions and predicates
- Sync and async retry support

This module aims to provide a reliable, cloud-native retry primitive suitable
for data platforms, API connectors, ingestion workers, and distributed systems
where transient faults are expected and should be handled gracefully.

**Full Configuration Reference**
```python
@retry(
    max_attempts=5,              # Stop after X attempts
    total_timeout=30,            # OR stop after X seconds
    base_delay=1.0,              # Initial backoff delay
    backoff_factor=2.0,          # Exponential backoff multiplier
    max_delay=60.0,              # Max cap on delay
    exceptions=(Exception,),     # What to retry
    retry_if_result=None,        # Predicate retrying results
    jitter="full",               # Jitter mode: None, 'full', 'uniform'
    before_sleep=None,           # Hook
    reraise=True                 # Whether to propagate final exception
)
def my_func():
    ...
```
---
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import random
import time
from typing import (
    Any,
    Callable,
    Optional,
    Type,
)

from libs.mixers.logger_mixin import get_logger

logger = get_logger("Retry", component="Utils")

# --- Type aliases for clarity ---
Predicate = Callable[[Any], bool]
BeforeSleepFn = Callable[[Exception | None, int, float, dict], None]
#   receives (exception or None if result triggered retry, attempt_number, next_delay, context)


# --- Helper wait strategies ---
def _exp_backoff_delay(
    base: float, factor: float, attempt: int, max_delay: Optional[float]
) -> float:
    """
    Calculates the delay for the next retry attempt using an exponential backoff strategy.

    Args:
        base (float): The initial delay in seconds.
        factor (float): The backoff factor to use.
        attempt (int): The current retry attempt number.
        max_delay (Optional[float]): The maximum delay in seconds.

    Returns:
        float: The calculated delay for the next retry attempt.
    """
    delay = base * (factor ** (attempt - 1))
    if max_delay is not None:
        return min(delay, max_delay)
    return delay


def _apply_jitter(delay: float, jitter: Optional[str]) -> float:
    """
    Applies jitter to a delay.

    Args:
        delay (float): The base delay to apply jitter to.
        jitter (Optional[str]): The type of jitter to apply. If None, no jitter is applied.

    Returns:
        float: The jittered delay.

    Raises:
        ValueError: If jitter is not one of (None, 'full', 'uniform').

    Note: jitter='full' applies a full uniform jitter between 0 and the delay,
        while jitter='uniform' applies a +/- 25% uniform jitter around the delay.
    """
    if not jitter:
        return delay
    if jitter == "full":
        return random.uniform(0, delay)
    if jitter == "uniform":
        # +/- 25% uniform jitter
        delta = 0.25 * delay
        return random.uniform(delay - delta, delay + delta)
    raise ValueError("jitter must be one of (None, 'full', 'uniform')")


# --- Stop conditions ---
def _stop_by_attempt(attempt: int, max_attempts: Optional[int]) -> bool:
    """
    Returns True if the retry attempt has exceeded the maximum number of attempts,
    and False otherwise.

    Args:
        attempt (int): The current retry attempt number.
        max_attempts (Optional[int]): The maximum number of retry attempts.

    Returns:
        bool: Whether the retry attempt has exceeded the maximum number of attempts.
    """
    if max_attempts is None:
        return False
    return attempt >= max_attempts


def _stop_by_deadline(start_ts: float, total_timeout: Optional[float]) -> bool:
    """
    Returns True if the time elapsed since `start_ts` has exceeded `total_timeout`, and False otherwise.

    Args:
        start_ts (float): The start time of the retry attempts in seconds since the epoch.
        total_timeout (Optional[float]): The total timeout in seconds. If None, no timeout is applied.

    Returns:
        bool: Whether the time elapsed since `start_ts` has exceeded `total_timeout`.
    """
    if total_timeout is None:
        return False
    return (time.time() - start_ts) >= total_timeout


# --- Default predicates ---
def _retry_if_exception(
    exc: BaseException, retry_exceptions: tuple[Type[BaseException], ...]
) -> bool:
    """
    Returns True if the given exception is an instance of any of the exception types
    in `retry_exceptions`, and False otherwise.

    Args:
        exc (BaseException): The exception to check.
        retry_exceptions (Tuple[Type[BaseException], ...]): A tuple of exception types to retry.

    Returns:
        bool: Whether the exception should be retried.
    """
    return isinstance(exc, retry_exceptions)


def _retry_if_result_is_truthy(result: Any) -> bool:
    """
    Returns True if the given result is truthy, and False otherwise.

    Args:
        result (Any): The result to check.

    Returns:
        bool: Whether the result is truthy.
    """
    return bool(result)


# --- The decorator factory ---
def retry(
    *,
    max_attempts: Optional[int] = 5,
    total_timeout: Optional[float] = None,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: Optional[float] = 60.0,
    exceptions: tuple[Type[BaseException], ...] = (Exception,),
    retry_if_result: Optional[Predicate] = None,
    jitter: Optional[str] = "full",  # None | 'full' | 'uniform'
    before_sleep: Optional[BeforeSleepFn] = None,
    reraise: bool = True,
):
    # normalize exceptions tuple
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_attempts (Optional[int]): Maximum number of retry attempts.
        total_timeout (Optional[float]): Total timeout in seconds.
        base_delay (float): Initial delay in seconds.
        backoff_factor (float): Backoff factor to use.
        max_delay (Optional[float]): Maximum delay in seconds.
        exceptions (tuple[Type[BaseException], ...]): Tuple of exception types to retry.
        retry_if_result (Optional[Predicate]): Optional predicate to check the result of the function.
            e.g. - @retry(retry_if_result=lambda res: res is None)
        jitter (Optional[str]): Type of jitter to apply to the delay. If None, no jitter is applied.
        before_sleep (Optional[BeforeSleepFn]): Optional function to call before sleeping.

    Returns:
        Callable: Decorated function.
    """
    if not isinstance(exceptions, tuple):
        exceptions = (exceptions,)

    # context dict that can carry user values (instrumentation)
    context_template: dict = {}

    def decorator(func: Callable):

        is_coro = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        def _sync_wrapper(*args, **kwargs):
            logger.debug("Sync wrapper for retry")

            start_ts = time.time()
            attempt = 0
            last_result: Any = None

            while True:
                attempt += 1
                context = dict(context_template)
                context.update(
                    {
                        "func": getattr(func, "__name__", str(func)),
                        "args": args,
                        "kwargs": kwargs,
                    }
                )
                try:
                    logger.debug(f"Function {func.__name__}, attempts: {attempt}")
                    res = func(*args, **kwargs)
                    last_result = res
                    # if user provided a result predicate, check it
                    if retry_if_result and retry_if_result(res):
                        # treat as retryable "soft" failure (no exception)
                        # determine next delay & possibly bail
                        if _stop_by_attempt(attempt, max_attempts) or _stop_by_deadline(
                            start_ts, total_timeout
                        ):
                            logger.error(
                                "Aborting, Final Attempt or timeout, retryable result"
                            )
                            if reraise:
                                # no exception to re-raise, return last result (or raise custom?) — choose to return
                                return last_result
                            return last_result
                        next_delay = _exp_backoff_delay(
                            base_delay, backoff_factor, attempt, max_delay
                        )
                        next_delay = _apply_jitter(next_delay, jitter)
                        logger.warning(
                            f"Retryable results, Retrying: {next_delay} seconds"
                        )
                        if before_sleep:
                            try:
                                before_sleep(None, attempt, next_delay, context)
                            except Exception as e:
                                logger.debug(f"before_sleep callback raised {str(e)}")
                        time.sleep(next_delay)
                        continue
                    # success (non-retryable result)
                    return res

                except Exception as exc:
                    # check if exception type should be retried
                    if not _retry_if_exception(exc, exceptions):
                        logger.error(
                            f"Aborting, Exception not configured to retry, {str(exc)}"
                        )
                        raise

                    # check stop conditions
                    if _stop_by_attempt(attempt, max_attempts) or _stop_by_deadline(
                        start_ts, total_timeout
                    ):
                        logger.error(
                            f"Aborting, Max Attempts or timeout reached, {str(exc)}"
                        )
                        if reraise:
                            raise
                        return None

                    # compute next delay
                    next_delay = _exp_backoff_delay(
                        base_delay, backoff_factor, attempt, max_delay
                    )
                    next_delay = _apply_jitter(next_delay, jitter)
                    logger.error(str(exc))
                    logger.warning(
                        f"Retryable exception, Retrying: {next_delay} seconds"
                    )

                    if before_sleep:
                        try:
                            before_sleep(exc, attempt, next_delay, context)
                        except Exception as e:
                            logger.debug(f"before_sleep callback raised {str(e)}")

                    # respect total_timeout budget: if sleeping would exceed budget, abort
                    if (
                        total_timeout is not None
                        and (time.time() + next_delay - start_ts) > total_timeout
                    ):
                        logger.error(
                            f"Aborting, sleep would exceed total timeout budget, {str(exc)}"
                        )

                        if reraise:
                            raise
                        return None

                    time.sleep(next_delay)
                    continue

        @functools.wraps(func)
        async def _async_wrapper(*args, **kwargs):
            logger.debug("Async wrapper for retry")

            start_ts = time.time()
            attempt = 0
            last_result: Any = None

            while True:
                attempt += 1
                context = dict(context_template)
                context.update(
                    {
                        "func": getattr(func, "__name__", str(func)),
                        "args": args,
                        "kwargs": kwargs,
                    }
                )
                try:
                    logger.debug(f"Async Function {func.__name__}, attempts: {attempt}")
                    res = await func(*args, **kwargs)
                    last_result = res
                    if retry_if_result and retry_if_result(res):
                        if _stop_by_attempt(attempt, max_attempts) or _stop_by_deadline(
                            start_ts, total_timeout
                        ):
                            logger.error(
                                "Aborting, Final Attempt or timeout, retryable result"
                            )
                            return last_result
                        next_delay = _exp_backoff_delay(
                            base_delay, backoff_factor, attempt, max_delay
                        )
                        next_delay = _apply_jitter(next_delay, jitter)
                        logger.warning(
                            f"Retryable results, Retrying: {next_delay} seconds"
                        )
                        if before_sleep:
                            try:
                                before_sleep(None, attempt, next_delay, context)
                            except Exception as e:
                                logger.debug(f"before_sleep callback raised, {str(e)}")
                        await asyncio.sleep(next_delay)
                        continue
                    return res

                except Exception as exc:  # noqa: BLE001
                    if not _retry_if_exception(exc, exceptions):
                        logger.error(
                            f"Aborting, Exception not configured to retry, {str(exc)}"
                        )
                        raise

                    if _stop_by_attempt(attempt, max_attempts) or _stop_by_deadline(
                        start_ts, total_timeout
                    ):
                        logger.error(
                            f"Aborting, Max Attempts or timeout reached, {str(exc)}"
                        )
                        raise

                    next_delay = _exp_backoff_delay(
                        base_delay, backoff_factor, attempt, max_delay
                    )
                    next_delay = _apply_jitter(next_delay, jitter)
                    logger.error(str(exc))
                    logger.warning(
                        f"Retryable exception, Retrying: {next_delay} seconds"
                    )

                    if before_sleep:
                        try:
                            before_sleep(exc, attempt, next_delay, context)
                        except Exception as e:
                            logger.debug(f"before_sleep callback raised, {str(e)}")

                    if (
                        total_timeout is not None
                        and (time.time() + next_delay - start_ts) > total_timeout
                    ):
                        logger.error(
                            f"Aborting, sleep would exceed total timeout budget, {str(exc)}"
                        )
                        raise

                    await asyncio.sleep(next_delay)
                    continue

        return _async_wrapper if is_coro else _sync_wrapper

    return decorator
