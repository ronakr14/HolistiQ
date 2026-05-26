from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, Union

import git
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from custom_logger.logging_util import get_logger

logger = get_logger("Git", component="Utils")


# Cache for repository objects to avoid repeated initialization
_repo_cache = {}


@lru_cache(maxsize=64)
def _get_repo_from_path(file_path: str) -> Optional[git.Repo]:
    """
    Retrieves a git repository object for the given file path.

    This function caches the repository objects to avoid repeated initialization.

    Args:
        file_path (str): The path to the file.

    Returns:
        Optional[git.Repo]: The git repository object or None if the file path is not within a git repository.
    """

    try:
        file_dir = Path(file_path).parent.resolve()
        cache_key = str(file_dir)

        if cache_key not in _repo_cache:
            _repo_cache[cache_key] = git.Repo(file_dir, search_parent_directories=True)

        return _repo_cache[cache_key]

    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.debug(f"Not a git repository: {file_path} - {e}")
        return None
    except Exception as e:
        logger.error(f"Error accessing git repository: {e}")
        return None


def _normalize_file_path(file_path: Union[str, Path], repo_root: str) -> str:
    """
    Normalizes a file path relative to a git repository root.

    Args:
        file_path (Union[str, Path]): The file path to normalize.
        repo_root (str): The git repository root.

    Returns:
        str: The normalized file path.

    Raises:
        ValueError: If the file path is not within the git repository.
    """
    file_path = Path(file_path).resolve()
    repo_root = Path(repo_root).resolve()

    try:
        rel_path = file_path.relative_to(repo_root)
        return str(rel_path).replace("\\", "/")
    except ValueError:
        logger.warning(f"File {file_path} is not within repository {repo_root}")
        return str(file_path)


@lru_cache(maxsize=32)
def _get_tracked_files(repo: git.Repo) -> set:
    """
    Returns a set of tracked files in a given git repository.

    Args:
        repo (git.Repo): The git repository to retrieve tracked files from.

    Returns:
        set: A set of tracked files.

    Raises:
        GitCommandError: If the git command to retrieve tracked files fails.
    """
    try:
        tracked_files = repo.git.ls_files().split("\n")
        return {f.strip() for f in tracked_files if f.strip()}
    except GitCommandError as e:
        logger.error(f"Failed to get tracked files: {e}")
        return set()


def is_file_in_git_repo(file_path: Union[str, Path]) -> bool:
    """
    Checks if a file is in a git repository.

    Args:
        file_path (Union[str, Path]): The file path to check.

    Returns:
        bool: True if the file is tracked, False otherwise.

    Raises:
        Exception: If an error occurs while checking if the file is tracked.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.warning(f"File does not exist: {file_path}")
        return False

    repo = _get_repo_from_path(str(file_path))
    if not repo:
        return False

    try:
        normalized_path = _normalize_file_path(file_path, repo.working_tree_dir)
        tracked_files = _get_tracked_files(repo)

        is_tracked = normalized_path in tracked_files
        logger.debug(f"File {file_path} tracked: {is_tracked}")
        return is_tracked

    except Exception as e:
        logger.error(f"Error checking if file is tracked: {e}")
        return False


def get_branch_name_from_file(file_path: Union[str, Path]) -> Optional[str]:
    """
    Retrieves the branch name associated with a given file path.

    Args:
        file_path (Union[str, Path]): The file path to retrieve the branch name from.

    Returns:
        Optional[str]: The branch name if successful, None otherwise.

    Raises:
        Exception: If an error occurs while retrieving the branch name.
    """
    repo = _get_repo_from_path(str(file_path))
    if not repo:
        return None

    try:
        branch_name = repo.active_branch.name
        logger.debug(f"Current branch: {branch_name}")
        return branch_name

    except Exception as e:
        logger.warning(f"Could not get branch name: {e}")
        # Handle detached HEAD state or other issues
        try:
            return repo.git.rev_parse("--abbrev-ref", "HEAD")
        except Exception:
            return None


def get_git_path_with_repo_folder(file_path: Union[str, Path]) -> str:
    """
    Retrieves a file path with the git repository folder name.

    Args:
        file_path (Union[str, Path]): The file path to retrieve the git repository folder name from.

    Returns:
        str: The file path with the git repository folder name, or the absolute file path if not in a git repository.

    Raises:
        Exception: If an error occurs while retrieving the git repository folder name.
    """
    file_path = Path(file_path).resolve()
    repo = _get_repo_from_path(str(file_path))

    if not repo or not repo.working_tree_dir:
        logger.debug(f"File not in git repo, returning absolute path: {file_path}")
        return str(file_path)

    try:
        repo_root = Path(repo.working_tree_dir)
        repo_name = repo_root.name
        rel_path = _normalize_file_path(file_path, repo.working_tree_dir)

        result = f"{repo_name}/{rel_path}"
        logger.debug(f"Git path: {result}")
        return result

    except Exception as e:
        logger.error(f"Error creating git path: {e}")
        return str(file_path)


def get_repo_info(file_path: Union[str, Path]) -> Optional[Tuple[str, str, str]]:
    """
    Retrieves information about the git repository associated with a file path.

    Args:
        file_path (Union[str, Path]): The file path to retrieve the git repository information from.

    Returns:
        Optional[Tuple[str, str, str]]: A tuple containing the repository name, branch name, and relative path
            if successful, None otherwise.

    Raises:
        Exception: If an error occurs while retrieving the git repository information.
    """
    repo = _get_repo_from_path(str(file_path))
    if not repo:
        return None

    try:
        repo_name = Path(repo.working_tree_dir).name
        branch_name = get_branch_name_from_file(file_path)
        rel_path = _normalize_file_path(file_path, repo.working_tree_dir)

        return (repo_name, branch_name, rel_path)

    except Exception as e:
        logger.error(f"Error getting repo info: {e}")
        return None


def get_branches_with_file(file_path: Union[str, Path]) -> List[str]:
    """Retrieves a list of branches that contain a given file.

    Args:
        file_path (Union[str, Path]): The file path to search for.

    Returns:
        List[str]: A list of branch names that contain the given file.

    Raises:
        Exception: If an error occurs while searching for the file.
    """
    repo = _get_repo_from_path(str(file_path))
    if not repo:
        logger.warning(f"File not in git repository: {file_path}")
        return []

    try:
        normalized_path = _normalize_file_path(file_path, repo.working_tree_dir)
        branches_with_file = []

        logger.debug(f"Searching for file {normalized_path} across branches")

        for branch in repo.branches:
            try:
                # Use ls-tree to check if file exists in branch
                output = repo.git.ls_tree("-r", "--name-only", branch.name)
                files = {f.strip() for f in output.splitlines() if f.strip()}

                if normalized_path in files:
                    branches_with_file.append(branch.name)
                    logger.debug(f"File found in branch: {branch.name}")

            except GitCommandError as e:
                logger.debug(f"Could not check branch {branch.name}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error checking branch {branch.name}: {e}")
                continue

        logger.info(
            f"File {normalized_path} found in {len(branches_with_file)} branches"
        )
        return branches_with_file

    except Exception as e:
        logger.error(f"Error searching branches for file: {e}")
        return []


def clear_cache() -> None:
    """
    Clears all caches associated with GitOps.

    This function is intended to be used when the program is finished using the GitOps module.
    It is not necessary to call this function, as the caches will be automatically cleared when the program terminates.
    However, calling this function can be useful in certain situations, such as when the program needs to free up memory.

    """
    _repo_cache.clear()
    _get_repo_from_path.cache_clear()
    _get_tracked_files.cache_clear()
    logger.debug("GitOps caches cleared")
