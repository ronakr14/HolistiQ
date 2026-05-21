import os
import random
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable, Optional

from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


# ---- Adaptive defaults ----
DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_MAX_RETRIES = 3
DEFAULT_THREADS = os.cpu_count() or 8  # auto-adjust to hardware


def _get_executor(executor_type: str, max_workers: int):
    """
    Returns an executor of the given type with the specified maximum number of workers.

    Args:
        executor_type (str): The type of executor to return. Must be either "process" or "thread".
        max_workers (int): The maximum number of workers for the executor.

    Returns:
        Union[ProcessPoolExecutor, ThreadPoolExecutor]: The executor of the given type with the specified maximum number of workers.
    """
    return (ProcessPoolExecutor if executor_type == "process" else ThreadPoolExecutor)(
        max_workers=max_workers
    )


def _collect_results(
    futures: list[Future],
    timeout: float,
    preserve_order: bool,
) -> list[Any]:
    """
    Collects the results of a list of futures, optionally preserving the order of the original list.

    Args:
        futures (list[Future]): A list of futures to collect the results from.
        timeout (float): The maximum time to wait for all futures to complete.
        preserve_order (bool): If True, the results will be returned in the same order as the original list.

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding future, or None if the future raised an exception.
    """
    results: list[Any] = [None] * len(futures) if preserve_order else []
    completed_count = 0

    try:
        if preserve_order:
            for i, future in enumerate(futures):
                try:
                    results[i] = future.result(timeout=timeout)
                    logger.debug(f"Task {i+1}/{len(futures)} completed")
                except Exception as e:
                    logger.error(f"Task {i+1} failed: {e}")
                    results[i] = None
        else:
            for future in as_completed(futures, timeout=timeout):
                try:
                    result = future.result()
                    results.append(result)
                    completed_count += 1
                    logger.debug(f"Task {completed_count}/{len(futures)} completed")
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                    results.append(None)

    except KeyboardInterrupt:
        logger.warning("Execution interrupted, cancelling remaining tasks")
        for f in futures:
            f.cancel()
        raise

    return results


def execute_parallel(
    tasks: list[Callable[[], Any]],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    preserve_order: bool = False,
    executor_type: str = "thread",
) -> list[Any]:
    """
    Execute a list of tasks in parallel using an executor of the given type with the specified maximum number of workers.

    Args:
        tasks (list[Callable[[], Any]]): A list of tasks to execute in parallel.
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        timeout (Optional[float]): The maximum time in seconds to wait for all tasks to complete. Defaults to DEFAULT_TIMEOUT.
        preserve_order (bool): If True, the results will be returned in the same order as the original list. Defaults to False.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task raised an exception.
    """
    if not tasks:
        logger.warning("No tasks provided for parallel execution")
        return []

    max_workers = max_workers if max_workers is not None else DEFAULT_THREADS
    timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    logger.info(
        f"Executing {len(tasks)} tasks in parallel with {max_workers} workers "
        f"(timeout: {timeout}s, executor: {executor_type})"
    )

    try:
        with _get_executor(executor_type, max_workers) as executor:
            futures = [executor.submit(task) for task in tasks]
            return _collect_results(futures, timeout, preserve_order)
    except Exception as e:
        logger.error(f"Parallel execution failed: {e}")
        raise


def execute_parallel_with_args(
    func: Callable[..., Any],
    args_list: list[tuple[Any, ...]],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    preserve_order: bool = False,
    executor_type: str = "thread",
) -> list[Any]:
    """
    Execute a list of tasks in parallel using an executor of the given type with the specified maximum number of workers.

    Args:
        func (Callable[..., Any]): The function to execute.
        args_list (list[tuple[Any, ...]]): A list of arguments to pass to the function.
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        timeout (Optional[float]): The maximum time in seconds to wait for all tasks to complete. Defaults to DEFAULT_TIMEOUT.
        preserve_order (bool): If True, the results will be returned in the same order as the original list. Defaults to False.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task raised an exception.
    """
    tasks = [partial(func, *args) for args in args_list]
    return execute_parallel(tasks, max_workers, timeout, preserve_order, executor_type)


def execute_parallel_with_retry(
    tasks: list[Callable[[], Any]],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = 1.0,
    executor_type: str = "thread",
    backoff_factor: float = 2.0,
    jitter: float = 0.5,
    fail_fast: bool = False,
) -> list[Any]:
    """
    Execute a list of tasks in parallel using an executor of the given type with the specified maximum number of workers, retrying tasks that fail up to the specified maximum number of times.

    Args:
        tasks (list[Callable[[], Any]]): A list of tasks to execute in parallel.
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        timeout (Optional[float]): The maximum time in seconds to wait for all tasks to complete. Defaults to DEFAULT_TIMEOUT.
        max_retries (int): The maximum number of times to retry tasks that fail. Defaults to DEFAULT_MAX_RETRIES.
        retry_delay (float): The initial delay in seconds between retries. Defaults to 1.0.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".
        backoff_factor (float): The factor to use for exponential backoff between retries. Defaults to 2.0.
        jitter (float): The fraction of the delay to use for random jitter. Defaults to 0.5.
        fail_fast (bool): If True, fail immediately if all tasks fail in one attempt. Defaults to False.

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task failed permanently.
    """
    max_workers = max_workers if max_workers is not None else DEFAULT_THREADS
    timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    # Important note up front: when using executor_type="process" your tasks (the callable you submit, plus args/returns) must be pickleable — i.e., top-level functions or picklable callables. The tests respect that.

    logger.info(
        f"Executing {len(tasks)} tasks with retry "
        f"(max_retries={max_retries}, executor={executor_type}, "
        f"backoff_factor={backoff_factor}, jitter={jitter}, fail_fast={fail_fast})"
    )

    results: list[Any] = [None] * len(tasks)
    # failed_tasks: list of tuples (original_index, callable)
    failed_tasks: list[tuple[int, Callable[[], Any]]] = list(enumerate(tasks))

    for attempt in range(max_retries + 1):
        if not failed_tasks:
            break

        logger.info(
            f"Attempt {attempt + 1}/{max_retries + 1} for {len(failed_tasks)} tasks"
        )

        with _get_executor(executor_type, max_workers) as executor:
            # Map futures back to original task indices
            future_map: dict[Future, int] = {
                executor.submit(task): idx for idx, task in failed_tasks
            }
            new_failed_tasks: list[tuple[int, Callable[[], Any]]] = []
            succeeded = 0

            for future in as_completed(future_map, timeout=timeout):
                task_idx = future_map[future]
                try:
                    results[task_idx] = future.result()
                    logger.debug(f"Task {task_idx} succeeded on attempt {attempt + 1}")
                except Exception as e:
                    # We'll retry if we still have attempts left
                    if attempt < max_retries:
                        new_failed_tasks.append((task_idx, tasks[task_idx]))
                        logger.warning(
                            f"Task {task_idx} failed on attempt {attempt + 1}: {e}"
                        )
                    else:
                        logger.error(f"Task {task_idx} failed permanently: {e}")

        # ---- Fail-fast check ----
        if fail_fast and succeeded == 0 and new_failed_tasks:
            logger.error("All tasks failed in one attempt, failing fast.")
            break

        failed_tasks = new_failed_tasks

        # ---- Exponential backoff with jitter ----
        if failed_tasks and attempt < max_retries:
            delay = retry_delay * (backoff_factor**attempt)
            jitter_offset = (
                delay * jitter * (random.random() * 2 - 1)
            )  # ± jitter fraction
            delay = max(0, delay + jitter_offset)
            logger.info(f"Retrying {len(failed_tasks)} tasks in {delay:.2f}s...")
            time.sleep(delay)

    success_count = sum(1 for r in results if r is not None)
    logger.info(
        f"Parallel execution completed: {success_count}/{len(tasks)} tasks succeeded"
    )
    return results


@contextmanager
def parallel_context(max_workers: Optional[int] = None, executor_type: str = "thread"):
    """
    Context manager for parallel execution.

    Yields an executor of the specified type with the specified maximum number of workers.

    Args:
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".

    Yields:
        Union[ThreadPoolExecutor, ProcessPoolExecutor]: The executor to use for parallel execution.
    """
    max_workers = max_workers if max_workers is not None else DEFAULT_THREADS
    with _get_executor(executor_type, max_workers) as executor:
        yield executor


def get_optimal_worker_count(task_count: int, cpu_bound: bool = False) -> int:
    """
    Returns the optimal number of workers for parallel execution based on the task count and cpu bound.

    Args:
        task_count (int): The number of tasks to execute in parallel.
        cpu_bound (bool): If True, use the number of CPU cores as the maximum number of workers. Defaults to False.

    Returns:
        int: The optimal number of workers for parallel execution.
    """
    if cpu_bound:
        optimal = min(os.cpu_count() or 1, task_count)
    else:
        optimal = min(DEFAULT_THREADS * 2, task_count)
    return optimal


def execute_batched_parallel(
    tasks: list[Callable[[], Any]],
    batch_size: int,
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    executor_type: str = "thread",
) -> list[Any]:
    """
    Execute a list of tasks in parallel using an executor of the given type with the specified maximum number of workers,
    processing tasks in batches of the specified size.

    Args:
        tasks (list[Callable[[], Any]]): A list of tasks to execute in parallel.
        batch_size (int): The number of tasks to process in each batch.
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        timeout (Optional[float]): The maximum time in seconds to wait for all tasks to complete. Defaults to DEFAULT_TIMEOUT.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task raised an exception.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    logger.info(f"Executing {len(tasks)} tasks in batches of {batch_size}")

    all_results: list[Any] = []
    total_batches = (len(tasks) + batch_size - 1) // batch_size

    for i in range(0, len(tasks), batch_size):
        batch = tasks[i : i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(
            f"Processing batch {batch_num}/{total_batches} ({len(batch)} tasks)"
        )
        batch_results = execute_parallel(
            batch,
            max_workers,
            timeout,
            preserve_order=True,
            executor_type=executor_type,
        )
        all_results.extend(batch_results)

    return all_results


def execute_parallel_mixed(
    tasks: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    preserve_order: bool = False,
    executor_type: str = "thread",
) -> list[Any]:
    """
    Execute a list of tasks in parallel using an executor of the given type with the specified maximum number of workers.
    Each task is a tuple of (func, args, kwargs), where func is the function to call, args is a tuple of arguments to pass to func,
    and kwargs is a dictionary of keyword arguments to pass to func.

    Args:
        tasks (list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]]): A list of tasks to execute in parallel.
        max_workers (Optional[int]): The maximum number of workers to use in the executor. Defaults to DEFAULT_THREADS.
        timeout (Optional[float]): The maximum time in seconds to wait for all tasks to complete. Defaults to DEFAULT_TIMEOUT.
        preserve_order (bool): If True, the results will be returned in the same order as the original list. Defaults to False.
        executor_type (str): The type of executor to use. Either "thread" or "process". Defaults to "thread".

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task raised an exception.
    """
    if not tasks:
        logger.info("No tasks provided for parallel execution")
        return []

    max_workers = max_workers if max_workers is not None else DEFAULT_THREADS
    timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    with _get_executor(executor_type, max_workers) as executor:
        futures = [
            executor.submit(func, *args, **kwargs) for func, args, kwargs in tasks
        ]
        return _collect_results(futures, timeout, preserve_order)
