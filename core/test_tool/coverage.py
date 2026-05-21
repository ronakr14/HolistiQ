import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from libs.test_ops.utils import prepare_report_dir, validate_test_path

logger = logging.getLogger(__name__)


def infer_modules_from_test(test_path: str) -> List[str]:
    """
    Infer modules from a test file by parsing its content.

    Args:
        test_path (str): Path to the test file

    Returns:
        List[str]: A list of inferred modules
    """
    logger.debug("Inferring modules from test file")
    modules = set()
    with open(test_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match both 'import libs.utils.parallel_ops'
    # and 'from libs.utils import parallel_ops'
    import_matches = re.findall(r"import\s+(libs[\w\.]*)", content)
    from_matches = re.findall(r"from\s+(libs[\w\.]*)\s+import", content)

    for m in import_matches + from_matches:
        # Reduce `from libs.utils import parallel_ops` → libs.utils`
        modules.add(m.strip())

    return sorted(modules)


def build_pytest_command(
    test_path: Path, modules: list[str], html_dir: Path, extra_args: list[str]
) -> list[str]:
    """
    Build a pytest command for running coverage on a test file.

    Args:
        test_path (Path): Path to the test file
        modules (list[str]): List of modules to include in coverage
        html_dir (Path): Directory to write HTML coverage report
        extra_args (list[str]): Extra arguments to pass to pytest

    Returns:
        list[str]: The pytest command as a list of strings
    """
    cmd = [
        "pytest",
        str(test_path),
        "--cov-report=term-missing",
        f"--cov-report=html:{html_dir}",
        *[f"--cov={m}" for m in modules],
        *extra_args,
    ]
    return cmd


def execute_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """
    Execute a pytest command and log its output.

    Args:
        cmd (list[str]): The pytest command as a list of strings

    Returns:
        subprocess.CompletedProcess: The result of the subprocess
    """
    logger.info("\nRunning pytest command:\n%s\n", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(result.stdout)
    if result.stderr.strip():
        logger.error(result.stderr)
    return result


def write_log(report_dir: Path, result: subprocess.CompletedProcess):
    """
    Write the output of a pytest command to a log file.

    Args:
        report_dir (Path): Directory to write log file
        result (subprocess.CompletedProcess): Result of the pytest command

    Returns:
        Path: Path to the log file
    """
    log_file = report_dir / "pytest_output.log"
    log_file.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    return log_file


def check_coverage_warnings(result: subprocess.CompletedProcess):
    """
    Check if there are any warnings in the pytest result, and log them accordingly.

    Warnings include "No data was collected", which may indicate that the coverage module
    was unable to collect data from the specified module or test.
    """
    if "No data was collected" in result.stderr:
        logger.warning("Warning: No coverage data collected — check imports or paths.")


def resolve_module(test_path: Path, module: Union[str, list[str], None]) -> list[str]:
    """Resolve module(s) from test path or explicit module parameter.

    If module is None, attempt to infer modules from imports in the test file.
    If inference fails, raise a ValueError.

    Normalize the module parameter to a list of str, if it is not already a list.

    Args:
        test_path (Path): Path to the test file
        module (Union[str, list[str], None]): Module(s) to resolve

    Returns:
        list[str]: Module(s) resolved from test path or explicit module parameter
    """
    if not module:
        module = infer_modules_from_test(str(test_path))
        if not module:
            raise ValueError(
                f"Could not infer module from imports in {test_path}. "
                f"Please specify --module explicitly."
            )
        logger.info(f"Inferred module(s): {module}")

    # Normalize to list
    return module if isinstance(module, list) else [module]


def coverage_with_pytest(
    test_dir: str,
    module: Union[str, list[str], None] = None,
    report_dir: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> str:
    """
    Run pytest with coverage report.

    Args:
        test_dir (str): Directory to discover tests
        module (Union[str, list[str], None], optional): Module(s) to include in coverage report.
            If None, attempt to infer modules from imports in the test file.
        report_dir (Optional[str], optional): Directory to write coverage report.
            If None, will use the default directory.
        extra_args (Optional[List[str]], optional): Extra arguments to pass to pytest.

    Returns:
        str: Path to the HTML coverage report
    """
    extra_args = extra_args or []

    test_path = validate_test_path(test_dir)
    modules = resolve_module(test_path, module)
    report_dir = prepare_report_dir(report_dir)
    html_report_dir = report_dir / "htmlcov"

    cmd = build_pytest_command(test_path, modules, html_report_dir, extra_args)
    result = execute_command(cmd)
    write_log(report_dir, result)
    check_coverage_warnings(result)

    logger.info(f"Coverage HTML report available at: {html_report_dir}")
