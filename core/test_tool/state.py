import logging
import threading
from datetime import datetime
from typing import Any, Dict


class TestExecutionState:
    """Tracks and manages test file execution state."""

    def __init__(self, total_tests: int):
        """
        Initializes a TestExecutionState instance.

        Args:
            total_tests (int): The number of tests to be executed in the test file.

        """
        self.lock = threading.Lock()
        self.total_tests = total_tests
        self.completed_tests = 0
        self.failed_tests = 0
        self.setup_done = False
        self.teardown_done = False
        self.start_time = datetime.now()
        self.log = logging.getLogger(self.__class__.__name__)

    def mark_test_completed(self, failed: bool = False) -> bool:
        """
        Marks a test as completed and updates the execution state accordingly.

        Args:
            failed (bool, optional): Whether the test failed. Defaults to False.

        Returns:
            bool: Whether all tests have been completed.
        """
        with self.lock:
            self.completed_tests += 1
            if failed:
                self.failed_tests += 1
            return self.is_all_tests_completed()

    def is_all_tests_completed(self) -> bool:
        """
        Checks if all tests have been completed.

        Returns:
            bool: True if all tests have been completed, False otherwise.
        """
        return self.completed_tests >= self.total_tests

    def get_summary(self) -> Dict[str, Any]:
        """
        Returns a summary of the test execution state.

        Returns:
            A dictionary containing the total number of tests, completed tests, remaining tests, failed tests, elapsed seconds, and whether setup and teardown have been completed.
        """
        with self.lock:
            return {
                "total_tests": self.total_tests,
                "completed_tests": self.completed_tests,
                "remaining_tests": self.total_tests - self.completed_tests,
                "failed_tests": self.failed_tests,
                "elapsed_seconds": (datetime.now() - self.start_time).total_seconds(),
                "setup_done": self.setup_done,
                "teardown_done": self.teardown_done,
            }
