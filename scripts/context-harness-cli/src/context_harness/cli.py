"""CLI entry point for ContextHarness."""

import click
from rich.console import Console
from rich.panel import Panel

from context_harness import __version__
from context_harness.installer import install_framework, InstallResult

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="context-harness")
def main():
    """ContextHarness CLI - Initialize agent frameworks in your project.

    A context-aware agent framework for OpenCode.ai that maintains session
    continuity through user-driven compaction cycles.
    """
    pass


@main.command()
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
def init(force: bool, target: str):
    """Initialize ContextHarness in your project.

    Creates the .context-harness/ and .opencode/agent/ directories with all
    necessary framework files.

    Examples:

        context-harness init

        context-harness init --target ./my-project

        context-harness init --force
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Installer",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    result = install_framework(target, force=force)

    if result == InstallResult.SUCCESS:
        console.print("[green]✅ ContextHarness initialized successfully![/green]")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Configure Context7 MCP in opencode.json (optional)")
        console.print(
            "  2. Start a session: [cyan]@context-harness /ctx my-feature[/cyan]"
        )
        console.print("  3. Work normally - the agent handles execution")
        console.print("  4. Compact when ready: [cyan]/compact[/cyan]")
        console.print()
    elif result == InstallResult.ALREADY_EXISTS:
        console.print("[yellow]⚠️  ContextHarness files already exist.[/yellow]")
        console.print("Use [cyan]--force[/cyan] to overwrite existing files.")
        raise SystemExit(1)
    elif result == InstallResult.ERROR:
        console.print("[red]❌ Failed to initialize ContextHarness.[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
