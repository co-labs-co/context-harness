"""Init command for ContextHarness CLI.

Handles the `context-harness init` command for initializing the framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from context_harness.installer import install_framework, InstallResult
from context_harness.interfaces.cli.formatters import (
    console,
    print_header,
    print_success,
    print_warning,
    print_error,
    print_next_steps,
)


@click.command("init")
@click.option(
    "--force", "-f", is_flag=True, help="Overwrite existing files without prompting."
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory for installation (default: current directory).",
)
def init_command(force: bool, target: str) -> None:
    """Initialize ContextHarness in your project.

    Creates the .context-harness/ and .opencode/agent/ directories with all
    necessary framework files.

    Examples:

        context-harness init

        context-harness init --target ./my-project

        context-harness init --force
    """
    print_header("Installer")

    result = install_framework(target, force=force)

    if result == InstallResult.SUCCESS:
        print_success("ContextHarness initialized successfully!")
        print_next_steps(
            [
                "(Optional) Add Context7 MCP: [cyan]context-harness mcp add context7[/cyan]",
                "Start a session: [cyan]@context-harness /ctx my-feature[/cyan]",
                "Work normally - the agent handles execution",
                "Compact when ready: [cyan]/compact[/cyan]",
            ]
        )
    elif result == InstallResult.ALREADY_EXISTS:
        print_warning("ContextHarness files already exist.")
        console.print("Use [cyan]--force[/cyan] to overwrite existing files.")
        raise SystemExit(1)
    elif result == InstallResult.ERROR:
        print_error("Failed to initialize ContextHarness.")
        raise SystemExit(1)
