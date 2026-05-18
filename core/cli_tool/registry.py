"""
adapters/cli/registry.py — Plugin registry with framework-neutral command definitions.

Plugins register commands using plain @dataclass-based schemas (see schema.py).
Zero argparse or typer imports here — this module is the framework-agnostic core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from core.cli_tool.schema import Arg

Handler = Callable[..., None]


@dataclass
class SubCommand:
    name: str
    help: str
    handler: Handler
    args: list[Arg] = field(default_factory=list)


@dataclass
class CommandGroup:
    name: str
    help: str
    subcommands: list[SubCommand] = field(default_factory=list)
    # Set when the group itself is a runnable leaf (e.g. `holistiq run`)
    handler: Optional[Handler] = None
    args: list[Arg] = field(default_factory=list)


class PluginRegistry:
    """Singleton that collects all decorated commands."""

    def __init__(self) -> None:
        self._groups: dict[str, CommandGroup] = {}

    # ------------------------------------------------------------------ #
    # Decorators                                                           #
    # ------------------------------------------------------------------ #

    def register_command(
        self,
        name: str,
        help: str = "",
        args: Optional[list[Arg]] = None,
    ) -> Callable[[Handler], Handler]:
        """
        Register a top-level command (no subcommands).

        Usage
        -----
        @registry.register_command(
            "run",
            help="Start the application",
            args=[Arg("--env", FieldType.CHOICE, choices=["dev","prod"], default="dev")],
        )
        def handle_run(args):
            ...
        """

        def decorator(fn: Handler) -> Handler:
            if name in self._groups:
                self._groups[name].handler = fn
                if args:
                    self._groups[name].args = args
            else:
                self._groups[name] = CommandGroup(
                    name=name,
                    help=help,
                    handler=fn,
                    args=args or [],
                )
            return fn

        return decorator

    def register_subcommand(
        self,
        group: str,
        name: str,
        help: str = "",
        group_help: str = "",
        args: Optional[list[Arg]] = None,
    ) -> Callable[[Handler], Handler]:
        """
        Register a subcommand under a named group.

        Usage
        -----
        @registry.register_subcommand(
            group="data",
            name="scan",
            help="Scan data sources",
            args=[Arg("--source", FieldType.STR, default=".")],
        )
        def handle_scan(args):
            ...
        """

        def decorator(fn: Handler) -> Handler:
            if group not in self._groups:
                self._groups[group] = CommandGroup(name=group, help=group_help)

            self._groups[group].subcommands.append(
                SubCommand(name=name, help=help, handler=fn, args=args or [])
            )
            return fn

        return decorator

    def groups(self) -> dict[str, CommandGroup]:
        return self._groups


# Global singleton
registry = PluginRegistry()
