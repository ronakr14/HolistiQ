import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


@dataclass
class TestMethodInfo:
    name: str
    hashkey: Optional[str] = None
    tags: Optional[str] = None

    def get_summary(self):
        """Return a summary of the test method.

        Returns:
            A dictionary containing the test method name, hashkey, and tags.
        """
        return {"name": self.name, "hashkey": self.hashkey, "tags": self.tags}


@dataclass
class TestInfo:
    name: str
    module_name: str
    file_path: str
    setup_all_method: Optional[str] = None
    setup_test_method: Optional[str] = None
    teardown_test_method: Optional[str] = None
    teardown_all_method: Optional[str] = None
    test_methods: list[TestMethodInfo] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)

    def get_summary(self) -> dict[str, Any]:
        """Returns a summary of the test class.

        Returns:
            A dictionary containing the test class name, module name, file path, test count, setup methods, teardown methods, test methods, and base classes.
        """
        return {
            "class_name": self.name,
            "module_name": self.module_name,
            "file_path": self.file_path,
            "test_count": len(self.test_methods),
            "setup_methods": {
                "setup_all": self.setup_all_method,
                "setup_test": self.setup_test_method,
            },
            "teardown_methods": {
                "teardown_test": self.teardown_test_method,
                "teardown_all": self.teardown_all_method,
            },
            "test_methods": [method.name for method in self.test_methods],
            "base_classes": self.base_classes,
        }


def now_ts():
    """Returns the current timestamp in the format %Y%m%d%H%M%S.

    Returns:
        str: The current timestamp.
    """
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    return current_time


@dataclass
class TestResultInfo:

    file_path: str
    module_name: str
    test_class_name: str
    test_method_name: str
    status: Enum
    start_time: datetime
    end_time: datetime
    elapsed_seconds: float
    exception_info: Optional[tuple[str, str]] = None
    output: Optional[str] = None
    run_id: str = now_ts() + "_" + uuid.uuid4().hex[:6]
    test_id: Optional[str] = None

    @property
    def elapsed_time_formatted(self) -> str:
        return f"{self.elapsed_seconds:.3f}s"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "module": self.module_name,
            "test_class": self.test_class_name,
            "test_method": self.test_method_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "elapsed_time_sec": self.elapsed_seconds,
            "status": self.status.value,
            "exception": (
                {"type": self.exception_info[0], "message": self.exception_info[1]}
                if self.exception_info
                else None
            ),
            "output": self.output,
        }


@dataclass
class DatabaseRecord:
    branch: str
    hashkey: str
