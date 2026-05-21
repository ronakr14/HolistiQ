import hashlib
import inspect
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pytest
from jinja2 import Template

from libs.sql_ops.core.db_connector import get_db_conn as get_all_db_conn
from libs.test_ops.templates import HTML_LIST_CUSTOM_TMPL, HTML_RESULT_CUSTOM_TMPL
from libs.test_ops.test_info import TestInfo, TestResultInfo

logger = logging.getLogger(__name__)
OUTPUT_DIR = ".output"


def prepare_report_dir(base_dir: Optional[str]) -> Path:
    """
    Prepare a directory for test results.

    Args:
        base_dir (Optional[str]): Base directory for report.

    Returns:
        Path: Path to the report directory.
    """
    base = Path(base_dir or OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = base / f"run_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def validate_test_path(test_dir: str) -> Path:
    """
    Validate a test path by checking if it exists.

    Args:
        test_dir (str): The path to the test directory

    Returns:
        Path: The validated test path

    Raises:
        FileNotFoundError: If the test path does not exist
    """
    path = Path(test_dir)
    if not path.exists():
        raise FileNotFoundError(f"Test path not found: {path}")
    return path


def _log_test_methods_summary(test_methods: dict[str, TestInfo]) -> None:
    """
    Logs a summary of the test methods loaded from a given dictionary.

    Args:
        test_methods (dict[str, TestInfo]): A dictionary of file paths to TestInfo objects

    Returns:
        None
    """
    if not test_methods:
        logger.warning("No test methods were loaded")
        return

    total_methods = sum(len(info.test_methods) for info in test_methods.values())
    logger.info(
        f"Successfully loaded {total_methods} test methods from {len(test_methods)} files"
    )

    # Create detailed log message
    summary_lines = []
    for file_idx, (file_path, info) in enumerate(test_methods.items(), 1):
        for method_idx, method_name in enumerate(info.test_methods, 1):
            line = (
                f"{file_idx}.{method_idx} - {file_path} - "
                f"{info.name} - {method_name.name}"
            )
            summary_lines.append(line)

    if summary_lines:
        detailed_summary = "\n\t".join(summary_lines)
        logger.info(f"Test methods extracted:\n\t{detailed_summary}")


def compute_test_hash(hash_obj: list[Any]) -> str:
    # Gather all relevant method sources
    """
    Compute a hash of a test method by combining the method source code
    of all objects in the given list.

    Args:
        hash_obj (list[Any]): A list of objects to include in the hash calculation

    Returns:
        str: A hash of the combined method source code as a hex string
    """
    combined_source = ""
    for obj in hash_obj:
        combined_source += get_method_source(obj)

    # Hash combined definition
    return hashlib.sha256(combined_source.encode("utf-8")).hexdigest()


def get_method_source(method: Optional[Callable]) -> str:
    """
    Retrieves the source code of a given method as a string.

    Args:
        method (Optional[Callable]): The method to retrieve the source code for

    Returns:
        str: The source code of the given method, or an empty string if the method is None

    Raises:
        OSError: If the source code of the method cannot be found
        TypeError: If the method is not a callable object
    """
    if method is None:
        return ""
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError):
        source = method.__name__  # fallback if source not available
    return " ".join(source.split())  # normalize whitespace


def tag(*tags):
    """
    A decorator that allows you to tag a test function with one or more names.

    This decorator can be used in two ways:

    1. Your custom runner can inspect the `_tags` attribute of the test function
        to determine which tests to run.

    2. Pytest will recognize the tags as marks, so you can use the `-m` command-line
        option to run only tests with a specific tag.

    Example:

        @tag("slow", "network")
        def test_something():
            pass

    This test will be marked as both "slow" and "network", and can be run with
    the command `pytest -m slow` or `pytest -m network`.
    """

    def decorator(func):
        # 1️⃣ Your custom runner can use this
        """
        A decorator that allows you to tag a test function with one or more names.

        The tags can be used in two ways:

        1. Your custom runner can inspect the `_tags` attribute of the test function
        to determine which tests to run.

        2. Pytest will recognize the tags as marks, so you can use the `-m` command-line
        option to run only tests with a specific tag.

        Example:

            @tag("slow", "network")
            def test_something():
                pass

        This test will be marked as both "slow" and "network", and can be run with
        the command `pytest -m slow` or `pytest -m network`.
        """

        setattr(func, "_tags", set(tags))

        # 2️⃣ Pytest will recognize this as a mark
        for t in tags:
            func = pytest.mark.__getattr__(t)(func)

        return func

    return decorator


def filter_tests_by_tags(test_dict: dict, include_tags: set[str]) -> dict:
    """
    Filters test methods from a given dictionary of TestInfo objects based on tag overlap.

    Args:
        test_dict (dict): A dictionary where the keys are file paths and the values are TestInfo objects.
        include_tags (set[str]): A set of tag names to filter by.

    Returns:
        dict: A filtered dictionary of TestInfo objects with only the matching test methods.
    """
    filtered = {}

    for file_path, test_info in test_dict.items():
        # Filter test methods based on tag overlap
        matching_methods = [
            m for m in test_info.test_methods if m.tags and (m.tags & include_tags)
        ]

        if matching_methods:
            # Create a shallow copy of TestInfo with filtered methods
            new_info = test_info.__class__(
                **{**test_info.__dict__, "test_methods": matching_methods}
            )
            filtered[file_path] = new_info

    return filtered


def render_testcases(test_data: dict[str, Any]) -> str:
    """
    Renders a summary HTML page for a given set of test cases.

    Args:
        test_data (dict[str, Any]): A dictionary where the keys are file paths and the values are TestInfo objects.

    Returns:
        str: A rendered HTML string summarizing the test cases.
    """

    summary = {
        "total_files": len(test_data),
        "total_classes": 0,
        "total_tests": 0,
        "tags": set(),
        "files": [],
    }

    # Extract data
    for file_path, test_info in test_data.items():
        class_name = getattr(test_info, "name", None) or "<no class>"
        test_methods = getattr(test_info, "test_methods", [])
        setup_all = bool(getattr(test_info, "setup_all_method", None))
        setup = bool(getattr(test_info, "setup_test_method", None))
        teardown = bool(getattr(test_info, "teardown_test_method", None))
        teardown_all = bool(getattr(test_info, "teardown_all_method", None))

        summary["total_classes"] += 1 if class_name != "<no class>" else 0
        summary["total_tests"] += len(test_methods)

        # Collect tags
        for t in test_methods:
            if hasattr(t, "tags") and isinstance(t.tags, set):
                summary["tags"].update(t.tags)

        test_names = [getattr(t, "name", "<no name>") for t in test_methods]

        summary["files"].append(
            {
                "filename": os.path.basename(file_path),
                "path": file_path,
                "classname": class_name,
                "test_names": test_names,
                "setup_all": setup_all,
                "setup": setup,
                "teardown": teardown,
                "teardown_all": teardown_all,
            }
        )

    template = Template(HTML_LIST_CUSTOM_TMPL)
    return template.render(**summary)


def serialize_testinfo_data(testinfo_dict):
    """
    Serializes a dictionary of TestInfo objects into a dictionary of summary dictionaries.

    Args:
        testinfo_dict (dict[str, TestInfo]): A dictionary where the keys are file paths and the values are TestInfo objects.

    Returns:
        dict[str, dict[str, Any]]: A dictionary where the keys are file paths and the values are summary dictionaries.
    """
    result = {}
    for file_path, ti in testinfo_dict.items():
        result[file_path] = ti.get_summary()

    return result


def render_testresults_custom(test_results: list[TestResultInfo]):
    # Summary stats
    """
    Renders an HTML report based on the test results provided.

    Args:
        test_results (list[TestResultInfo]): A list of TestResultInfo objects containing test result information.

    Returns:
        str: An HTML string containing the rendered report.
    """
    total = len(test_results)
    passed = sum(1 for t in test_results if t.status == "pass")
    failed = sum(1 for t in test_results if t.status == "fail")
    errored = sum(1 for t in test_results if t.status == "error")

    template = Template(HTML_RESULT_CUSTOM_TMPL)

    return template.render(
        total=total,
        passed=passed,
        failed=failed,
        errored=errored,
        tests=test_results,
        generated_on=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def get_db_conn(config: dict):
    """
    Retrieves a database connection based on the provided configuration.

    Args:
        config (dict): A dictionary containing configuration for the test warehouse database.

    Returns:
        Any: A database connection object based on the provided configuration.
    """
    all_conn = get_all_db_conn(config=config)
    return all_conn[f"{config['testops']['conn']}_conn"]


def _get_username() -> str:
    """
    Gets the current username safely.

    If os.getlogin() fails, it will fall back to using the USER or USERNAME environment variable.
    If both environment variables are not set, it will default to "system".
    """
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER", os.environ.get("USERNAME", "system"))
