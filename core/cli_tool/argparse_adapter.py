"""
adapters/cli/argparse_adapter.py — Argparse implementation of BaseCLIAdapter.

Translates Arg schema → argparse.ArgumentParser calls.
Only this file knows about argparse. Plugins never import it.
"""

from __future__ import annotations

import argparse
import sys

from core.cli_tool.base import BaseCLIAdapter
from core.cli_tool.bootstrap import bootstrap
from core.cli_tool.registry import registry
from core.cli_tool.schema import Arg, FieldType


def _apply_args(parser: argparse.ArgumentParser, args: list[Arg]) -> None:
    """Translate a list of neutral Arg objects into argparse calls."""
    for arg in args:
        kwargs: dict = {"help": arg.help}

        if arg.type == FieldType.BOOL:
            kwargs["action"] = "store_true"
            kwargs["default"] = False

        elif arg.type == FieldType.CHOICE:
            kwargs["choices"] = arg.choices
            kwargs["default"] = arg.default
            kwargs["type"] = str

        else:
            type_map = {
                FieldType.STR: str,
                FieldType.INT: int,
                FieldType.FLOAT: float,
            }
            kwargs["type"] = type_map[arg.type]
            kwargs["default"] = arg.default

            if arg.is_option:
                kwargs["required"] = arg.required

        if arg.is_option:
            parser.add_argument(arg.name, **kwargs)
        else:
            # Positional — argparse doesn't accept required/default the same way
            kwargs.pop("required", None)
            if arg.default is not None:
                kwargs["nargs"] = "?"
            parser.add_argument(arg.dest, **kwargs)


class ArgparseAdapter(BaseCLIAdapter):

    def __init__(self) -> None:
        self._parser: argparse.ArgumentParser | None = None

    def build(self) -> None:
        root = argparse.ArgumentParser(
            prog="holistiq",
            description="Holistiq — modular CLI",
        )
        root.add_argument(
            "-ll",
            "--log-level",
            default="INFO",
            help="set logging level",
            dest="log_level",
        )
        top_sub = root.add_subparsers(dest="command", metavar="<command>")
        top_sub.required = True

        for group_name, group in registry.groups().items():
            if group.subcommands:
                group_parser = top_sub.add_parser(group_name, help=group.help)

                if group.handler:
                    group_parser.set_defaults(_handler=group.handler)
                    _apply_args(group_parser, group.args)

                sub = group_parser.add_subparsers(
                    dest=f"{group_name}_subcommand",
                    metavar="<subcommand>",
                )
                sub.required = True

                for cmd in group.subcommands:
                    cmd_parser = sub.add_parser(cmd.name, help=cmd.help)
                    cmd_parser.set_defaults(_handler=cmd.handler)
                    _apply_args(cmd_parser, cmd.args)

            else:
                cmd_parser = top_sub.add_parser(group_name, help=group.help)
                if group.handler:
                    cmd_parser.set_defaults(_handler=group.handler)
                _apply_args(cmd_parser, group.args)

        self._parser = root

    def run(self) -> None:
        if self._parser is None:
            raise RuntimeError("ArgparseAdapter.build() must be called before run()")
        args = vars(self._parser.parse_args())
        log_level = args.pop("log_level")
        ctx = bootstrap(log_level=log_level)
        handler = args.pop("_handler")
        if handler is None:
            self._parser.print_help()
            sys.exit(1)
        handler(ctx, args)
