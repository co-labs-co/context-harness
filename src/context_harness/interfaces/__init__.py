"""Interfaces package for ContextHarness.

This package contains interface implementations that use the services layer.
Each interface (CLI, SDK, Web) provides a different way to interact with
ContextHarness functionality.

Subpackages:
    cli: Command-line interface using Click and Rich
    sdk: Programmatic SDK for Python applications
"""

from context_harness.interfaces.cli import cli_main
from context_harness.interfaces.sdk import Client

__all__ = [
    "cli_main",
    "Client",
]
