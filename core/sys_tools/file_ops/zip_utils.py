import os
import zipfile

from libs.mixers.logger_mixin import get_logger

logger = get_logger("Zip", component="Utils")


def extract_zip(zip_path, extract_to):
    """Extract contents of a zip file to a target directory.

    Args:
        zip_path (str): Path to the zip file to extract.
        extract_to (str): Path to the directory where zip contents should be extracted.

    Returns:
        None
    """
    logger.debug(f"Extracting zip from {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    logger.debug(f"Extracted zip to {extract_to}")


def list_all_files(directory, extensions=None):
    """Generate a list of all files within a directory and its subdirectories.

    Args:
        directory (str): Path to the directory to list files from.
        extensions (Optional[List[str]]): List of file extensions to filter by. If None, all files are listed.

    Yields:
        str: Path to a file
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if not extensions or file.lower().endswith(tuple(extensions)):
                yield os.path.join(root, file)


def create_zip(zip_path, files):
    """Create a zip file from a list of files.

    Args:
        zip_path (str): Path to the zip file to create.
        files (List[str]): List of file paths to include in the zip.

    Returns:
        None
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_ref:
        for file in files:
            zip_ref.write(file, os.path.basename(file))
