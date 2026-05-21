from pathlib import Path

import yaml

from custom_logger.logging_util import get_logger
from core.loaders.txt_loader import _load_file_contents

logger = get_logger(__name__)


def load_yaml(path: Path, encoding: str = "utf-8"):
    logger.debug(f"loading yaml from {path}")
    try:
        contents = _load_file_contents(path, encoding)
        yaml_data = yaml.safe_load(contents) or {}
        return yaml_data
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML config: {e}")
