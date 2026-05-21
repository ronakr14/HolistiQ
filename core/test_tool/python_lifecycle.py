import logging
from contextlib import contextmanager
from typing import Any, Optional

from libs.test_ops.state import TestExecutionState

logger = logging.getLogger(__name__)


def _call_method(instance: Any, method_name: str, phase: str) -> None:
    """
    Calls a method on an instance with logging and error handling.

    Args:
        instance (Any): The instance to call the method on.
        method_name (str): The name of the method to call.
        phase (str): The phase of the method call (e.g. "setup", "teardown").

    Raises:
        RuntimeError: If the method call fails, a RuntimeError is raised with the original exception as the cause.
    """
    try:
        logger.debug(f"Executing {phase}: {method_name}")
        if instance:
            getattr(instance, method_name)()
        else:
            method_name()
        logger.debug(f"{phase} completed successfully")
    except Exception as e:
        msg = f"{phase} failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e


@contextmanager
def setup_all_context(
    test_instance: Any, method_name: Optional[str], file_state: TestExecutionState
):
    """
    Context manager to execute the setup_all method if it has not been executed before.

    Args:
        test_instance (Any): The test instance to call the setup_all method on.
        method_name (Optional[str]): The name of the setup_all method to call.
        file_state (TestExecutionState): The file execution state to keep track of the setup_all execution.

    Yields:
        None

    Raises:
        RuntimeError: If the setup_all method call fails, a RuntimeError is raised with the original exception as the cause.
    """
    if method_name:
        with file_state.lock:
            if not file_state.setup_done:
                _call_method(test_instance, method_name, "setup_all")
                file_state.setup_done = True
    yield


@contextmanager
def teardown_all_context(
    test_instance: Any, method_name: Optional[str], file_state: TestExecutionState
):
    """
    Context manager to execute the teardown_all method if it has not been executed before.

    Args:
        test_instance (Any): The test instance to call the teardown_all method on.
        method_name (Optional[str]): The name of the teardown_all method to call.
        file_state (TestExecutionState): The file execution state to keep track of the teardown_all execution.

    Yields:
        None

    Raises:
        RuntimeError: If the teardown_all method call fails, a RuntimeError is raised with the original exception as the cause.
    """
    try:
        yield
    finally:
        if (
            method_name
            and file_state.is_all_tests_completed()
            and not file_state.teardown_done
        ):
            with file_state.lock:
                try:
                    _call_method(test_instance, method_name, "teardown_all")
                    file_state.teardown_done = True
                except Exception:
                    # already logged; no re-raise to not block test completion
                    pass


def execute_setup_test(test_instance: Any, method_name: Optional[str]) -> None:
    """
    Executes the setup_test method if it has been specified.

    Args:
        test_instance (Any): The test instance to call the setup_test method on.
        method_name (Optional[str]): The name of the setup_test method to call.

    Raises:
        RuntimeError: If the setup_test method call fails, a RuntimeError is raised with the original exception as the cause.
    """
    if method_name:
        _call_method(test_instance, method_name, "setup_test")


def execute_teardown_test(
    test_instance: Any, method_name: Optional[str], file_state: TestExecutionState
) -> None:
    """
    Executes the teardown_test method if it has been specified.

    Args:
        test_instance (Any): The test instance to call the teardown_test method on.
        method_name (Optional[str]): The name of the teardown_test method to call.
        file_state (TestExecutionState): The file execution state to mark test completion.

    Raises:
        RuntimeError: If the teardown_test method call fails, a RuntimeError is raised with the original exception as the cause.
    """
    if method_name and hasattr(test_instance, method_name):
        try:
            _call_method(test_instance, method_name, "teardown_test")
        finally:
            file_state.mark_test_completed()
