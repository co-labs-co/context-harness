"""CLI entry point for ContextHarness."""

from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from context_harness import __version__
from context_harness.installer import install_framework, InstallResult, TargetType
from context_harness.mcp_config import (
    add_mcp_server,
    list_mcp_servers,
    get_available_servers,
    get_mcp_server_info,
    MCPResult,
)
from context_harness.oauth import (
    get_atlassian_oauth_flow,
    get_oauth_flow,
    MCPOAuthFlow,
    OAuthConfig,
    OAUTH_PROVIDERS,
    OAuthError,
    OAuthTimeoutError,
    OAuthCancelledError,
    AuthStatus,
)
from context_harness.skills import (
    list_skills,
    list_local_skills,
    get_skill_info,
    install_skill,
    extract_skill,
    SkillResult,
)
from context_harness.primitives import (
    Failure,
    SKILLS_REPO_ENV_VAR,
    SkillsRegistryConfig,
    UserConfig,
)
from context_harness.services.skills_registry import get_skills_repo_info
from context_harness.services.user_config_service import UserConfigService
from context_harness.services.config_service import ConfigService
from context_harness.completion import (
    complete_skill_names,
    interactive_skill_picker,
    interactive_local_skill_picker,
    complete_mcp_servers,
    interactive_mcp_picker,
)
from context_harness.interfaces.cli.worktree_cmd import worktree_group

# Check if web dependencies are available
try:
    import uvicorn
    from context_harness.interfaces.web.app import create_app

    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

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
@click.option(
    "--tool",
    type=click.Choice(["opencode", "claude-code", "both"]),
    default="both",
    help="Which tool(s) to install for: opencode, claude-code, or both (default: both).",
)
def init(force: bool, target: str, tool: str):
    """Initialize ContextHarness in your project.

    Creates configuration directories for AI coding assistants:
    - .context-harness/ - Session data and project context (shared)
    - .opencode/ - OpenCode configuration (agents, commands, skills)
    - .claude/ - Claude Code configuration (agents, commands, skills)

    By default, installs support for both OpenCode and Claude Code.
    Use --tool to install for a specific tool only.

    Examples:

        context-harness init

        context-harness init --target ./my-project

        context-harness init --force

        context-harness init --tool opencode

        context-harness init --tool claude-code

        context-harness init --force --tool both
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Installer",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # Show what will be installed
    if tool == "both":
        console.print("[dim]Installing support for: OpenCode + Claude Code[/dim]")
    elif tool == "opencode":
        console.print("[dim]Installing support for: OpenCode only[/dim]")
    else:
        console.print("[dim]Installing support for: Claude Code only[/dim]")
    console.print()

    result = install_framework(target, force=force, tool_target=tool)  # type: ignore[arg-type]

    if result == InstallResult.SUCCESS:
        console.print("[green]✅ ContextHarness initialized successfully![/green]")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        if tool in ("opencode", "both"):
            console.print(
                "  1. (Optional) Add Context7 MCP: [cyan]context-harness mcp add context7[/cyan]"
            )
            console.print(
                "  2. Start a session: [cyan]@context-harness /ctx my-feature[/cyan]"
            )
        if tool in ("claude-code", "both"):
            if tool == "claude-code":
                console.print("  1. MCP servers configured in .mcp.json")
                console.print("  2. Start a session: [cyan]/ctx my-feature[/cyan]")
            else:
                console.print(
                    "  • Claude Code: MCP configured in .mcp.json, use [cyan]/ctx my-feature[/cyan]"
                )
        console.print("  3. Work normally - the agent handles execution")
        console.print("  4. Compact when ready: [cyan]/compact[/cyan]")
        console.print()
    elif result == InstallResult.ALREADY_EXISTS:
        console.print("[yellow]⚠️  ContextHarness files already exist.[/yellow]")
        console.print("Use [cyan]--force[/cyan] to overwrite existing files.")
        console.print(
            "[dim]Use --force to upgrade to dual-tool support (OpenCode + Claude Code).[/dim]"
        )
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


@mcp.command("auth")
@click.argument("server", required=True)
@click.option(
    "--client-id",
    "-c",
    default=None,
    help="OAuth client ID (or set <SERVER>_CLIENT_ID env var).",
)
@click.option(
    "--status",
    "-s",
    is_flag=True,
    help="Check authentication status without starting a new flow.",
)
@click.option(
    "--logout",
    is_flag=True,
    help="Remove stored authentication tokens.",
)
def mcp_auth(server: str, client_id: str, status: bool, logout: bool):
    """Authenticate with an MCP server using OAuth.

    Starts a browser-based OAuth flow to authenticate with servers that
    require OAuth (like Atlassian). Tokens are stored securely for future use.

    The flow works with any OAuth-enabled MCP server in the registry.
    Client IDs can be provided via --client-id or environment variable
    (e.g., ATLASSIAN_CLIENT_ID for Atlassian).

    Examples:

        context-harness mcp auth atlassian --client-id YOUR_CLIENT_ID

        export ATLASSIAN_CLIENT_ID=your_client_id
        context-harness mcp auth atlassian

        context-harness mcp auth atlassian --status

        context-harness mcp auth atlassian --logout
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] MCP Authentication",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # Validate server supports OAuth
    server_info = get_mcp_server_info(server)
    if server_info is None:
        console.print(f"[red]Error: Unknown MCP server '{server}'[/red]")
        console.print(
            f"[dim]Available servers: {', '.join(get_available_servers())}[/dim]"
        )
        raise SystemExit(1)

    if server_info.auth_type != "oauth":
        console.print(
            f"[yellow]Server '{server}' does not use OAuth authentication.[/yellow]"
        )
        if server_info.auth_type == "api-key":
            console.print(
                f"[dim]Use 'context-harness mcp add {server} --api-key YOUR_KEY' instead.[/dim]"
            )
        raise SystemExit(1)

    # Check if this is a registered OAuth provider
    if server not in OAUTH_PROVIDERS:
        console.print(f"[yellow]OAuth not yet configured for '{server}'.[/yellow]")
        console.print(
            "[dim]The server requires OAuth but no provider configuration exists.[/dim]"
        )
        raise SystemExit(1)

    # Use the generic OAuth flow
    _handle_oauth_auth(server, client_id, status, logout)


def _handle_oauth_auth(
    server: str, client_id: Optional[str], status: bool, logout: bool
) -> None:
    """Handle generic OAuth authentication for any MCP server."""
    try:
        oauth = get_oauth_flow(server, client_id)
    except OAuthError as e:
        console.print(f"[red]Error: {e}[/red]")

        # Show setup instructions if available
        if server in OAUTH_PROVIDERS:
            provider = OAUTH_PROVIDERS[server]
            if provider.setup_url:
                console.print()
                console.print(
                    f"[bold]To get a {provider.display_name or server.title()} OAuth client ID:[/bold]"
                )
                console.print(f"  1. Go to {provider.setup_url}")
                console.print("  2. Create a new OAuth 2.0 app")
                console.print("  3. Add callback URL: http://localhost:PORT/callback")
                console.print(
                    "     (any port works, the CLI uses a random available port)"
                )
                if provider.scopes:
                    console.print("  4. Enable the required scopes:")
                    for scope in provider.scopes[:5]:  # Show first 5 scopes
                        console.print(f"     - {scope}")
                    if len(provider.scopes) > 5:
                        console.print(f"     ... and {len(provider.scopes) - 5} more")
                console.print()
        raise SystemExit(1)

    display_name = OAUTH_PROVIDERS[server].display_name or server.title()

    # Handle --status flag
    if status:
        auth_status = oauth.get_auth_status()
        if auth_status == AuthStatus.AUTHENTICATED:
            console.print(f"[green]✓ Authenticated with {display_name}[/green]")
            tokens = oauth.get_tokens()
            if tokens and tokens.scope:
                console.print(f"[dim]Scopes: {tokens.scope}[/dim]")
        elif auth_status == AuthStatus.TOKEN_EXPIRED:
            console.print("[yellow]⚠ Token expired[/yellow]")
            console.print(
                f"[dim]Run 'context-harness mcp auth {server}' to refresh.[/dim]"
            )
        else:
            console.print(f"[dim]Not authenticated with {display_name}[/dim]")
            console.print(
                f"[dim]Run 'context-harness mcp auth {server}' to authenticate.[/dim]"
            )
        console.print()
        return

    # Handle --logout flag
    if logout:
        if oauth.logout():
            console.print(f"[green]✓ Logged out from {display_name}[/green]")
            console.print("[dim]Stored tokens have been removed.[/dim]")
        else:
            console.print(f"[dim]Not currently logged in to {display_name}.[/dim]")
        console.print()
        return

    # Run OAuth flow
    try:
        tokens = oauth.authenticate()

        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print(
            f"  • Run 'context-harness mcp add {server}' to configure the MCP"
        )
        console.print("  • The agent will use your stored credentials automatically")
        console.print()

    except OAuthTimeoutError:
        console.print()
        console.print("[yellow]⚠ Authentication timed out.[/yellow]")
        console.print(
            "[dim]The browser flow was not completed in time. Please try again.[/dim]"
        )
        console.print()
        raise SystemExit(1)

    except OAuthCancelledError:
        console.print()
        console.print("[yellow]⚠ Authentication cancelled.[/yellow]")
        console.print(
            "[dim]You denied access in the browser. No tokens were stored.[/dim]"
        )
        console.print()
        raise SystemExit(1)

    except OAuthError as e:
        console.print()
        console.print(f"[red]❌ Authentication failed: {e}[/red]")
        console.print()
        raise SystemExit(1)


def _handle_atlassian_auth(
    client_id: Optional[str], status: bool, logout: bool
) -> None:
    """Handle Atlassian OAuth authentication.

    DEPRECATED: Use _handle_oauth_auth(server="atlassian", ...) instead.
    Kept for backward compatibility.
    """
    _handle_oauth_auth("atlassian", client_id, status, logout)


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


# =============================================================================
# Config Management Commands
# =============================================================================


@main.group()
def config():
    """Manage ContextHarness configuration.

    View and modify configuration settings at user or project level.
    Configuration is resolved with the following precedence:

    \b
    1. Environment variable (highest priority)
    2. Project config (opencode.json)
    3. User config (~/.context-harness/config.json)
    4. Default values (lowest priority)
    """
    pass


@config.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a configuration value.

    Shows the current value and where it comes from.

    \b
    Supported keys:
      skills-repo    The skills repository (owner/repo format)

    Examples:

        context-harness config get skills-repo
    """
    if key == "skills-repo":
        result = get_skills_repo_info()
        if isinstance(result, Failure):
            console.print(f"[red]Error: {result.error}[/red]")
            raise SystemExit(1)

        info = result.value
        console.print()
        console.print(f"[bold cyan]skills-repo[/bold cyan]: {info['repo']}")
        console.print(f"[dim]Source: {info['source']}[/dim]")
        console.print()

        # Show all configured values
        console.print("[dim]Configuration layers:[/dim]")
        env_val = info["env_value"] or "(not set)"
        proj_val = info["project_value"] or "(not set)"
        user_val = info["user_value"] or "(not set)"
        default_val = info["default_value"]

        source = info["source"]
        console.print(
            f"  1. Environment ({SKILLS_REPO_ENV_VAR}): {env_val}"
            + (" [green]← active[/green]" if source == "environment" else "")
        )
        console.print(
            f"  2. Project (opencode.json): {proj_val}"
            + (" [green]← active[/green]" if source == "project" else "")
        )
        console.print(
            f"  3. User (~/.context-harness/config.json): {user_val}"
            + (" [green]← active[/green]" if source == "user" else "")
        )
        console.print(
            f"  4. Default: {default_val}"
            + (" [green]← active[/green]" if source == "default" else "")
        )
        console.print()
    else:
        console.print(f"[red]Error: Unknown configuration key: {key}[/red]")
        console.print()
        console.print("[dim]Supported keys: skills-repo[/dim]")
        raise SystemExit(1)


def _parse_repo_value(value: str) -> Optional[str]:
    """Parse a repository value, accepting owner/repo or full GitHub URL.

    Args:
        value: Repository in format "owner/repo" or "https://github.com/owner/repo"

    Returns:
        Normalized "owner/repo" format, or None if invalid
    """
    import re

    # Strip whitespace and trailing slashes
    value = value.strip().rstrip("/")

    # Check if it's a full GitHub URL
    github_url_pattern = r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?$"
    match = re.match(github_url_pattern, value)
    if match:
        owner, repo = match.groups()
        return f"{owner}/{repo}"

    # Check if it's already in owner/repo format
    if "/" in value and value.count("/") == 1:
        owner, repo = value.split("/")
        # Basic validation: both parts should be non-empty and contain valid chars
        if (
            owner
            and repo
            and re.match(r"^[\w.-]+$", owner)
            and re.match(r"^[\w.-]+$", repo)
        ):
            return value

    return None


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--user",
    "scope",
    flag_value="user",
    help="Set in user config (~/.context-harness/config.json)",
)
@click.option(
    "--project",
    "scope",
    flag_value="project",
    default=True,
    help="Set in project config (opencode.json) [default]",
)
def config_set(key: str, value: str, scope: str):
    """Set a configuration value.

    By default, sets values in project config (opencode.json).
    Use --user to set in user config (~/.context-harness/config.json).

    \b
    Supported keys:
      skills-repo    The skills repository (owner/repo or full GitHub URL)

    Examples:

        context-harness config set skills-repo my-org/my-skills

        context-harness config set skills-repo https://github.com/my-org/my-skills

        context-harness config set skills-repo my-org/my-skills --user

        context-harness config set skills-repo my-org/my-skills --project
    """
    if key == "skills-repo":
        # Parse and normalize repo value (accepts owner/repo or full GitHub URL)
        repo = _parse_repo_value(value)
        if repo is None:
            console.print(f"[red]Error: Invalid repository format: {value}[/red]")
            console.print()
            console.print(
                "[dim]Expected format: owner/repo or https://github.com/owner/repo[/dim]"
            )
            raise SystemExit(1)

        if scope == "user":
            _set_user_skills_repo(repo)
        else:
            _set_project_skills_repo(repo)
    else:
        console.print(f"[red]Error: Unknown configuration key: {key}[/red]")
        console.print()
        console.print("[dim]Supported keys: skills-repo[/dim]")
        raise SystemExit(1)


def _set_user_skills_repo(repo: str) -> None:
    """Set skills repo in user config."""
    service = UserConfigService()

    # Load existing config
    result = service.load()
    if isinstance(result, Failure):
        console.print(f"[red]Error: {result.error}[/red]")
        raise SystemExit(1)

    # Create new config with updated skills registry
    new_config = UserConfig(
        skills_registry=SkillsRegistryConfig(default=repo),
    )

    # Save
    save_result = service.save(new_config)
    if isinstance(save_result, Failure):
        console.print(f"[red]Error: {save_result.error}[/red]")
        raise SystemExit(1)

    console.print()
    console.print(f"[green]✓ Set skills-repo to '{repo}' in user config[/green]")
    console.print(f"[dim]Location: {service.config_path}[/dim]")
    console.print()


def _set_project_skills_repo(repo: str) -> None:
    """Set skills repo in project config."""
    service = ConfigService()

    # Load or create config
    result = service.load_or_create()
    if isinstance(result, Failure):
        console.print(f"[red]Error: {result.error}[/red]")
        raise SystemExit(1)

    config = result.value

    # Import here to avoid circular import
    from context_harness.primitives.config import OpenCodeConfig

    # Create new config with updated skills registry
    new_config = OpenCodeConfig(
        schema_version=config.schema_version,
        mcp=config.mcp,
        agents=config.agents,
        commands=config.commands,
        skills=config.skills,
        skills_registry=SkillsRegistryConfig(default=repo),
        project_context=config.project_context,
        raw_data=config.raw_data,
    )

    # Save
    save_result = service.save(new_config)
    if isinstance(save_result, Failure):
        console.print(f"[red]Error: {save_result.error}[/red]")
        raise SystemExit(1)

    console.print()
    console.print(f"[green]✓ Set skills-repo to '{repo}' in project config[/green]")
    console.print(f"[dim]Location: {service.project_config.opencode_json_path}[/dim]")
    console.print()


@config.command("list")
def config_list():
    """List all configuration values.

    Shows current values and their sources.

    Example:

        context-harness config list
    """
    from pathlib import Path

    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Configuration",
            subtitle=f"v{__version__}",
        )
    )
    console.print()

    # Skills repo
    result = get_skills_repo_info()
    if isinstance(result, Failure):
        console.print(f"[red]Error: {result.error}[/red]")
        raise SystemExit(1)

    info = result.value
    console.print("[bold]Skills Registry[/bold]")
    console.print(f"  skills-repo: [cyan]{info['repo']}[/cyan]")
    console.print(f"  [dim]Source: {info['source']}[/dim]")
    console.print()

    # Show paths
    console.print("[bold]Configuration Paths[/bold]")
    console.print(f"  User config: [dim]{UserConfig.config_path()}[/dim]")
    console.print(f"  Project config: [dim]{Path.cwd() / 'opencode.json'}[/dim]")
    console.print()

    # Show environment variable
    console.print("[bold]Environment Variables[/bold]")
    env_val = info["env_value"]
    if env_val:
        console.print(f"  {SKILLS_REPO_ENV_VAR}={env_val}")
    else:
        console.print(f"  [dim]{SKILLS_REPO_ENV_VAR} (not set)[/dim]")
    console.print()


@config.command("unset")
@click.argument("key")
@click.option(
    "--user",
    "scope",
    flag_value="user",
    help="Unset in user config",
)
@click.option(
    "--project",
    "scope",
    flag_value="project",
    default=True,
    help="Unset in project config [default]",
)
def config_unset(key: str, scope: str):
    """Remove a configuration value.

    Removes the configuration value, falling back to the next layer.

    \b
    Supported keys:
      skills-repo    The skills repository

    Examples:

        context-harness config unset skills-repo

        context-harness config unset skills-repo --user
    """
    if key == "skills-repo":
        if scope == "user":
            _unset_user_skills_repo()
        else:
            _unset_project_skills_repo()
    else:
        console.print(f"[red]Error: Unknown configuration key: {key}[/red]")
        console.print()
        console.print("[dim]Supported keys: skills-repo[/dim]")
        raise SystemExit(1)


def _unset_user_skills_repo() -> None:
    """Remove skills repo from user config."""
    service = UserConfigService()

    if not service.exists():
        console.print("[dim]User config does not exist, nothing to unset.[/dim]")
        return

    result = service.load()
    if isinstance(result, Failure):
        console.print(f"[red]Error: {result.error}[/red]")
        raise SystemExit(1)

    # Create new config without skills registry
    new_config = UserConfig(skills_registry=None)

    save_result = service.save(new_config)
    if isinstance(save_result, Failure):
        console.print(f"[red]Error: {save_result.error}[/red]")
        raise SystemExit(1)

    console.print()
    console.print("[green]✓ Removed skills-repo from user config[/green]")
    console.print()


def _unset_project_skills_repo() -> None:
    """Remove skills repo from project config."""
    service = ConfigService()

    if not service.exists():
        console.print("[dim]Project config does not exist, nothing to unset.[/dim]")
        return

    result = service.load()
    if isinstance(result, Failure):
        console.print(f"[red]Error: {result.error}[/red]")
        raise SystemExit(1)

    config = result.value

    from context_harness.primitives.config import OpenCodeConfig

    # Create new config without skills registry
    new_config = OpenCodeConfig(
        schema_version=config.schema_version,
        mcp=config.mcp,
        agents=config.agents,
        commands=config.commands,
        skills=config.skills,
        skills_registry=None,
        project_context=config.project_context,
        raw_data=config.raw_data,
    )

    save_result = service.save(new_config)
    if isinstance(save_result, Failure):
        console.print(f"[red]Error: {save_result.error}[/red]")
        raise SystemExit(1)

    console.print()
    console.print("[green]✓ Removed skills-repo from project config[/green]")
    console.print()


# =============================================================================
# Web UI Command
# =============================================================================


@main.command()
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    help="Host to bind the server to (default: 127.0.0.1).",
)
@click.option(
    "--port",
    "-p",
    default=8000,
    type=int,
    help="Port to bind the server to (default: 8000).",
)
@click.option(
    "--reload",
    "-r",
    is_flag=True,
    help="Enable auto-reload for development.",
)
@click.option(
    "--working-dir",
    "-w",
    default=".",
    type=click.Path(exists=True),
    help="Working directory for ContextHarness operations (default: current directory).",
)
def serve(host: str, port: int, reload: bool, working_dir: str):
    """Start the ContextHarness web UI server.

    Launches a local web server that provides a browser-based interface
    for managing sessions, chatting with agents, and voice input.

    Requires the [web] optional dependencies to be installed:

        pip install context-harness[web]

    Or with uv:

        uv pip install context-harness[web]

    Examples:

        context-harness serve

        context-harness serve --port 3000

        context-harness serve --host 0.0.0.0 --port 8080

        context-harness serve --reload  # For development

        context-harness serve --working-dir ./my-project
    """
    if not WEB_AVAILABLE:
        console.print()
        console.print("[red]❌ Web dependencies not installed.[/red]")
        console.print()
        console.print("Install them with:")
        console.print("  [cyan]pip install context-harness[web][/cyan]")
        console.print("Or with uv:")
        console.print("  [cyan]uv pip install context-harness[web][/cyan]")
        console.print()
        raise SystemExit(1)

    from pathlib import Path

    console.print()
    console.print(
        Panel.fit(
            "[bold blue]ContextHarness[/bold blue] Web UI",
            subtitle=f"v{__version__}",
        )
    )
    console.print()
    console.print(f"[bold]Starting server...[/bold]")
    console.print(f"  • Host: [cyan]{host}[/cyan]")
    console.print(f"  • Port: [cyan]{port}[/cyan]")
    console.print(f"  • Working directory: [cyan]{Path(working_dir).resolve()}[/cyan]")
    console.print(
        f"  • Auto-reload: [cyan]{'enabled' if reload else 'disabled'}[/cyan]"
    )
    console.print()
    console.print(
        f"[green]➜[/green] Open [cyan]http://{host}:{port}[/cyan] in your browser"
    )
    console.print()
    console.print("[dim]Press Ctrl+C to stop the server[/dim]")
    console.print()

    # Create and run the app
    app = create_app(working_dir=Path(working_dir).resolve())

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# =============================================================================
# Register external command groups
# =============================================================================

# NOTE: The `worktree` command group is also registered in
# `context_harness.interfaces.cli.main`. Both registrations are intentional to
# ensure all CLI entry points expose the same commands. This module
# (context_harness.cli) is the primary entry point defined in pyproject.toml.
# The interfaces/cli/main.py entry point is maintained for backward compatibility
# and may be deprecated in a future release.
main.add_command(worktree_group, name="worktree")


if __name__ == "__main__":
    main()
