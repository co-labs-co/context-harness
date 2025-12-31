"""Main CLI entry point for ContextHarness.

This module assembles all command groups and provides the main entry point.
"""

from __future__ import annotations

import click

from context_harness import __version__
from context_harness.interfaces.cli.init_cmd import init_command
from context_harness.interfaces.cli.mcp_cmd import mcp_group
from context_harness.interfaces.cli.skill_cmd import skill_group


@click.group()
@click.version_option(version=__version__, prog_name="context-harness")
def main() -> None:
    """ContextHarness CLI - Initialize agent frameworks in your project.

    A context-aware agent framework for OpenCode.ai that maintains session
    continuity through user-driven compaction cycles.
    """
    pass


# Register command groups
main.add_command(init_command, name="init")
main.add_command(mcp_group, name="mcp")
main.add_command(skill_group, name="skill")


def cli_main() -> None:
    """Entry point for the CLI.

    This function is the main entry point called by the console script.
    """
    main()


if __name__ == "__main__":
    cli_main()
