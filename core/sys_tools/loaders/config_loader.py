import os
import re
from pathlib import Path
from typing import Any, Union

from core.loaders.yaml_loader import load_yaml
from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def _resolve_env(value: Any) -> Any:
    """
    Recursively walk config values.
    Strings containing ${ENV_VAR} are replaced with the actual env value.
    """
    logger.debug("resolving env variables in config")
    if isinstance(value, str):
        # Replace all occurrences of ${VAR} with the environment variable value
        pattern = re.compile(r"\$\{(\w+)\}")

        def _replace(match):
            env_var = match.group(1)
            resolved = os.getenv(env_var)
            if resolved is None:
                raise EnvironmentError(
                    f"Config references env var '{env_var}' but it is not set in .env or environment."
                )
            return resolved

        try:
            return pattern.sub(_replace, value)
        except re.error:  # This should not happen with our pattern
            return value
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(i) for i in value]
    return value


def _validate_config_file(path: Path) -> bool:
    """
    Validates the given Path object to ensure it is a valid YAML config file.

    Args:
        path (Path): Path to YAML config file

    Raises:
        FileNotFoundError: If config file is not found
        ValueError: If config file is not in YAML format
    """
    logger.debug("validating config file")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    if path.suffix.lower() not in (".yml", ".yaml"):
        raise ValueError(f"Config file must be in YAML format: {path}")
    return True


def _extract_keys(config_data: dict, keys: list[str], *, strict: bool = True) -> dict:
    """
    Extracts a subset of config keys from a given config dictionary.

    Args:
        config_data (dict): Config dictionary
        keys (list[str]): List of key paths to extract
        strict (bool, optional): If True, raises KeyError if key path is missing. Defaults to True.

    Returns:
        dict: Extracted config keys with nested structure

    Raises:
        KeyError: If strict is True and key path is missing
    """
    result = {}

    for key_path in keys:
        parts = key_path.split(".")
        node = config_data
        found = True

        # Traverse intermediate levels
        for part in parts[:-1]:
            if part in node:
                node = node[part]
            else:
                found = False
                break

        # Check leaf key
        leaf_key = parts[-1]
        if found and leaf_key in node:
            # Build nested structure in result
            d = result
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[leaf_key] = node[leaf_key]
        else:
            if strict:
                raise KeyError(f"Missing key path: '{key_path}' in config")
            else:
                logger.error(f"Skipping missing key path: '{key_path}'")
    return result


def validate_load_config(
    config_path: Union[str, Path], extract_keys: Union[list, str, None] = None
) -> dict:
    """
    Load and validate the YAML config file.
    API keys referenced as ${ENV_VAR} are resolved from .env.

    Returns the fully resolved config dict.
    """

    path = Path(config_path)
    _validate_config_file(path=path)

    config_data = load_yaml(path)
    logger.info(f"config file {path} loaded.")

    config_data = _resolve_env(config_data)
    logger.info(f"resolved env variables in config file {path}")

    if extract_keys:
        logger.info(f"extracting keys: {extract_keys} from config data")
        if isinstance(extract_keys, str):
            extract_keys = [extract_keys]
        return _extract_keys(config_data=config_data, keys=extract_keys)

    return config_data
