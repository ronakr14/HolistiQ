from pathlib import Path

from core.infrastructure.observability.logging.logging_util import get_logger
from core.utils.file_utils import generate_datetime_suffix
from core.utils.directory_utils import ensure_dir

logger = get_logger(__name__)


def export_html(
    data: str,
    file_name: str,
    format: str = "html",
    encoding: str = "utf-8",
    output_dir: str = None,
    include_timestamp: bool = True,
):
    if output_dir is None:
        output_dir = Path.cwd()

    if include_timestamp:
        file_name = f"{file_name}_{generate_datetime_suffix()}.{format}"
    else:
        file_name = f"{file_name}.{format}"

    file_path = Path(output_dir).resolve() / file_name

    ensure_dir(file_path.parent)

    try:
        with open(file_path, "w", encoding=encoding) as f:
            f.write(data)

        logger.info(f"Content written to {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to export to {file_path}: {e}")
        raise
