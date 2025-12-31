"""CLI package for ContextHarness.

Command-line interface using Click for argument parsing and Rich for output.
This package provides the `context-harness` command with subcommands for:

- init: Initialize ContextHarness in a project
- mcp: Manage MCP server configurations
- skill: Manage and install skills

The CLI uses services from the services package and formats output with Rich.

Example:
    from context_harness.interfaces.cli import cli_main
    cli_main()  # Run the CLI
"""

from context_harness.interfaces.cli.main import cli_main, main

__all__ = [
    "cli_main",
    "main",
]
