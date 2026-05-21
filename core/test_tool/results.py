import logging
from collections import defaultdict
from typing import Any

from libs.file_ops.exporters.exporter import export_html, export_json, export_txt
from libs.sql_ops.core.executor import QueryExecutor
from libs.sql_ops.querybuilder.querybuilder import QueryBuilder
from libs.sql_ops.table_ops import verify_table_presence
from libs.test_ops.test_info import TestResultInfo
from libs.test_ops.utils import _get_username, get_db_conn, render_testresults_custom
from libs.utils.git_utils import (
    get_branch_name_from_file,
    get_git_path_with_repo_folder,
    is_file_in_git_repo,
)
from libs.utils.sys_utils import get_hardware_type

logger = logging.getLogger(__name__)


def process_test_results(
    results: list[TestResultInfo], html: bool, json: bool, txt: bool
) -> None:
    """
    Process test results and export them to desired formats.

    Args:
        results (list[TestResultInfo]): List of test result information.
        html (bool): Whether to export test results to an HTML file.
        json (bool): Whether to export test results to a JSON file.
        txt (bool): Whether to export test results to a text file.

    Returns:
        None
    """
    if not results:
        logger.warning("No test results provided")
        return

    # Calculate statistics
    passed = [r for r in results if r.status.value == "passed"]
    failed = [r for r in results if r.status.value == "failed"]
    # skipped = [r for r in results if r.status.value == "skipped"]
    errors = [r for r in results if r.status.value == "error"]
    # Log detailed results
    _log_detailed_results(passed, failed, errors)

    if html:
        html_report = render_testresults_custom(test_results=results)
        export_html(report=html_report, file_name="test_result")
        if json:
            json_data = [result.to_dict() for result in results]
            export_json(data=json_data, file_name="test_result")
        if txt:
            export_txt(data=results, file_name="test_result")


def _log_detailed_results(
    passed: list[TestResultInfo],
    failed: list[TestResultInfo],
    error: list[TestResultInfo],  # summary: TestSummary
) -> None:
    """
    Logs detailed test results to the console.

    Args:
        passed (list[TestResultInfo]): List of test results that passed.
        failed (list[TestResultInfo]): List of test results that failed.
        error (list[TestResultInfo]): List of test results that encountered errors.

    Notes:
        Generates a final report message that includes the number of passed, failed, and
        error tests. Also includes a success rate percentage.
    """
    report_sections = []

    # Add passed tests section
    if passed:
        pass_section = _format_passed_tests(passed)
        report_sections.append(pass_section)

    # Add failed tests section
    if failed:
        fail_section = _format_failed_tests(failed)
        report_sections.append(fail_section)

    if error:
        error_section = _format_error_tests(error)
        report_sections.append(error_section)

    # Generate final message
    if report_sections:
        final_report = "\n\n".join(report_sections)
    else:
        final_report = "No tests were executed."

    # Add summary line
    if len(passed) > 0 and len(failed) == 0 and len(error) == 0:
        final_report += "\n\n Hooray!!! All tests passed."
    elif len(passed) == 0:
        final_report += "\n\n Important!!! All tests failed."

    total_tests = len(passed) + len(failed) + len(error)
    success_rate = len(passed) / total_tests * 100 if total_tests > 0 else 0.0

    logger.info(
        f"Test Results Summary (Success Rate: {success_rate:.1f}%):\n{final_report}"
    )


def _format_passed_tests(passed_tests: list[TestResultInfo]) -> str:
    """
    Formats a list of test results into a string that summarizes the passed test cases.

    Args:
        passed_tests (list[TestResultInfo]): A list of test results that passed.

    Returns:
        str: A string summarizing the passed test cases.

    Notes:
        The string includes the number of passed tests and their respective names (module name, class name, method name).
    """
    lines = ["Passed Test Cases:"]
    for idx, test in enumerate(passed_tests, 1):
        full_test_name = (
            f"{test.module_name}.{test.test_class_name}.{test.test_method_name}"
        )
        lines.append(f"\t{idx}. {full_test_name}")
    return "\n".join(lines)


def _format_failed_tests(failed_tests: list[TestResultInfo]) -> str:
    """
    Formats a list of test results into a string that summarizes the failed test cases.

    Args:
        failed_tests (list[TestResultInfo]): A list of test results that failed.

    Returns:
        str: A string summarizing the failed test cases.

    Notes:
        The string includes the number of failed tests and their respective names (module name, class name, method name) and error messages (if any).
    """
    grouped_failures: defaultdict[str, list[TestResultInfo]] = defaultdict(list)
    for test in failed_tests:
        exception_category = (
            test.exception_info[1].split(":")[0] if test.exception_info else None
        )
        exception_type = exception_category or "Unknown Failure"
        grouped_failures[exception_type].append(test)

    lines = ["Failed Test Cases:"]

    for exception_type, tests in grouped_failures.items():
        lines.append(f"\t{exception_type}:")
        for idx, test in enumerate(tests, 1):
            exception_msg = (
                test.exception_info[1].split(":")[1] if test.exception_info else None
            )
            error_msg = exception_msg or "No error message"
            full_test_name = (
                f"{test.module_name}.{test.test_class_name}.{test.test_method_name}"
            )
            lines.append(f"\t\t{idx}. {full_test_name} - {error_msg}")

    return "\n".join(lines)


def _format_error_tests(error_tests: list[TestResultInfo]) -> str:
    # Group by exception type
    """
    Formats a list of test results into a string that summarizes the error test cases.

    Args:
        error_tests (list[TestResultInfo]): A list of test results that encountered errors.

    Returns:
        str: A string summarizing the error test cases.

    Notes:
        The string includes the number of error tests and their respective names (module name, class name, method name) and error messages (if any).
    """
    grouped_failures: defaultdict[str, list[TestResultInfo]] = defaultdict(list)
    for test in error_tests:
        exception_msg = (
            test.exception_info[1].split(":")[0] if test.exception_info else None
        )
        exception_type = exception_msg or "Unknown Error"
        grouped_failures[exception_type].append(test)

    lines = ["Error Test Cases:"]

    for exception_type, tests in grouped_failures.items():
        lines.append(f"\t{exception_type}:")
        for idx, test in enumerate(tests, 1):
            exception_msg = (
                test.exception_info[1].split(":")[1] if test.exception_info else None
            )
            error_msg = exception_msg or "No error message"
            full_test_name = (
                f"{test.module_name}.{test.test_class_name}.{test.test_method_name}"
            )
            lines.append(f"\t\t{idx}. {full_test_name} - {error_msg}")

    return "\n".join(lines)


def upload_results(results: list[TestResultInfo], config: dict = {}) -> bool:
    """
    Uploads test results to the test warehouse database.

    Args:
        results (list[TestResultInfo]): A list of test results to upload.
        config (dict): A dictionary containing configuration for the test warehouse database.

    Returns:
        bool: True if the test results are successfully uploaded, False otherwise.

    Raises:
        Exception: If there is an error while uploading the test results.
    """

    if not results:
        logger.warning("No test results to upload")
        return False

    if not config:
        logger.error("Unable to upload test cases: No config provided")
        return

    try:
        data = _prepare_upload_data(results)
        return _execute_upload(data=data, config=config)
    except Exception:
        logger.exception("Failed to upload test results")
        return False


def _prepare_upload_data(results: list[TestResultInfo]) -> dict[str, list[Any]]:
    """
    Prepares a dictionary of data to be uploaded to the test warehouse database.

    Args:
        results (list[TestResultInfo]): A list of test results to upload.

    Returns:
        dict[str, list[Any]]: A dictionary containing the test results data.

    Notes:
        The dictionary contains the following keys:

        - platform: The hardware type of the machine that ran the test.
        - runner: The test runner that executed the test.
        - git_repo: A boolean indicating whether the test file is in a Git repository.
        - filepath: The path to the test file relative to the Git repository.
        - branch: The branch name of the Git repository.
        - module: The name of the module that contains the test.
        - classname: The name of the class that contains the test.
        - testname: The name of the test.
        - result: The result of the test (pass, fail, error, or skipped).
        - error: The error message of the test if it failed.
        - started: The start time of the test.
        - finished: The end time of the test.
        - duration: The duration of the test.
        - username: The username of the user who ran the test.
        - parallely: A boolean indicating whether the test was run in parallel.
        - threads: The number of threads used to run the test.
        - exception: The exception type of the test if it failed.
    """
    result_count = len(results)

    # Get system information once
    hardware_type = get_hardware_type()
    username = _get_username()

    return {
        "platform": [hardware_type] * result_count,
        "runner": ["custom"] * result_count,
        "git_repo": [is_file_in_git_repo(r.file_path) for r in results],
        "filepath": [get_git_path_with_repo_folder(r.file_path) for r in results],
        "branch": [get_branch_name_from_file(r.file_path) for r in results],
        "module": [r.module_name for r in results],
        "classname": [r.test_class_name for r in results],
        "testname": [r.test_method_name for r in results],
        "result": [r.status.value for r in results],
        "error": [
            r.exception_info[1] if r.exception_info is not None else None
            for r in results
        ],
        "started": [r.start_time for r in results],
        "finished": [r.end_time for r in results],
        "duration": [r.elapsed_seconds for r in results],
        "username": [username] * result_count,
        "parallely": [False] * result_count,  # need improvement
        "threads": [1] * result_count,  # need improvement
        "exception": [
            r.exception_info[0] if r.exception_info is not None else None
            for r in results
        ],
        # "test_id": [r.test_id for r in results],
    }


def _execute_upload(data: dict[str, list[Any]], config: dict) -> bool:
    """
    Upload test results data to the holistiq database.

    Args:
        data (dict[str, list[Any]]): A dictionary containing the test results data.
        config (dict): A dictionary containing the database configuration.

    Returns:
        bool: True if the upload is successful, False otherwise.
    """
    conn_str = get_db_conn(config)
    try:
        qb = QueryBuilder(
            schema="holistiq_testops", table_name="testruns", db_conn=conn_str
        )
        verify_table_presence(db_conn=conn_str, table_name="testruns")

        if qb:
            qb.batch_insert(data=data).execute()
            _assign_runid(qb.executor)
            logger.info("Test results successfully uploaded to holistiq database")
            return True
        else:
            logger.error("Unable to create QueryBuilder for database upload")
            return False

    except Exception:
        logger.exception("Database upload failed")
        return False


def _assign_runid(executor: QueryExecutor) -> None:
    """
    Assigns a unique runid to each test result record in the testruns table.

    The runid is generated by concatenating the current date and time with the
    record's id, using the format '%Y%m%d_%H%M%f'.
    """

    query = "UPDATE testruns SET runid = strftime('%Y%m%d_%H%M%f', insertdate) || '_' || id WHERE runid IS NULL OR runid = '';"
    executor.execute_sync(query)
