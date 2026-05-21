from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ArgMeta:
    """Represents a single function argument."""

    name: str
    type_hint: Optional[str] = None  # e.g. "int", "str", "list[str]"
    default: Optional[Any] = None  # Only set for kwargs
    is_kwarg: bool = False  # True if has a default value
    is_variadic: bool = False  # True if *args or **kwargs - skipped in CLI


@dataclass
class FunctionMeta:
    """Represents a scanned function with all CLI-relevant metadata."""

    name: str
    module: str  # e.g. "pipelines.etl"
    file_path: Path
    args: list[ArgMeta] = field(default_factory=list)
    docstring: Optional[str] = None
    source_lines: Optional[tuple[int, int]] = None  # (start, end) for LLM context

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}"

    @property
    def positional_args(self) -> list[ArgMeta]:
        return [a for a in self.args if not a.is_kwarg and not a.is_variadic]

    @property
    def keyword_args(self) -> list[ArgMeta]:
        return [a for a in self.args if a.is_kwarg]

    def usage_signature(self) -> str:
        """Human-readable signature for docs and --help."""
        parts = []
        for arg in self.positional_args:
            hint = f":{arg.type_hint}" if arg.type_hint else ""
            parts.append(f"<{arg.name}{hint}>")
        for arg in self.keyword_args:
            hint = f" ({arg.type_hint})" if arg.type_hint else ""
            default = f"={repr(arg.default)}" if arg.default is not None else ""
            parts.append(f"[--{arg.name}{hint}{default}]")
        return " ".join(parts)
