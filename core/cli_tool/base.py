"""
adapters/cli/base.py — Abstract CLI adapter interface.

Every CLI framework adapter (argparse, typer, click, …) must implement
this interface. The rest of the application depends only on this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCLIAdapter(ABC):
    """
    Translates the framework-neutral plugin registry into a runnable CLI.
    """

    @abstractmethod
    def build(self) -> None:
        """
        Read the registry and construct the CLI app/parser.
        Called once at startup after all plugins are loaded.
        """
        ...

    @abstractmethod
    def run(self) -> None:
        """
        Parse sys.argv and dispatch to the appropriate handler.
        """
        ...
