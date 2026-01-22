"""MCP configuration management for ContextHarness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from context_harness.primitives.tool_detector import (
    ToolDetector,
    ToolTarget,
    ToolType,
)

console = Console()


class MCPResult(Enum):
    """Result of an MCP configuration operation."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    UPDATED = "updated"
    ERROR = "error"


@dataclass
class MCPServerInfo:
    """Information about an MCP server."""

    name: str
    url: str
    description: str
    server_type: str  # "remote" or "local"
    auth_type: Optional[str] = None  # "oauth", "api-key", None


# MCP Server Registry with rich metadata
MCP_REGISTRY: List[MCPServerInfo] = [
    MCPServerInfo(
        name="context7",
        url="https://mcp.context7.com/mcp",
        description="Documentation lookup for libraries and frameworks",
        server_type="remote",
        auth_type="api-key",
    ),
    MCPServerInfo(
        name="atlassian",
        url="https://mcp.atlassian.com/v1/mcp",
        description="Jira, Confluence, and Compass integration via OAuth 2.1",
        server_type="remote",
        auth_type="oauth",
    ),
    MCPServerInfo(
        name="exa",
        url="https://mcp.exa.ai/mcp",
        description="AI-powered web search and research assistant",
        server_type="remote",
        auth_type=None,
    ),
]

# Known MCP server configurations (derived from registry for backward compatibility)
MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    server.name: {
        "type": server.server_type,
        "url": server.url,
    }
    for server in MCP_REGISTRY
}


def get_opencode_config_path(target: str = ".") -> Path:
    """Get the path to the opencode.json config file.

    Args:
        target: Target directory path (default: current directory)

    Returns:
        Path to opencode.json in the target directory
    """
    return Path(target).resolve() / "opencode.json"


def get_mcp_json_config_path(target: str = ".") -> Path:
    """Get the path to the .mcp.json config file (Claude Code).

    Args:
        target: Target directory path (default: current directory)

    Returns:
        Path to .mcp.json in the target directory
    """
    return Path(target).resolve() / ".mcp.json"


def get_mcp_config_paths(
    target: str = ".", tool_target: Optional[ToolTarget] = None
) -> List[Path]:
    """Get MCP config file paths based on tool target.

    Args:
        target: Target directory path (default: current directory)
        tool_target: Which tool(s) to get config paths for:
            - "opencode": Only opencode.json
            - "claude-code": Only .mcp.json
            - "both": Both config files
            - None: Auto-detect based on installed tools

    Returns:
        List of MCP config file paths
    """
    target_path = Path(target).resolve()
    detector = ToolDetector(target_path)
    return detector.get_mcp_config_paths(tool_target)


def load_opencode_config(config_path: Path) -> Dict[str, Any]:
    """Load existing opencode.json or return default structure.

    Args:
        config_path: Path to opencode.json

    Returns:
        Parsed config dict or default structure
    """
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            console.print(
                f"[yellow]Warning: {config_path} contains invalid JSON, "
                "will create backup[/yellow]"
            )
            return {}
    return {}


def load_mcp_json_config(config_path: Path) -> Dict[str, Any]:
    """Load existing .mcp.json or return default structure.

    The .mcp.json format for Claude Code uses a different structure:
    - "mcpServers" key (camelCase) instead of "mcp"
    - Server configs are nested directly under server names

    Args:
        config_path: Path to .mcp.json

    Returns:
        Parsed config dict or default structure
    """
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            console.print(
                f"[yellow]Warning: {config_path} contains invalid JSON, "
                "will create backup[/yellow]"
            )
            return {}
    return {}


def save_opencode_config(config_path: Path, config: Dict[str, Any]) -> None:
    """Save config to opencode.json with proper formatting.

    Args:
        config_path: Path to opencode.json
        config: Config dict to save
    """
    # Ensure $schema is first
    if "$schema" not in config:
        config = {"$schema": "https://opencode.ai/config.json", **config}

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")  # Trailing newline


def save_mcp_json_config(config_path: Path, config: Dict[str, Any]) -> None:
    """Save config to .mcp.json with proper formatting.

    Args:
        config_path: Path to .mcp.json
        config: Config dict to save
    """
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")  # Trailing newline


def add_mcp_server(
    server_name: str,
    target: str = ".",
    api_key: Optional[str] = None,
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> MCPResult:
    """Add an MCP server configuration to opencode.json and/or .mcp.json.

    Args:
        server_name: Name of the MCP server (e.g., "context7")
        target: Target directory path
        api_key: Optional API key for the server
        quiet: If True, suppress output messages
        tool_target: Which tool(s) to configure:
            - "opencode": Only opencode.json
            - "claude-code": Only .mcp.json
            - "both": Both config files
            - None: Auto-detect based on installed tools

    Returns:
        MCPResult indicating success or failure reason
    """
    if server_name not in MCP_SERVERS:
        if not quiet:
            console.print(f"[red]Error: Unknown MCP server '{server_name}'[/red]")
            console.print(
                f"[dim]Available servers: {', '.join(MCP_SERVERS.keys())}[/dim]"
            )
        return MCPResult.ERROR

    target_path = Path(target).resolve()
    detector = ToolDetector(target_path)

    # Determine which config files to update
    if tool_target == "opencode":
        config_paths = [("opencode", get_opencode_config_path(target))]
    elif tool_target == "claude-code":
        config_paths = [("claude-code", get_mcp_json_config_path(target))]
    elif tool_target == "both":
        config_paths = [
            ("opencode", get_opencode_config_path(target)),
            ("claude-code", get_mcp_json_config_path(target)),
        ]
    else:
        # Auto-detect based on installed tools
        detected = detector.detect()
        config_paths = []
        if detected.opencode:
            config_paths.append(("opencode", get_opencode_config_path(target)))
        if detected.claude_code:
            config_paths.append(("claude-code", get_mcp_json_config_path(target)))
        # If no tools installed, default to opencode.json
        if not config_paths:
            config_paths = [("opencode", get_opencode_config_path(target))]

    # Build the server config
    base_config: Dict[str, Any] = MCP_SERVERS[server_name].copy()
    if api_key and server_name == "context7":
        base_config["headers"] = {"CONTEXT7_API_KEY": api_key}

    # For OAuth-authenticated servers, try to get stored OAuth token
    server_info = get_mcp_server_info(server_name)
    if server_info and server_info.auth_type == "oauth":
        try:
            from context_harness.oauth import get_mcp_bearer_token

            token = get_mcp_bearer_token(server_name)
            if token:
                base_config["headers"] = {"Authorization": f"Bearer {token}"}
                if not quiet:
                    console.print("[green]✓ Using stored OAuth credentials[/green]")
            else:
                if not quiet:
                    console.print(
                        f"[yellow]Note: No OAuth credentials found. "
                        f"Run 'context-harness mcp auth {server_name}' to authenticate.[/yellow]"
                    )
        except ImportError:
            # OAuth module not available - proceed without token
            pass

    any_updated = False
    any_created = False

    try:
        for tool_type, config_path in config_paths:
            if tool_type == "opencode":
                # Update opencode.json format
                config = load_opencode_config(config_path)
                existed = config_path.exists()

                # Ensure mcp section exists
                if "mcp" not in config:
                    config["mcp"] = {}

                # Check if already configured with same settings
                if server_name in config["mcp"]:
                    if config["mcp"][server_name] == base_config:
                        if not quiet:
                            console.print(
                                f"[dim]MCP server '{server_name}' already configured "
                                f"in {config_path.name}[/dim]"
                            )
                        continue  # Skip this config, check others

                config["mcp"][server_name] = base_config
                save_opencode_config(config_path, config)

                if existed:
                    any_updated = True
                else:
                    any_created = True

                if not quiet:
                    console.print(
                        f"[green]✅ Added '{server_name}' to {config_path.name}[/green]"
                    )

            else:  # claude-code
                # Update .mcp.json format (uses "mcpServers" key)
                config = load_mcp_json_config(config_path)
                existed = config_path.exists()

                # Ensure mcpServers section exists
                if "mcpServers" not in config:
                    config["mcpServers"] = {}

                # Check if already configured with same settings
                if server_name in config["mcpServers"]:
                    if config["mcpServers"][server_name] == base_config:
                        if not quiet:
                            console.print(
                                f"[dim]MCP server '{server_name}' already configured "
                                f"in {config_path.name}[/dim]"
                            )
                        continue  # Skip this config, check others

                config["mcpServers"][server_name] = base_config
                save_mcp_json_config(config_path, config)

                if existed:
                    any_updated = True
                else:
                    any_created = True

                if not quiet:
                    console.print(
                        f"[green]✅ Added '{server_name}' to {config_path.name}[/green]"
                    )

        if any_created:
            return MCPResult.SUCCESS
        elif any_updated:
            return MCPResult.UPDATED
        else:
            return MCPResult.ALREADY_EXISTS

    except PermissionError:
        if not quiet:
            console.print(f"[red]Error: Permission denied writing to config file[/red]")
        return MCPResult.ERROR
    except Exception as e:
        if not quiet:
            console.print(f"[red]Error: {e}[/red]")
        return MCPResult.ERROR


def list_mcp_servers(
    target: str = ".",
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> Dict[str, Any]:
    """List configured MCP servers from opencode.json and/or .mcp.json.

    Args:
        target: Target directory path
        quiet: If True, suppress output messages
        tool_target: Which tool(s) to list servers from:
            - "opencode": Only opencode.json
            - "claude-code": Only .mcp.json
            - "both": Both config files
            - None: Auto-detect based on installed tools

    Returns:
        Dict of configured MCP servers (merged from all sources)
    """
    target_path = Path(target).resolve()
    detector = ToolDetector(target_path)

    # Determine which config files to read
    if tool_target == "opencode":
        config_sources = [("opencode.json", get_opencode_config_path(target), "mcp")]
    elif tool_target == "claude-code":
        config_sources = [(".mcp.json", get_mcp_json_config_path(target), "mcpServers")]
    elif tool_target == "both":
        config_sources = [
            ("opencode.json", get_opencode_config_path(target), "mcp"),
            (".mcp.json", get_mcp_json_config_path(target), "mcpServers"),
        ]
    else:
        # Auto-detect based on installed tools
        detected = detector.detect()
        config_sources = []
        if detected.opencode:
            config_sources.append(
                ("opencode.json", get_opencode_config_path(target), "mcp")
            )
        if detected.claude_code:
            config_sources.append(
                (".mcp.json", get_mcp_json_config_path(target), "mcpServers")
            )
        # If no tools installed, check opencode.json anyway
        if not config_sources:
            config_sources = [
                ("opencode.json", get_opencode_config_path(target), "mcp")
            ]

    all_servers: Dict[str, Any] = {}
    any_found = False

    for source_name, config_path, mcp_key in config_sources:
        if not config_path.exists():
            continue

        if source_name == "opencode.json":
            config = load_opencode_config(config_path)
        else:
            config = load_mcp_json_config(config_path)

        mcp_config = config.get(mcp_key, {})

        if mcp_config:
            any_found = True
            # Merge servers (later sources override earlier for same server name)
            for name, settings in mcp_config.items():
                all_servers[name] = {"source": source_name, "settings": settings}

    if not quiet:
        if any_found:
            console.print("[bold]Configured MCP servers:[/bold]")
            for name, data in all_servers.items():
                settings = data["settings"]
                source = data["source"]
                server_type = settings.get("type", "unknown")
                url = settings.get("url", settings.get("command", "N/A"))
                has_key = "headers" in settings or "--api-key" in str(url)
                key_indicator = " 🔑" if has_key else ""
                console.print(
                    f"  • {name} ({server_type}){key_indicator} [dim]({source})[/dim]"
                )
        else:
            console.print("[dim]No MCP servers configured[/dim]")

    # Return just the server configs (without source info) for backward compat
    return {name: data["settings"] for name, data in all_servers.items()}


def get_available_servers() -> List[str]:
    """Get list of available MCP server names.

    Returns:
        List of server names that can be configured
    """
    return list(MCP_SERVERS.keys())


def get_mcp_server_info(server_name: str) -> Optional[MCPServerInfo]:
    """Get detailed information about a specific MCP server.

    Args:
        server_name: Name of the MCP server

    Returns:
        MCPServerInfo or None if not found
    """
    for server in MCP_REGISTRY:
        if server.name == server_name:
            return server
    return None


def get_mcp_registry() -> List[MCPServerInfo]:
    """Get the full MCP server registry.

    Returns:
        List of all MCPServerInfo objects
    """
    return MCP_REGISTRY.copy()


def list_available_mcp_servers(quiet: bool = False) -> List[MCPServerInfo]:
    """List all available MCP servers that can be configured.

    Args:
        quiet: If True, suppress output messages

    Returns:
        List of MCPServerInfo objects
    """
    servers = get_mcp_registry()

    if not quiet and servers:
        table = Table(title="Available MCP Servers")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Auth", style="dim")

        for server in servers:
            auth_display = server.auth_type or "none"
            table.add_row(server.name, server.description, auth_display)

        console.print(table)

    return servers
