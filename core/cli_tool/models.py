from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class Argument:
    name: str
    flags: Optional[list[str]] = None  # e.g. ["--log-level", "-ll"]
    help: str = ""
    default: Any = None
    action: Optional[str] = None
    nargs: Optional[str] = None


@dataclass
class Command:
    name: str
    help: str = ""
    handler: Optional[Callable] = None
    arguments: list[Argument] = field(default_factory=list)
    subcommands: dict[str, "Command"] = field(default_factory=dict)

    def add_subcommand(self, cmd: "Command"):
        self.subcommands[cmd.name] = cmd
        return cmd


@dataclass
class CLIContext:
    run_id: str
    config: str
    app_start_time: datetime
