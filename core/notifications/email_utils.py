import mimetypes
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Tuple
from core.infrastructure.observability.logging.logging_util import get_logger

logger = get_logger(__name__)


def is_html(text: str) -> bool:
    """
    Detects if a given string contains HTML content.

    Args:
        text (str): The text to check.

    Returns:
        bool: True if the string contains HTML tags, False otherwise.
    """
    logger.debug("Detecting HTML content.")
    if not text or not isinstance(text, str):
        return False
    soup = BeautifulSoup(text, "html.parser")
    return bool(soup.find())


def load_attachment(path: str) -> Tuple[bytes, str, str]:
    """
    Load an attachment from a given path, which can be a local file or a remote URL.

    Args:
        path (str): The path to the attachment.

    Returns:
        Tuple[bytes, str, str]: A tuple containing the attachment data, the MIME type, and the subtype.

    Raises:
        requests.exceptions.RequestException: If the remote attachment cannot be downloaded.
    """
    logger.debug(f"Loading attachment: {path}")

    filename = Path(path).name
    ctype, _ = mimetypes.guess_type(filename)
    maintype, subtype = (ctype or "application/octet-stream").split("/", 1)

    if str(path).lower().startswith("http"):
        logger.info(f"Downloading remote attachment: {path}")
        response = requests.get(path, timeout=30)
        response.raise_for_status()
        data = response.content
    else:
        with open(path, "rb") as f:
            data = f.read()

    return data, maintype, subtype