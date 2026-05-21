import importlib
import inspect
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Type, Union

from libs.test_ops.test_info import TestInfo, TestMethodInfo
from libs.test_ops.utils import compute_test_hash

logger = logging.getLogger(__name__)
_cache_lock = threading.Lock()
_module_cache: dict[str, Any] = {}
setup_all_names = {"setup_all"}
setup_test_names = {"setup_test"}
teardown_test_names = {"teardown_test"}
teardown_all_names = {"teardown_all"}


def python_loader(file_path: str) -> TestInfo:
    """Loads a Python module and extracts test class information.

    Args:
        file_path (str): Path to the Python module

    Returns:
        TestInfo: Test class information
    """
    logger.debug(file_path)
    file_path = Path(file_path)
    module = _load_module(file_path)
    _validate_module(module)
    test_classes = _load_class(module)
    if test_classes:
        logger.warning(
            f"Multiple test classes found in {file_path}. Using first one: {test_classes[0].__name__}"
        )
        test_class = test_classes[0]
        _validate_class(test_class, test_class.__name__)
        class_info = _extract_class_info(test_class, module, file_path)
    else:
        logger.warning(f"No test classes found in {file_path}")
        class_info = _extract_class_info(None, module, file_path)
    return class_info


def _load_module(file_path: Path) -> Any:
    """Loads a Python module from a file path and caches it for future use.

    Args:
        file_path (Path): Path to the Python module

    Returns:
        Any: Loaded Python module

    Raises:
        ModuleNotFoundError: If the module could not be loaded from the file path
    """
    module_name = file_path.stem
    cache_key = str(file_path.resolve())

    # Check cache first
    with _cache_lock:
        if cache_key in _module_cache:
            logger.debug(f"Using cached module: {module_name}")
            return _module_cache[cache_key]

    try:
        logger.debug(f"Loading module {module_name} from {file_path}")

        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for {file_path}")
        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules before execution
        original_module = sys.modules.get(module_name)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception:
            # Restore original module on failure
            if original_module is not None:
                sys.modules[module_name] = original_module
            else:
                sys.modules.pop(module_name, None)
            raise

        # Cache the module
        with _cache_lock:
            _module_cache[cache_key] = module

        logger.debug(f"Successfully loaded module: {module_name}")
        return module

    except Exception as e:
        raise ModuleNotFoundError(f"Failed to load module from {file_path}: {e}") from e


def _validate_module(module: Any) -> None:
    """
    Validates a Python module for loading.

    Checks that the module is not None, has a __name__ attribute, and has a __file__ attribute.

    Raises:
        ModuleNotFoundError: If the module is invalid
    """
    if module is None:
        raise ModuleNotFoundError("Module is None")

    if not hasattr(module, "__name__"):
        raise ModuleNotFoundError("Module missing __name__ attribute")

    if not hasattr(module, "__file__"):
        logger.warning("Module missing __file__ attribute")


def _load_class(module: Any) -> list[Any]:
    """
    Loads test classes from a given Python module.

    Iterates over the members of the module and checks if each member is a class.
    If the class has test methods (i.e., methods starting with "test_"), it is added to the list of test classes.

    Args:
        module (Any): The module to load test classes from

    Returns:
        list[Any]: A list of test classes found in the module
    """
    test_classes = []

    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Skip imported classes
        if obj.__module__ != module.__name__:
            continue

        # Check if class has test methods
        methods = inspect.getmembers(obj, predicate=inspect.isfunction)
        test_methods = [
            method_name for method_name, _ in methods if method_name.startswith("test_")
        ]

        if test_methods:
            test_classes.append(obj)
            logger.debug(
                f"Found test class: {name} with {len(test_methods)} test methods"
            )

    return test_classes


def _validate_class(test_class: Type, class_name: str):
    """
    Validates a test class for loading.

    Checks that the class is a class and has at least one test method.

    Args:
        test_class (Type): The class to validate
        class_name (str): The name of the class

    Raises:
        ValueError: If the class is invalid
    """
    if not inspect.isclass(test_class):
        raise ValueError(f"{class_name} is not a class")

    # Check if class has at least one test method
    methods = inspect.getmembers(test_class, predicate=inspect.isfunction)
    test_methods = [name for name, _ in methods if name.startswith("test_")]

    if not test_methods:
        raise ValueError(f"No test methods found in class {class_name}")


def _analyze_methods(file_obj: Union[Type, Any, None]):
    """
    Analyzes a Python file or class for test methods and setup/teardown methods.

    Args:
        file_obj (Union[Type, Any, None]): The file or class to analyze

    Returns:
        dict: A dictionary containing the analyzed methods. The dictionary has the following keys:

            - "setup_all": The name of the setup_all method, or None if not found
            - "setup_test": The name of the setup_test method, or None if not found
            - "teardown_test": The name of the teardown_test method, or None if not found
            - "teardown_all": The name of the teardown_all method, or None if not found
            - "test_methods": A list of TestMethodInfo objects for test methods found in the file or class
            - "other_methods": A list of method names that were not categorized as test, setup, or teardown methods

    Raises:
        ValueError: If the file or class is invalid
    """
    methods = inspect.getmembers(file_obj, predicate=inspect.isfunction)

    result = {
        "setup_all": None,
        "setup_test": None,
        "teardown_test": None,
        "teardown_all": None,
        "test_methods": [],
        "other_methods": [],
    }
    hash_obj = []
    for method_name, method_obj in methods:
        # Skip private methods
        if method_name.startswith("_"):
            continue

        # Categorize methods
        if method_name in setup_all_names:
            result["setup_all"] = method_name
            hash_obj.append(method_obj)
        elif method_name in setup_test_names:
            result["setup_test"] = method_name
            hash_obj.append(method_obj)
        elif method_name in teardown_test_names:
            result["teardown_test"] = method_name
            hash_obj.append(method_obj)
        elif method_name in teardown_all_names:
            result["teardown_all"] = method_name
            hash_obj.append(method_obj)
        elif method_name.startswith("test_"):
            test_method_info = _create_test_method_info(
                method_name, method_obj, hash_obj
            )
            result["test_methods"].append(test_method_info)
        else:
            result["other_methods"].append(method_name)

    return result


def _create_test_method_info(
    method_name: str, method_obj: Any, hash_obj: list[Any]
) -> TestMethodInfo:
    """
    Creates a TestMethodInfo object from a given method.

    Args:
        method_name (str): The name of the method
        method_obj (Any): The method object
        hash_obj (list[Any]): A list of objects to include in the hash calculation

    Returns:
        TestMethodInfo: A TestMethodInfo object representing the method

    Raises:
        ValueError: If the method is invalid
    """
    try:
        hash_obj.append(method_obj)

        # Find tags
        tags = getattr(method_obj, "_tags", set())

        return TestMethodInfo(
            name=method_name, hashkey=compute_test_hash(hash_obj), tags=tags
        )
    except Exception as e:
        logger.warning(f"Could not fully analyze method {method_name}: {e}")
        return TestMethodInfo(name=method_name, signature=inspect.Signature())


def _extract_class_info(test_class: Optional[Type], module: Any, file_path: Path):
    # Analyze methods
    """
    Extracts information about a test class from a given module.

    Args:
        test_class (Optional[Type]): The test class to extract information from
        module (Any): The module to extract information from
        file_path (Path): The path to the file containing the test class

    Returns:
        TestInfo: A TestInfo object containing information about the test class
    """

    if test_class:
        method_analysis = _analyze_methods(test_class)
    else:
        method_analysis = _analyze_methods(module)

    # Extract class info
    if test_class:
        base_classes = [
            base.__name__ for base in test_class.__bases__ if base is not object
        ]

    return TestInfo(
        name=test_class.__name__ if test_class else None,
        module_name=module.__name__,
        file_path=str(file_path),
        setup_all_method=method_analysis["setup_all"],
        setup_test_method=method_analysis["setup_test"],
        teardown_test_method=method_analysis["teardown_test"],
        teardown_all_method=method_analysis["teardown_all"],
        test_methods=method_analysis["test_methods"],
        base_classes=base_classes if test_class else [],
    )
