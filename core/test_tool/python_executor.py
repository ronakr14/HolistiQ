import logging
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from libs.test_ops.python_libs.python_lifecycle import (
    execute_setup_test,
    execute_teardown_test,
    setup_all_context,
    teardown_all_context,
)
from libs.test_ops.python_libs.python_loader import _load_module
from libs.test_ops.state import TestExecutionState
from libs.test_ops.test_info import TestInfo, TestResultInfo

logger = logging.getLogger(__name__)

_file_execution_states: dict[str, TestExecutionState] = {}
_states_lock = threading.Lock()


class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


def _get_or_create_file_state(file_path: str, test_count: int) -> TestExecutionState:
    """
    Retrieves or creates a TestExecutionState instance for the given file path.

    Args:
        file_path (str): Path to the test file
        test_count (int): Number of tests in the file

    Returns:
        TestExecutionState: The execution state for the file
    """
    with _states_lock:
        if file_path not in _file_execution_states:
            _file_execution_states[file_path] = TestExecutionState(test_count)
        return _file_execution_states[file_path]


def prepare_tasks(file_path: str, test_file_info: TestInfo):
    """
    Prepares a list of test tasks for the given file path and test file info.

    Args:
        file_path (str): Path to the test file
        test_file_info (TestInfo): Test file info containing the test methods

    Returns:
        list: A list of task functions to be executed in parallel
    """
    file_state = _get_or_create_file_state(file_path, len(test_file_info.test_methods))
    tasks = []

    for test_method in test_file_info.test_methods:

        def task(tm=test_method.name, th=test_method.hashkey):
            """
            Returns a task function that executes a test method.

            Args:
                tm (str): The name of the test method
                th (str): The hash key of the test method

            Returns:
                callable: A task function that executes the test method
            """
            return execute_test(
                Path(file_path),
                test_file_info,
                tm,
                file_state,
                th,
            )

        tasks.append(task)

    logger.info(f"Prepared {len(tasks)} test tasks for {file_path}")
    return tasks


def execute_test_method(
    test_instance: Any, method_name: str, module: Optional[Any] = None
) -> None:
    """
    Executes a test method.

    Args:
        test_instance (Any): The test instance to execute the test method on
        method_name (str): The name of the test method to execute
        module (Optional[Any]): The module to execute the test method from (if not test_instance)

    Raises:
        AttributeError: If the test method is not found in the class or module
        TypeError: If the test method is not callable
        AssertionError: If an assertion fails in the test method
        Exception: If any other exception occurs during test method execution
    """
    logger.info(f"Executing test method: {method_name}")

    # Figure out where the callable lives
    target = None

    if test_instance and hasattr(test_instance, method_name):
        target = getattr(test_instance, method_name)
    elif module and hasattr(module, method_name):
        target = getattr(module, method_name)
    else:
        raise AttributeError(
            f"Test method '{method_name}' not found in class or module"
        )

    if not callable(target):
        raise TypeError(f"'{method_name}' is not callable")

    try:
        target()
        logger.debug(f"Test method {method_name} completed successfully")
    except AssertionError as e:
        logger.error(f"Assertion failed in {method_name}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Execution error in {method_name}: {e}")
        raise


def execute_test(
    file_path: Path,
    test_file_info: TestInfo,
    test_method: str,
    file_state: TestExecutionState,
    test_id: Optional[str],
) -> TestResultInfo:
    """
    Executes a test method from a given test file info.

    Args:
        file_path (Path): The path to the test file
        test_file_info (TestInfo): Test file info containing the test methods
        test_method (str): The name of the test method to execute
        file_state (TestExecutionState): The file execution state to mark test completion
        test_id (Optional[str]): The ID of the test (if any)

    Returns:
        TestResultInfo: A TestResultInfo object containing the result of the test execution
    """
    start_time = datetime.now()
    status = TestStatus.PENDING
    exception_info = None
    test_instance = None

    try:
        logger.info(f"Executing {test_file_info.name}.{test_method}")
        module = _load_module(file_path)
        test_class = None
        if test_file_info.name:
            test_class = getattr(module, test_file_info.name)
        if test_class:
            test_instance = test_class()
        with setup_all_context(
            test_instance, test_file_info.setup_all_method, file_state
        ):
            status = TestStatus.RUNNING
            with teardown_all_context(
                test_instance, test_file_info.teardown_all_method, file_state
            ):
                execute_setup_test(test_instance, test_file_info.setup_test_method)
                try:
                    execute_test_method(test_instance, test_method, module)
                    status = TestStatus.PASSED
                finally:
                    execute_teardown_test(
                        test_instance, test_file_info.teardown_test_method, file_state
                    )

    except AssertionError as e:
        exception_info = (type(e).__name__, str(e))
        file_state.mark_test_completed(failed=True)
        if "assertion" in str(e).lower():
            status = TestStatus.FAILED
            logger.error(f"{test_file_info.name}.{test_method} failed: {e}")
        else:
            status = TestStatus.ERROR
            logger.exception(
                f"Test execution error in {test_file_info.name}.{test_method}: {e}"
            )

    except Exception as e:
        status = TestStatus.ERROR
        exception_info = (type(e).__name__, str(e))
        logger.exception(
            f"Unexpected error in {test_file_info.name}.{test_method}: {e}"
        )

    finally:
        end_time = datetime.now()
        elapsed_seconds = (end_time - start_time).total_seconds()
        # Update file state
        all_done = file_state.is_all_tests_completed()
        logger.info(
            f"{test_file_info.name}.{test_method} completed in {elapsed_seconds:.3f}s "
            f"with status: {status.value}"
        )
        if all_done:
            summary = file_state.get_summary()
            _file_execution_states.pop(str(file_path), None)
            logger.info(
                f"File {file_path.name} execution completed: "
                f"{summary['completed_tests']} tests, "
                f"{summary['failed_tests']} failures, "
                f"{summary['elapsed_seconds']:.2f}s total"
            )

    return TestResultInfo(
        file_path=str(file_path),
        module_name=test_file_info.module_name,
        test_class_name=test_file_info.name,
        test_method_name=test_method,
        status=status,
        start_time=start_time,
        end_time=end_time,
        elapsed_seconds=elapsed_seconds,
        exception_info=exception_info,
        test_id=test_id,
    )
