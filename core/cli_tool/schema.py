"""
adapters/cli/schema.py — Framework-neutral argument definitions.

Plugins declare their arguments using these dataclasses.
No argparse, no typer — just plain data.
The active CLI adapter is responsible for translating these
into whatever the underlying framework expects.

Supported field types map as follows:

  FieldType   | argparse                  | typer
  ------------|---------------------------|-----------------------------
  STR         | type=str                  | str annotation
  INT         | type=int                  | int annotation
  FLOAT       | type=float                | float annotation
  BOOL        | action="store_true"       | bool (Optional, default False)
  CHOICE      | choices=[...], type=str   | Enum or Annotated[str, ...]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class FieldType(Enum):
    STR = auto()
    INT = auto()
    FLOAT = auto()
    BOOL = auto()  # flag — presence means True
    CHOICE = auto()  # requires `choices` list


@dataclass
class Arg:
    """
    A single CLI argument or option.

    Examples
    --------
    Arg("--env", FieldType.CHOICE, choices=["dev", "prod"], default="dev")
    Arg("--deep", FieldType.BOOL)
    Arg("--source", FieldType.STR, default=".", help="Path to scan")
    Arg("--target", FieldType.STR, required=True, help="Target DB URL")
    """

    name: str  # "--env" or positional "path"
    type: FieldType = FieldType.STR
    default: Any = None
    required: bool = False
    help: str = ""
    choices: list[str] = field(default_factory=list)  # only for CHOICE

    @property
    def is_option(self) -> bool:
        """True if this is a --flag, False if it's a positional."""
        return self.name.startswith("-")

    @property
    def dest(self) -> str:
        """The attribute name on the parsed args namespace."""
        return self.name.lstrip("-").replace("-", "_")


@dataclass
class CliContext:
    run_id: str
    app_start_time: datetime

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "app_start_time": self.app_start_time,
        }
