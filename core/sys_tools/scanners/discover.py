import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional, Union

from libs.test_ops.python_libs.python_loader import python_loader
from libs.test_ops.test_info import TestInfo
from libs.test_ops.utils import filter_tests_by_tags

EXCLUDED_EXTENSIONS = (".pyc", ".pyo", "__pycache__")
EXCLUDED_DIRS = ("venv", ".venv", ".git", "__pycache__")
SUPPORTED_LOADERS = (".py",)
LOADERS: dict[str, Callable[[str], TestInfo]] = {
    ".py": python_loader,
}

logger = logging.getLogger(__name__)


def is_test_file(path: Path) -> bool:
    """Check if a given path is a test file.

    A test file is defined as a file whose name starts with 'test_' or
    whose stem ends with '_test', and whose suffix is one of the supported
    loaders (currently only '.py' is supported). The file must not have
    any of the excluded extensions.

    Args:
        path: The path to check.

    Returns:
        bool: True if the path is a test file, False otherwise."""
    if not path.is_file():
        return False

    return (
        (path.name.startswith("test_") or path.stem.endswith("_test"))
        and path.suffix in SUPPORTED_LOADERS
        and path.suffix not in EXCLUDED_EXTENSIONS
    )


def is_excluded_dir(path: Path) -> bool:
    """Check if a given path is in an excluded directory.

    Args:
        path: The path to check.

    Returns:
        bool: True if the path is in an excluded directory, False otherwise."""
    return any(part in EXCLUDED_DIRS for part in path.parts)


def find_test_files(test_dir: Union[str, Path] = Path.cwd()) -> list[Path]:
    """Find all test files in the given directory.

    Args:
        test_dir: The directory to search for test files. Defaults to the current working directory.

    Returns:
        list[Path]: A sorted list of all test files found in the given directory.

    Notes:
        A test file is defined as a file whose name starts with 'test_' or
        whose stem ends with '_test', and whose suffix is one of the supported
        loaders (currently only '.py' is supported). The file must not have
        any of the excluded extensions. If the given path is a single file,
        it is returned as a list containing only that file if it is a test file,
        otherwise an empty list is returned. If the given path is a directory,
        all test files found in that directory and its subdirectories are returned.
    """
    start = Path(test_dir).resolve()

    # Single-file case
    if start.is_file():
        return [start] if is_test_file(start) else []

    # Directory case
    test_files = [
        f.resolve()
        for f in start.rglob("*.py")
        if not is_excluded_dir(f) and is_test_file(f)
    ]

    return sorted(test_files)


def validate_file_list(file_paths: list[str]) -> None:
    """Validate that the given list of file paths is not empty.

    Args:
        file_paths: A list of file paths to validate.

    Raises:
        ValueError: If the given list of file paths is empty.
    """
    if not file_paths:
        raise ValueError("No test files provided")


def load_test_info(file_path: str) -> TestInfo:
    """
    Load test information from a given file path.

    Args:
        file_path: The path to the file to load test information from.

    Returns:
        TestInfo: A TestInfo object containing information about the test methods in the given file, or None if no test methods were found or if an exception occurred during loading.

    Notes:
        If the given file path is not a file, or if it does not have any test methods, this function returns None. If an exception occurs during loading, this function logs the exception and returns None.
    """
    try:
        test_info = _load_file_methods(file_path)
        if not test_info:
            logger.debug(f"No test methods found in {file_path}")
            return None

        logger.debug(f"Loaded {len(test_info.test_methods)} methods from {file_path}")
        return test_info

    except Exception as e:
        logger.error(f"Failed to load test methods from {file_path}: {e}")
        return None


def summarize_failures(failed_files: list[str]) -> None:
    """
    Summarize the failed files during test method discovery.

    Args:
        failed_files (list[str]): A list of file paths that failed to load during test method discovery.

    Notes:
        Logs a warning message containing the number and names of the failed files.
    """
    if failed_files:
        logger.warning(f"Failed to load {len(failed_files)} files: {failed_files}")


def get_loader(file_extension: str) -> Optional[Callable[[str], TestInfo]]:
    """Get the loader associated with the given file extension.

    Args:
        file_extension (str): The file extension to get the loader for.

    Returns:
        Optional[Callable[[str], TestInfo]]: The loader associated with the given file extension, or None if no loader is registered for that extension.
    """
    return LOADERS.get(file_extension)


def find_test_methods(file_paths: list[str]) -> dict[str, TestInfo]:
    """
    Find test methods in the given list of file paths.

    Args:
        file_paths (list[str]): A list of file paths to search for test methods.

    Returns:
        dict[str, TestInfo]: A dictionary where the keys are the file paths and the values are TestInfo objects containing information about the test methods in the given file.

    Notes:
        Logs a warning message for each file that failed to load during test method discovery, and summarizes the failed files at the end.
    """
    validate_file_list(file_paths)

    test_methods: dict[str, TestInfo] = {}
    failed_files: list[str] = []

    for file_path in file_paths:
        test_info = load_test_info(file_path)
        if test_info:
            test_methods[str(file_path)] = test_info
        else:
            failed_files.append(file_path)

    summarize_failures(failed_files)
    return test_methods


def _load_file_methods(file_path: str) -> Optional[TestInfo]:
    """
    Loads test methods from a file path using the appropriate loader.

    Args:
        file_path (str): The file path to load test methods from.

    Returns:
        Optional[TestInfo]: The loaded test methods, or None if the file path does not have a registered loader or if an exception occurs during loading.

    Notes:
        Logs a debug message if no loader is registered for the given file extension.
        Logs a warning message if the loader returns no tests for the given file path.
        Logs an exception message if an exception occurs during loading.
    """
    ext = Path(file_path).suffix
    loader = get_loader(ext)

    if not loader:
        logger.debug(f"No loader registered for extension '{ext}' in {file_path}")
        return None

    try:
        result = loader(file_path)
        if result:
            logger.debug(f"Successfully loaded tests from {file_path}")
        else:
            logger.warning(f"Loader returned no tests for {file_path}")
        return result
    except Exception:
        logger.exception(f"Failed to load test methods from {file_path}")
        return None


def discover_custom(test_dir: Union[str, Path] = Path.cwd(), tags: list[str] = None):
    """
    Discovers test methods from a given directory using custom loaders.

    Args:
        test_dir (Union[str, Path], optional): The directory to discover tests in. Defaults to Path.cwd().
        tags (list[str], optional): The tags to filter tests by. If None, all tests are returned. Defaults to None.

    Returns:
        list[TestInfo]: The discovered test methods.
    """
    test_dir = Path(test_dir).resolve()
    logger.info(f"Starting test discovery in: {test_dir} (tags={tags})")

    files = find_test_files(test_dir)
    test_methods = find_test_methods(files)

    if tags:
        test_methods = filter_tests_by_tags(test_methods, set(tags))

    logger.info(f"Discovery complete. Found {len(test_methods)} test files.")

    return test_methods


def discover_pytest(test_dir: Union[str, Path] = Path.cwd(), tags: list[str] = None):
    """
    Discovers test classes/modules from a given directory using pytest.

    Args:
        test_dir (Union[str, Path], optional): The directory to discover tests in. Defaults to Path.cwd().
        tags (list[str], optional): The tags to filter tests by. If None, all tests are returned. Defaults to None.

    Returns:
        list[TestInfo]: The discovered test classes/modules.

    Notes:
        Logs a debug message with the pytest command and the output from pytest.
        Logs an info message with the number of test classes/modules discovered.
    """
    test_dir = Path(test_dir).resolve()
    logger.info(f"Discovering pytest tests in {test_dir} (tags={tags})")

    output = _run_pytest_collect(str(test_dir), tags)
    logger.info(f"Discovered using pytest:\n {output}")
    test_methods = _parse_pytest_output(output)

    logger.info(f"Discovered {len(test_methods)} test classes/modules from pytest.")
    return test_methods


def _run_pytest_collect(test_dir: str, tags: Optional[list[str]]) -> str:
    """
    Executes a pytest command to collect test information and returns the stdout.

    Args:
        test_dir (str): The directory to collect tests from.
        tags (Optional[list[str]]): The tags to filter tests by. If None, all tests are collected.

    Returns:
        str: The stdout from the pytest command, stripped of trailing whitespace.
    """
    cmd = ["pytest", test_dir, "--collect-only", "-q"]
    if tags:
        cmd += ["-m", " or ".join(tags)]

    logger.info(f"Executing pytest discovery command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"pytest exited with code {result.returncode}")
        logger.debug(f"stderr:\n{result.stderr}")

    return result.stdout.strip()


def _parse_pytest_output(output: str) -> dict[str, TestInfo]:
    """
    Parses the output from a pytest discovery command and returns a dictionary mapping file paths to TestInfo objects.

    Args:
        output (str): The output from a pytest discovery command.

    Returns:
        dict[str, TestInfo]: A dictionary mapping file paths to TestInfo objects.
    """
    file_map: dict[str, TestInfo] = {}
    file_list: list[str] = []

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("<") or "tests collected" in line:
            continue

        parts = line.split("::")
        file_list.append(parts[0])

    for file_path in file_list:
        file_map[str(Path(file_path).resolve())] = python_loader(file_path)

    return file_map
