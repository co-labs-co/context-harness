"""Rich formatters for CLI output.

Provides consistent formatting for CLI output using Rich library.
All formatting logic is centralized here to keep command modules clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from context_harness import __version__

if TYPE_CHECKING:
    from context_harness.primitives import (
        MCPServer,
        OpenCodeConfig,
        Skill,
    )

# Shared console instance
console = Console()


def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """Print a styled header panel.

    Args:
        title: Main title text
        subtitle: Optional subtitle (defaults to version)
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]ContextHarness[/bold blue] {title}",
            subtitle=subtitle or f"v{__version__}",
        )
    )
    console.print()


def print_success(message: str) -> None:
    """Print a success message with checkmark."""
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_error(message: str) -> None:
    """Print an error message with X."""
    console.print(f"[red]❌ {message}[/red]")


def print_info(message: str) -> None:
    """Print an informational message (dimmed)."""
    console.print(f"[dim]{message}[/dim]")


def print_bold(message: str) -> None:
    """Print bold text."""
    console.print(f"[bold]{message}[/bold]")


def print_next_steps(steps: List[str]) -> None:
    """Print a list of next steps.

    Args:
        steps: List of step descriptions
    """
    console.print()
    console.print("[bold]Next steps:[/bold]")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i}. {step}")
    console.print()


def print_skill_table(skills: List["Skill"]) -> None:
    """Print a table of skills.

    Args:
        skills: List of Skill objects to display
    """
    if not skills:
        console.print("[dim]No skills found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Source", style="dim")
    table.add_column("Version", style="dim")

    for skill in skills:
        version = skill.metadata.version if skill.metadata else "-"
        table.add_row(
            skill.name,
            skill.description[:50] + "..."
            if len(skill.description) > 50
            else skill.description,
            skill.source.value,
            version or "-",
        )

    console.print(table)


def print_mcp_server_table(servers: List["MCPServer"]) -> None:
    """Print a table of MCP servers.

    Args:
        servers: List of MCPServer objects to display
    """
    if not servers:
        console.print("[dim]No MCP servers found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Auth Type", style="dim")

    for server in servers:
        table.add_row(
            server.name,
            server.description[:60] + "..."
            if len(server.description) > 60
            else server.description,
            server.auth_type.value if server.auth_type else "none",
        )

    console.print(table)


def print_configured_servers(config: "OpenCodeConfig") -> None:
    """Print configured MCP servers from opencode.json.

    Args:
        config: OpenCodeConfig with mcpServers
    """
    if not config.mcpServers:
        console.print("[dim]No MCP servers configured.[/dim]")
        console.print("[dim]Use 'context-harness mcp add <server>' to add one.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Command")
    table.add_column("Args", style="dim")

    for name, server_config in config.mcpServers.items():
        args = " ".join(server_config.args) if server_config.args else "-"
        table.add_row(name, server_config.command, args[:40])

    console.print(table)


def print_mcp_usage_tips(server_name: str) -> None:
    """Print usage tips for an MCP server.

    Args:
        server_name: Name of the server
    """
    if server_name == "context7":
        console.print()
        print_info("Context7 provides documentation lookup capabilities.")
        print_info("The agent can now fetch up-to-date docs for libraries.")
        console.print()
        print_bold("Available tools:")
        console.print("  • resolve-library-id - Find library documentation IDs")
        console.print("  • get-library-docs - Fetch documentation for a library")
        console.print()
    elif server_name == "atlassian":
        console.print()
        print_info("Atlassian MCP provides Jira, Confluence, and Compass integration.")
        print_info("Authentication uses OAuth 2.1 via browser-based flow.")
        console.print()
        print_bold("Capabilities:")
        console.print("  • Access Jira issues and projects")
        console.print("  • Query Confluence pages and spaces")
        console.print("  • Interact with Compass components")
        console.print()
        print_info("On first use, you'll be prompted to authenticate via browser.")
        console.print()


def print_oauth_setup_instructions(
    provider_name: str,
    display_name: str,
    setup_url: Optional[str],
    scopes: Optional[List[str]] = None,
) -> None:
    """Print OAuth setup instructions.

    Args:
        provider_name: Provider identifier
        display_name: Human-readable provider name
        setup_url: URL for creating OAuth apps
        scopes: Required scopes
    """
    if not setup_url:
        return

    console.print()
    print_bold(f"To get a {display_name} OAuth client ID:")
    console.print(f"  1. Go to {setup_url}")
    console.print("  2. Create a new OAuth 2.0 app")
    console.print("  3. Add callback URL: http://localhost:PORT/callback")
    console.print("     (any port works, the CLI uses a random available port)")

    if scopes:
        console.print("  4. Enable the required scopes:")
        for scope in scopes[:5]:
            console.print(f"     - {scope}")
        if len(scopes) > 5:
            console.print(f"     ... and {len(scopes) - 5} more")
    console.print()
