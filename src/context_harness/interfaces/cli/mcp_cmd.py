"""MCP commands for ContextHarness CLI.

Handles the `ch mcp` command group for MCP server management.
"""

from __future__ import annotations

from typing import Optional

import click

from context_harness.mcp_config import (
    add_mcp_server,
    list_mcp_servers,
    get_available_servers,
    get_mcp_server_info,
    MCPResult,
)
from context_harness.oauth import (
    get_oauth_flow,
    OAUTH_PROVIDERS,
    OAuthError,
    OAuthTimeoutError,
    OAuthCancelledError,
    AuthStatus,
)
from context_harness.completion import (
    complete_mcp_servers,
    interactive_mcp_picker,
)
from context_harness.interfaces.cli.formatters import (
    console,
    print_header,
    print_warning,
    print_error,
    print_info,
    print_bold,
    print_mcp_usage_tips,
    print_oauth_setup_instructions,
)


@click.group("mcp")
def mcp_group() -> None:
    """Manage MCP server configurations in opencode.json.

    Add, list, and configure MCP servers for enhanced AI capabilities.
    """
    pass


@mcp_group.command("add")
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
def mcp_add(server: Optional[str], api_key: Optional[str], target: str) -> None:
    """Add an MCP server to opencode.json.

    Configures the specified MCP server in your project's opencode.json file.
    If opencode.json doesn't exist, it will be created.

    If no server name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a server.

    Available servers: context7, atlassian

    Examples:

        ch mcp add

        ch mcp add context7

        ch mcp add atlassian

        ch mcp add context7 --api-key YOUR_API_KEY

        ch mcp add context7 --target ./my-project
    """
    print_header("MCP Configuration")

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
        print_bold("MCP server configured!")
        print_mcp_usage_tips(server)
    elif result == MCPResult.UPDATED:
        console.print()
        print_bold("MCP server added to existing config!")
        print_mcp_usage_tips(server)
    elif result == MCPResult.ALREADY_EXISTS:
        raise SystemExit(0)  # Not an error, just informational
    elif result == MCPResult.ERROR:
        print_error("Failed to configure MCP server.")
        raise SystemExit(1)


@mcp_group.command("list")
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory containing opencode.json (default: current directory).",
)
def mcp_list(target: str) -> None:
    """List configured MCP servers from opencode.json.

    Shows all MCP servers currently configured in the project's opencode.json.

    Examples:

        ch mcp list

        ch mcp list --target ./my-project
    """
    console.print()
    list_mcp_servers(target=target)
    console.print()


@mcp_group.command("auth")
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
def mcp_auth(server: str, client_id: Optional[str], status: bool, logout: bool) -> None:
    """Authenticate with an MCP server using OAuth.

    Starts a browser-based OAuth flow to authenticate with servers that
    require OAuth (like Atlassian). Tokens are stored securely for future use.

    The flow works with any OAuth-enabled MCP server in the registry.
    Client IDs can be provided via --client-id or environment variable
    (e.g., ATLASSIAN_CLIENT_ID for Atlassian).

    Examples:

        ch mcp auth atlassian --client-id YOUR_CLIENT_ID

        export ATLASSIAN_CLIENT_ID=your_client_id
        ch mcp auth atlassian

        ch mcp auth atlassian --status

        ch mcp auth atlassian --logout
    """
    print_header("MCP Authentication")

    # Validate server supports OAuth
    server_info = get_mcp_server_info(server)
    if server_info is None:
        print_error(f"Unknown MCP server '{server}'")
        print_info(f"Available servers: {', '.join(get_available_servers())}")
        raise SystemExit(1)

    if server_info.auth_type != "oauth":
        print_warning(f"Server '{server}' does not use OAuth authentication.")
        if server_info.auth_type == "api-key":
            print_info(f"Use 'ch mcp add {server} --api-key YOUR_KEY' instead.")
        raise SystemExit(1)

    # Check if this is a registered OAuth provider
    if server not in OAUTH_PROVIDERS:
        print_warning(f"OAuth not yet configured for '{server}'.")
        print_info("The server requires OAuth but no provider configuration exists.")
        raise SystemExit(1)

    # Handle OAuth authentication
    _handle_oauth_auth(server, client_id, status, logout)


def _handle_oauth_auth(
    server: str, client_id: Optional[str], status: bool, logout: bool
) -> None:
    """Handle OAuth authentication for an MCP server."""
    try:
        oauth = get_oauth_flow(server, client_id)
    except OAuthError as e:
        print_error(str(e))

        # Show setup instructions if available
        if server in OAUTH_PROVIDERS:
            provider = OAUTH_PROVIDERS[server]
            print_oauth_setup_instructions(
                server,
                provider.display_name or server.title(),
                provider.setup_url,
                provider.scopes,
            )
        raise SystemExit(1)

    display_name = OAUTH_PROVIDERS[server].display_name or server.title()

    # Handle --status flag
    if status:
        auth_status = oauth.get_auth_status()
        if auth_status == AuthStatus.AUTHENTICATED:
            console.print(f"[green]✓ Authenticated with {display_name}[/green]")
            tokens = oauth.get_tokens()
            if tokens and tokens.scope:
                print_info(f"Scopes: {tokens.scope}")
        elif auth_status == AuthStatus.TOKEN_EXPIRED:
            print_warning("Token expired")
            print_info(f"Run 'ch mcp auth {server}' to refresh.")
        else:
            print_info(f"Not authenticated with {display_name}")
            print_info(f"Run 'ch mcp auth {server}' to authenticate.")
        console.print()
        return

    # Handle --logout flag
    if logout:
        if oauth.logout():
            console.print(f"[green]✓ Logged out from {display_name}[/green]")
            print_info("Stored tokens have been removed.")
        else:
            print_info(f"Not currently logged in to {display_name}.")
        console.print()
        return

    # Run OAuth flow
    try:
        oauth.authenticate()

        console.print()
        print_bold("Next steps:")
        console.print(f"  • Run 'ch mcp add {server}' to configure the MCP")
        console.print("  • The agent will use your stored credentials automatically")
        console.print()

    except OAuthTimeoutError:
        console.print()
        print_warning("Authentication timed out.")
        print_info("The browser flow was not completed in time. Please try again.")
        console.print()
        raise SystemExit(1)

    except OAuthCancelledError:
        console.print()
        print_warning("Authentication cancelled.")
        print_info("You denied access in the browser. No tokens were stored.")
        console.print()
        raise SystemExit(1)

    except OAuthError as e:
        console.print()
        print_error(f"Authentication failed: {e}")
        console.print()
        raise SystemExit(1)
