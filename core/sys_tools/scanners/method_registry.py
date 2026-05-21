"""
registry.py - Builds and manages the nested command tree.

Converts flat module→functions scan results into a nested tree keyed by
folder segments → file → function name. Also detects overloaded function
names across different modules and flags them for LLM analysis.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from custom_logger.logging_util import get_logger
from core.scanners.file_scanner import FunctionMeta

logger = get_logger(__name__)


@dataclass
class OverloadConflict:
    """Represents two functions with the same name in different modules."""

    function_name: str
    instances: list[FunctionMeta]
    llm_analysis: Optional[str] = None  # Populated by llm_analyzer
    merge_recommendation: Optional[str] = None  # "merge" | "keep_separate" | "review"
    similarity_score: Optional[float] = None  # 0.0–1.0 from LLM


# Type alias for the nested command tree:
# { "pipelines": { "etl": { "run": FunctionMeta, ... }, ... }, ... }
CommandTree = dict[str, "CommandTree | FunctionMeta"]


class Registry:
    """
    Central store for the command tree and conflict tracking.

    Usage:
        registry = Registry()
        registry.build(scan_results)
        tree = registry.tree
        conflicts = registry.conflicts
    """

    def __init__(self):
        self._tree: CommandTree = {}
        self._all_functions: list[FunctionMeta] = []
        self._conflicts: list[OverloadConflict] = []
        self._name_index: dict[str, list[FunctionMeta]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, scan_results: dict[str, list[FunctionMeta]]) -> None:
        """
        Populate the registry from scan_results (module → [FunctionMeta]).

        This is idempotent — calling build() again replaces previous state.
        """
        self._tree = {}
        self._all_functions = []
        self._conflicts = []
        self._name_index = defaultdict(list)

        for module, functions in scan_results.items():
            # module = "pipelines.etl" → segments = ["pipelines", "etl"]
            segments = module.split(".")

            for func in functions:
                self._all_functions.append(func)
                self._name_index[func.name].append(func)
                self._insert(self._tree, segments, func)

        self._detect_conflicts()

    def _insert(
        self,
        tree: CommandTree,
        segments: list[str],
        func: FunctionMeta,
    ) -> None:
        """
        Recursively insert a function into the nested tree.

        Path: segments = ["pipelines", "etl"], func.name = "run"
        Result: tree["pipelines"]["etl"]["run"] = func
        """
        node = tree
        for seg in segments:
            if seg not in node:
                node[seg] = {}
            node = node[seg]  # type: ignore[assignment]

        # At the leaf dict, insert by function name
        if func.name in node:
            existing = node[func.name]
            if isinstance(existing, FunctionMeta):
                logger.warning(
                    f"Name collision at leaf: {func.qualified_name} "
                    f"conflicts with {existing.qualified_name}"
                )
            # Still insert — conflict is tracked separately via _name_index
        node[func.name] = func

    # ------------------------------------------------------------------
    # Conflict Detection
    # ------------------------------------------------------------------

    def _detect_conflicts(self) -> None:
        """
        Find function names that appear in more than one module.
        These are candidates for LLM analysis.
        """
        for name, instances in self._name_index.items():
            if len(instances) > 1:
                conflict = OverloadConflict(
                    function_name=name,
                    instances=instances,
                )
                self._conflicts.append(conflict)
                logger.info(
                    f"Overload detected: '{name}' found in "
                    + ", ".join(f.module for f in instances)
                )

    # ------------------------------------------------------------------
    # Public Interface
    # ------------------------------------------------------------------

    @property
    def tree(self) -> CommandTree:
        return self._tree

    @property
    def all_functions(self) -> list[FunctionMeta]:
        return self._all_functions

    @property
    def conflicts(self) -> list[OverloadConflict]:
        return self._conflicts

    @property
    def has_conflicts(self) -> bool:
        return len(self._conflicts) > 0

    def get_function(self, *path: str) -> Optional[FunctionMeta]:
        """
        Look up a function by its tree path.

        Example: registry.get_function("pipelines", "etl", "run")
        Returns FunctionMeta or None if not found.
        """
        node = self._tree
        for segment in path:
            if not isinstance(node, dict) or segment not in node:
                return None
            node = node[segment]  # type: ignore[assignment]
        return node if isinstance(node, FunctionMeta) else None

    def iter_functions(self):
        """Flat iterator over all FunctionMeta in the registry."""
        yield from self._all_functions

    def iter_leaves(self, tree: Optional[CommandTree] = None, prefix: tuple = ()):
        """
        Recursively yield (path_tuple, FunctionMeta) for every leaf in tree.

        Example yields:
            (("pipelines", "etl", "run"), FunctionMeta(...))
        """
        if tree is None:
            tree = self._tree

        for key, value in tree.items():
            current_path = prefix + (key,)
            if isinstance(value, FunctionMeta):
                yield current_path, value
            elif isinstance(value, dict):
                yield from self.iter_leaves(value, current_path)

    def summary(self) -> str:
        """Human-readable summary of the registry state."""
        lines = [
            f"Registry: {len(self._all_functions)} function(s) across "
            f"{len(set(f.module for f in self._all_functions))} module(s)",
        ]
        if self._conflicts:
            lines.append(f"  ⚠️  {len(self._conflicts)} overloaded name(s) detected:")
            for c in self._conflicts:
                modules = ", ".join(f.module for f in c.instances)
                lines.append(f"     '{c.function_name}' in: {modules}")
        else:
            lines.append("  ✓ No name conflicts detected")
        return "\n".join(lines)
