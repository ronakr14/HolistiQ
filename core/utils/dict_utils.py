from argparse import Namespace
from typing import Any, Dict, List, Union

from custom_logger.logging_util import get_logger

logger = get_logger("Dict", component="Utils")

NestedData = Union[Dict[str, Any], List[Any], Any]


def dict_to_namespace(data: NestedData) -> Any:
    """
    Convert dict to namespace recursively, handling nested structures.

    Args:
        data: Dictionary, list, or other data to convert

    Returns:
        Namespace object for dicts, converted list for lists, or original data
    """
    logger.debug("Converting dict to namespace")
    if isinstance(data, dict):
        return Namespace(
            **{key: dict_to_namespace(value) for key, value in data.items()}
        )
    elif isinstance(data, list):
        return [dict_to_namespace(item) for item in data]
    return data


def namespace_to_dict(data: NestedData) -> Any:
    """
    Convert namespace to dict recursively, handling nested structures.

    Args:
        data: Namespace, list, or other data to convert

    Returns:
        Dictionary for namespaces, converted list for lists, or original data
    """

    logger.debug("Converting namespace to dict")
    if isinstance(data, Namespace):
        return {key: namespace_to_dict(value) for key, value in vars(data).items()}
    elif isinstance(data, list):
        return [namespace_to_dict(item) for item in data]
    return data
