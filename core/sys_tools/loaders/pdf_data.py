from pathlib import Path
from typing import Union

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from core.infrastructure.observability.logging.logging_util import get_logger


logger = get_logger(__name__)


def extract_pdf_text_robust(path: Union[str, Path]) -> str:
    logger.debug(f"Extracting text from PDF using OCR: {path}")
    path = Path(path).resolve()
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        text = page.get_text()
        if not text.strip():
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        full_text += text + "\n"
    return full_text
