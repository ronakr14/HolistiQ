import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from libs.file_ops.directory_ops import ensure_dir
from libs.test_ops.python_libs.python_executor import (
    prepare_tasks as python_prepare_tasks,
)
from libs.test_ops.test_info import TestInfo
from libs.utils.parallel_utils import execute_parallel

logger = logging.getLogger(__name__)
DEFAULT_OUTPUT_DIR = ".output"


def runner_custom(test_methods_dict: dict[str, TestInfo], timeout: Optional[int] = 300):
    """
    Executes a list of test tasks in parallel using an executor of the given type with the specified maximum number of workers.

    Args:
        test_methods_dict (dict[str, TestInfo]): A dictionary of test files and their associated test methods.
        timeout (Optional[int]): The maximum time in seconds to wait for all tasks to complete. Defaults to 300.

    Returns:
        list[Any]: A list of results, where each result is the result of the corresponding task, or None if the task raised an exception.
    """
    if not test_methods_dict:
        raise ValueError("test_methods_dict cannot be empty")

    tasks = _prepare_all_tasks(test_methods_dict)

    if not tasks:
        logger.warning("No test tasks were generated.")
        return None

    logger.info(f"Executing {len(tasks)} test tasks in parallel.")

    try:
        results = execute_parallel(tasks=tasks, timeout=timeout)
        if results:
            logger.info("Test executions completed successfully")
            return results
        else:
            logger.warning("No test results returned from execution")
    except Exception as e:
        logger.error(f"Error during parallel execution: {e}")
        raise


def runner_pytest(
    html: bool,
    json: bool,
    txt: bool,
    tags: list[str],
    test_dir: str,
    output_dir: Optional[str] = None,
    file_name: Optional[str] = None,
):
    """
    Executes pytest on a given test directory with optional output to HTML, JSON, and TXT files.

    Args:
        html (bool): Whether to generate an HTML report.
        json (bool): Whether to generate a JSON report.
        txt (bool): Whether to generate a TXT report.
        tags (list[str]): The tags to filter tests by.
        test_dir (str): The directory to discover tests in.
        output_dir (Optional[str], optional): The directory to write output files to. Defaults to None.
        file_name (Optional[str], optional): The base filename to use for output files. Defaults to None.

    Returns:
        subprocess.CompletedProcess: The result of the pytest command. If txt is False, the stdout and stderr of the command are logged instead.
    """

    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    ensure_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = file_name or "pytest_results"

    # Build the pytest command
    pytest_cmd = [
        "pytest",
        test_dir,
    ]

    if tags:
        pytest_cmd.extend(
            [
                "-m",
                tags,
            ]
        )

    pytest_cmd = _prepare_pytest_outputs(
        pytest_cmd, base_name, output_dir, timestamp, html, json
    )

    logger.info(f"Running Pytest command:\n{' '.join(pytest_cmd)}")

    if txt:
        txt_file = output_dir / f"{base_name}_{timestamp}.txt"
        _run_pytest_to_file(pytest_cmd, txt_file)
    else:
        result = subprocess.run(pytest_cmd, capture_output=True, text=True)
        logger.debug(result.stdout)
        logger.error(result.stderr if result.stderr else "")
        return result


def _prepare_pytest_outputs(
    pytest_cmd, base_name: str, output_dir: Path, timestamp: str, html: bool, json: bool
):
    """
    Prepare a pytest command by adding options for HTML and JSON output.

    Args:
        pytest_cmd (list[str]): The pytest command to modify.
        base_name (str): The base filename to use for output files.
        output_dir (Path): The directory to write output files to.
        timestamp (str): The timestamp to append to output filenames.
        html (bool): Whether to generate an HTML report.
        json (bool): Whether to generate a JSON report.

    Returns:
        list[str]: The modified pytest command.
    """
    file_paths = {}
    if html:
        html_file = output_dir / f"{base_name}_{timestamp}.html"
        pytest_cmd += ["--html", str(html_file), "--self-contained-html"]
        file_paths["html"] = html_file
    if json:
        json_file = output_dir / f"{base_name}_{timestamp}.json"
        pytest_cmd += ["--json-report", f"--json-report-file={json_file}"]
        file_paths["json"] = json_file
    return pytest_cmd


def _run_pytest_to_file(pytest_cmd, file_path: Path):
    """
    Run a pytest command and write the output to a file.

    Args:
        pytest_cmd (list[str]): The pytest command to run.
        file_path (Path): The file to write the output to.
    """
    ensure_dir(file_path.parent)
    with open(file_path, "w", encoding="utf-8") as txt_file:
        subprocess.run(pytest_cmd, stdout=txt_file, stderr=subprocess.STDOUT)
    logger.info(f"Pytest output written to {file_path}")


def _prepare_all_tasks(test_methods_dict: dict[str, list[str]]) -> list[Any]:
    """
    Prepare a list of tasks to execute in parallel based on the given test methods.

    Args:
        test_methods_dict (dict[str, list[str]]): A dictionary where the keys are file paths and the values are lists of test methods to run.

    Returns:
        list[Any]: A list of tasks to execute in parallel.
    """
    tasks = []

    for file_path, test_file_info in test_methods_dict.items():
        try:
            file_tasks = _prepare_file_tasks(file_path, test_file_info)
            tasks.extend(file_tasks)
        except Exception as e:
            logger.error(f"Failed to prepare tasks for {file_path}: {e}")
            # Continue with other files instead of failing completely
            continue

    return tasks


def _prepare_file_tasks(file_path: str, test_file_info: list[str]) -> list[Any]:
    """
    Prepare a list of tasks to execute in parallel based on the given test methods.

    Args:
        file_path (str): The file path to prepare tasks for.
        test_file_info (list[str]): The test methods to prepare tasks for.

    Returns:
        list[Any]: A list of tasks to execute in parallel.
    """
    if not test_file_info:
        logger.warning(f"No test methods provided for {file_path}")
        return []

    logger.debug(
        f"Preparing {len(test_file_info.test_methods)} tasks for {file_path} "  # type: ignore
    )
    if file_path.endswith(".py"):
        return python_prepare_tasks(file_path, test_file_info)
    return []
