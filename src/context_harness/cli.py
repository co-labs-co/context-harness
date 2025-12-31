"""CLI entry point for ContextHarness."""

import click
from rich.console import Console
from rich.panel import Panel

from context_harness import __version__
from context_harness.installer import install_framework, InstallResult
from context_harness.mcp_config import (
    add_mcp_server,
    list_mcp_servers,
    get_available_servers,
    MCPResult,
)
from context_harness.skills import (
    list_skills,
    list_local_skills,
    get_skill_info,
    install_skill,
    extract_skill,
    SkillResult,
)
from context_harness.completion import (
    complete_skill_names,
    interactive_skill_picker,
    interactive_local_skill_picker,
    complete_mcp_servers,
    interactive_mcp_picker,
)

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
        console.print(
            "  1. (Optional) Add Context7 MCP: [cyan]context-harness mcp add context7[/cyan]"
        )
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


@main.group()
def mcp():
    """Manage MCP server configurations in opencode.json.

    Add, list, and configure MCP servers for enhanced AI capabilities.
    """
    pass


@mcp.command("add")
@click.argument(
    "server",
    required=False,
    default=None,
    shell_complete=complete_mcp_servers,
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key for the MCP server (optional, enables higher rate limits).",
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory containing opencode.json (default: current directory).",
)
def mcp_add(server: str | None, api_key: str, target: str):
    """Add an MCP server to opencode.json.

    Configures the specified MCP server in your project's opencode.json file.
    If opencode.json doesn't exist, it will be created.

    If no server name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a server.

    Available servers: context7, atlassian

    Examples:

        context-harness mcp add

        context-harness mcp add context7

        context-harness mcp add atlassian

        context-harness mcp add context7 --api-key YOUR_API_KEY

        context-harness mcp add context7 --target ./my-project
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] MCP Configuration",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # If no server provided, show interactive picker
    if server is None:
        server = interactive_mcp_picker(console)
        if server is None:
            # User cancelled or no servers available
            raise SystemExit(0)
        console.print()

    result = add_mcp_server(server, target=target, api_key=api_key)

    if result == MCPResult.SUCCESS:
        console.print()
        console.print("[bold]MCP server configured![/bold]")
        _print_mcp_usage_tips(server)
    elif result == MCPResult.UPDATED:
        console.print()
        console.print("[bold]MCP server added to existing config![/bold]")
        _print_mcp_usage_tips(server)
    elif result == MCPResult.ALREADY_EXISTS:
        raise SystemExit(0)  # Not an error, just informational
    elif result == MCPResult.ERROR:
        console.print("[red]❌ Failed to configure MCP server.[/red]")
        raise SystemExit(1)


@mcp.command("list")
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory containing opencode.json (default: current directory).",
)
def mcp_list(target: str):
    """List configured MCP servers from opencode.json.

    Shows all MCP servers currently configured in the project's opencode.json.

    Examples:

        context-harness mcp list

        context-harness mcp list --target ./my-project
    """
    console.print()
    list_mcp_servers(target=target)
    console.print()


def _print_mcp_usage_tips(server: str) -> None:
    """Print usage tips for the configured MCP server."""
    if server == "context7":
        console.print()
        console.print("[dim]Context7 provides documentation lookup capabilities.[/dim]")
        console.print(
            "[dim]The agent can now fetch up-to-date docs for libraries.[/dim]"
        )
        console.print()
        console.print("[bold]Available tools:[/bold]")
        console.print("  • resolve-library-id - Find library documentation IDs")
        console.print("  • get-library-docs - Fetch documentation for a library")
        console.print()
    elif server == "atlassian":
        console.print()
        console.print(
            "[dim]Atlassian MCP provides Jira, Confluence, and Compass integration.[/dim]"
        )
        console.print(
            "[dim]Authentication uses OAuth 2.1 via browser-based flow.[/dim]"
        )
        console.print()
        console.print("[bold]Capabilities:[/bold]")
        console.print("  • Access Jira issues and projects")
        console.print("  • Query Confluence pages and spaces")
        console.print("  • Interact with Compass components")
        console.print()
        console.print(
            "[dim]On first use, you'll be prompted to authenticate via browser.[/dim]"
        )
        console.print()


# =============================================================================
# Skill Management Commands
# =============================================================================


@main.group()
def skill():
    """Manage ContextHarness skills.

    List, install, and extract skills from the central skills repository.
    Skills extend agent capabilities with specialized knowledge and workflows.
    """
    pass


@skill.command("list")
@click.option(
    "--tags",
    "-t",
    multiple=True,
    help="Filter skills by tag (can be specified multiple times).",
)
def skill_list(tags: tuple):
    """List available skills from the central repository.

    Shows all skills available for installation, with optional tag filtering.

    Examples:

        context-harness skill list

        context-harness skill list --tags react

        context-harness skill list --tags frontend --tags forms
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Skills",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    tags_list = list(tags) if tags else None
    skills = list_skills(tags=tags_list)

    if not skills:
        console.print("[dim]No skills found.[/dim]")
        console.print()
        console.print("[dim]The skills repository may be empty or inaccessible.[/dim]")


@skill.command("list-local")
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing .opencode/skill/ (default: current directory).",
)
def skill_list_local(source: str):
    """List skills installed in your local project.

    Discovers all skills in the .opencode/skill/ directory and displays
    their name, description, and version. Useful for finding skills to extract.

    Examples:

        context-harness skill list-local

        context-harness skill list-local --source ./my-project
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Local Skills",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    list_local_skills(source_path=source)


@skill.command("info")
@click.argument("skill_name")
def skill_info_cmd(skill_name: str):
    """Show detailed information about a skill.

    Displays the skill's description, version, author, and requirements.

    Examples:

        context-harness skill info react-forms

        context-harness skill info django-auth
    """
    console.print()
    skill_data = get_skill_info(skill_name)
    if skill_data is None:
        raise SystemExit(1)
    console.print()


@skill.command("install")
@click.argument(
    "skill_name", required=False, default=None, shell_complete=complete_skill_names
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory for installation (default: current directory).",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing skill if already installed.",
)
def skill_install_cmd(skill_name: str | None, target: str, force: bool):
    """Install a skill from the central repository.

    Downloads and installs the specified skill to .opencode/skill/ in the
    target directory.

    If no skill name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a skill.

    Examples:

        context-harness skill install

        context-harness skill install react-forms

        context-harness skill install django-auth --target ./my-project

        context-harness skill install react-forms --force
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Skill Installer",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # If no skill name provided, show interactive picker
    if skill_name is None:
        skill_name = interactive_skill_picker(console)
        if skill_name is None:
            # User cancelled or no skills available
            raise SystemExit(0)
        console.print()

    result = install_skill(skill_name, target=target, force=force)

    if result == SkillResult.SUCCESS:
        console.print()
        console.print("[bold]Skill installed![/bold]")
        console.print()
        console.print("[dim]The skill is now available in your project.[/dim]")
        console.print("[dim]It will be automatically loaded when relevant.[/dim]")
    elif result == SkillResult.ALREADY_EXISTS:
        raise SystemExit(0)  # Not an error, just informational
    elif result == SkillResult.NOT_FOUND:
        console.print()
        console.print(f"[red]❌ Skill '{skill_name}' not found.[/red]")
        console.print(
            "[dim]Use 'context-harness skill list' to see available skills.[/dim]"
        )
        raise SystemExit(1)
    elif result in (SkillResult.AUTH_ERROR, SkillResult.ERROR):
        console.print()
        console.print("[red]❌ Failed to install skill.[/red]")
        raise SystemExit(1)


@skill.command("extract")
@click.argument("skill_name", required=False, default=None)
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing .opencode/skill/ (default: current directory).",
)
def skill_extract_cmd(skill_name: str | None, source: str):
    """Extract a local skill and create a PR to the central repository.

    Takes a skill from your local .opencode/skill/ directory and creates
    a pull request to add it to the central skills repository for review.

    If no skill name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a skill.

    Examples:

        context-harness skill extract

        context-harness skill extract my-custom-skill

        context-harness skill extract react-auth --source ./my-project
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Skill Extractor",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # If no skill name provided, show interactive picker
    if skill_name is None:
        skill_name = interactive_local_skill_picker(console, source_path=source)
        if skill_name is None:
            # User cancelled or no skills available
            raise SystemExit(0)
        console.print()

    result, pr_url = extract_skill(skill_name, source_path=source)

    if result == SkillResult.SUCCESS:
        console.print()
        console.print("[bold]Pull request created![/bold]")
        console.print()
        console.print(
            "[dim]Once merged, the skill will be available to all users.[/dim]"
        )
    elif result == SkillResult.NOT_FOUND:
        console.print()
        console.print(f"[red]❌ Skill '{skill_name}' not found locally.[/red]")
        console.print(
            f"[dim]Expected location: {source}/.opencode/skill/{skill_name}/[/dim]"
        )
        raise SystemExit(1)
    elif result == SkillResult.AUTH_ERROR:
        console.print()
        console.print("[red]❌ Authentication failed.[/red]")
        console.print("[dim]Make sure you're logged in with 'gh auth login'.[/dim]")
        raise SystemExit(1)
    elif result == SkillResult.ERROR:
        console.print()
        console.print("[red]❌ Failed to extract skill.[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
