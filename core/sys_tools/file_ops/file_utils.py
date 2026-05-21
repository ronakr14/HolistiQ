from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional
# import os
# import sys
# from pathlib import Path
# import tempfile
# from typing import Union

from core.infrastructure.observability.logging.logging_util import get_logger
from core.utils.datetime_utils import now_utc_ts

logger = get_logger(__name__)


def generate_datetime_suffix(now: datetime = None) -> str:
    logger.debug("Generating datetime suffix")
    now = now_utc_ts()
    return now.strftime("%Y%m%d%H%M%S")


def move_file(src: Path, dst: Path) -> Path:
    """
    Atomically moves a file from the source path to the destination path.

    If the move is cross-filesystem, falls back to copying the file and deleting the source.

    Args:
        src (Path): Source file path
        dst (Path): Destination file path

    Returns:
        Path: The destination path of the moved file
    """

    logger.info("Moving file %s -> %s", src, dst)

    if not src.exists():
        logger.error("Source file does not exist: %s", src)
        raise FileNotFoundError(src)

    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        src.replace(dst)
        logger.debug("File moved atomically")
    except OSError:
        logger.warning("Cross-filesystem move detected. Falling back to copy+delete.")
        shutil.copy2(src, dst)
        src.unlink()

    logger.info("File move completed: %s", dst)
    return dst


def get_latest_file(folder: str, prefix: str, suffix: str = "") -> Optional[Path]:
    """
    Retrieves the latest file from a given folder based on its modification time.

    Args:
        folder (str): The folder to search for files
        prefix (str): The prefix that files must start with
        suffix (str, optional): The suffix that files must end with. Defaults to "".

    Returns:
        Optional[Path]: The latest file, or None if no matching files are found
    """
    folder_path = Path(folder)

    files = [
        f
        for f in folder_path.iterdir()
        if f.is_file()
        and f.name.startswith(prefix)
        and (f.name.endswith(suffix) if suffix else True)
    ]

    if not files:
        return None

    return max(files, key=lambda f: f.stat().st_mtime)



# def is_file_locked(path: Union[Path, str]) -> bool:
#     """
#     Check if a file is locked by another process.

#     This function checks if a file is open by another process by attempting to
#     open it in exclusive mode. If the file does not exist, it returns False.
#     If the file exists but an error occurs while attempting to open it, it
#     returns True.

#     If the platform is Windows, the function will return True if a
#     PermissionError occurs while attempting to open the file, indicating that
#     the file is locked by another process.

#     If the platform is POSIX, the function will return False, as POSIX does
#     not provide a reliable way to detect if a file is open by another process.

#     Args:
#         path (Path): path to the file to check

#     Returns:
#         bool: True if the file is locked by another process, False otherwise
#     """
#     logger.debug(f"Checking if file is locked: {path}")
#     path = Path(path).resolve()
#     if not path.exists():
#         return False  # doesn't exist = not locked

#     if sys.platform.startswith("win"):
#         try:
#             fd = os.open(str(path), os.O_RDWR | os.O_EXCL)
#             os.close(fd)
#             return False
#         except PermissionError:
#             return True
#         except OSError:
#             # Covers edge cases (read-only file, etc.)
#             return True
#         except Exception:
#             return True
#     else:
#         # POSIX can't reliably detect "open by another process"
#         return False


# def _timestamped_name(base_name: str, ext: str, add_ts: bool = True, ts_fmt: str = "%Y%m%d%H%M%S") -> str:
#     logger.debug("generating timestamp based filename")
#     ts = datetime.now().strftime(ts_fmt) if add_ts else ""
#     return f"{base_name}{('_' + ts) if ts else ''}.{ext}"


# def _atomic_write_bytes(target: Path, data_bytes: bytes) -> Path:
#     logger.debug("writing bytes to temp file")
#     # write to temporary file in same dir then replace
#     tmp = Path(tempfile.NamedTemporaryFile(delete=False, dir=str(target.parent)).name)
#     try:
#         tmp.write_bytes(data_bytes)
#         tmp.replace(target)
#         return target
#     finally:
#         if tmp.exists():
#             try:
#                 tmp.unlink()
#             except Exception:
#                 pass


# def _atomic_write_text(target: Path, text: str, encoding: str = "utf-8") -> Path:
#     logger.debug("writing text to temp file")
#     return _atomic_write_bytes(target, text.encode(encoding))