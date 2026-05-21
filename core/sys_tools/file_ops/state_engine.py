import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def load_ignore_file(file_path: Union[str, Path]) -> list[str]:
    logger.debug("[STATE]: Loading ignore file...")
    ignore_list = []
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"[STATE]: Ignore file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # skip comments (# ...) and empty lines
            if not line or line.startswith("#"):
                continue
            ignore_list.append(line)

    return ignore_list


def log_summary(stats: dict):

    content = (
        "\n===== Sync Summary =====\n"
        f"\t ✅ New:   {stats['new']}\n"
        f"\t ⏩ Updated:   {stats['updated']}\n"
        f"\t ⚠️ Local Conflict:    {stats['local_conflict']}\n"
        f"\t ⚠️ Remote Conflict: {stats['remote_conflict']}\n"
        f"\t ❌ Skipped:     {stats['skipping']}\n"
        "========================"
    )
    logger.info(f"[STATE]: {content}")


def _get_state_file() -> Path:
    """
    Returns the path to the sync state file.

    The sync state file is a JSON file that contains the current sync state, including
    the mapping of local files to drive files, the last change token used to
    poll for changes, and the IDs of the drive root and recycle folders.

    Returns:
        Path: The path to the sync state file
    """
    logger.debug("[ENGINE-STATE]: Fetching sync state file path.")
    state_file_path = Path(os.getenv("GDRIVE_CREDENTIAL_PATH"))
    return state_file_path / "sync_state.json"


def load_state() -> dict:
    """
    Load the sync state from the state file.

    The state file is a JSON file that contains the current sync state, including
    the mapping of local files to drive files, the last change token used to
    poll for changes, and the IDs of the drive root and recycle folders.

    Returns:
        dict: The sync state as a dictionary
    """
    logger.debug("[ENGINE-STATE]: Loading sync state file")
    state_file = _get_state_file()
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "files": {},
            "last_change_token": None,
            "drive_root_id": None,
        }


def save_state(s) -> None:
    """
    Save the sync state to the state file.

    The state file is a JSON file that contains the current sync state, including
    the mapping of local files to drive files, the last change token used to
    poll for changes, and the IDs of the drive root and recycle folders.

    Args:
        s (dict): The sync state as a dictionary
    """
    state_file = _get_state_file()
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, sort_keys=True)
    logger.debug("[ENGINE-STATE]: Saved sync state file")


def safe_conflict_name(name: str) -> str:
    """
    Creates a conflict name by appending a timestamp to the file name.

    Example: for a file named "foo.txt", the conflict name would be
    "foo_conflict_20221225-123400.txt"

    Args:
        name: The original file name

    Returns:
        The conflict name as a string
    """
    logger.debug(f"[ENGINE-STATE]: Getting conflict name for {name}")
    stem = Path(name).stem
    suf = Path(name).suffix
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stem}_conflict_{ts}{suf}"


def get_filename_by_driveid(index, drive_id):
    for filename, meta in index["files"].items():
        if meta["drive_id"] == drive_id:
            return filename
    return None  # if not found


def is_file_locked(path: Path) -> bool:
    if not path.exists():
        return False

    if sys.platform.startswith("win"):
        try:
            fd = os.open(str(path), os.O_RDWR | os.O_EXCL)
            os.close(fd)
            return False
        except PermissionError:
            return True
        except OSError:
            # Covers edge cases (read-only file, etc.)
            return True
    else:
        # POSIX can't reliably detect "open by another process"
        return False
