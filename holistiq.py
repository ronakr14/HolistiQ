"""
cli.py — Entry point.

Loads plugins, selects the adapter from HOLISTIQ_CLI env var,
builds and runs the CLI. This file never changes.
"""

# import os
# import sys

from dotenv import load_dotenv

from core.cli_tool import get_adapter
from core.cli_tool.loader import load_plugins

# sys.path.append(os.path.abspath("../apps"))


def main() -> None:
    load_dotenv()
    load_plugins()
    adapter = get_adapter()
    adapter.build()
    adapter.run()
