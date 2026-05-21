from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class CommandResult:
    command: Union[str, list[str]]
    return_code: Optional[int]
    stdout: str
    stderr: str
    start_time: float
    end_time: float
    duration: float
    error: Optional[str] = None  # Python-level exception message (if any)


@dataclass
class AsyncCommandResult(CommandResult):
    pass