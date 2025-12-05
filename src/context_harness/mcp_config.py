"""MCP configuration management for ContextHarness."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


class MCPResult(Enum):
    """Result of an MCP configuration operation."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    UPDATED = "updated"
    ERROR = "error"


# Known MCP server configurations
MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "context7": {
        "type": "remote",
        "url": "https://mcp.context7.com/mcp",
    },
}


def get_opencode_config_path(target: str = ".") -> Path:
    """Get the path to the opencode.json config file.

    Args:
        target: Target directory path (default: current directory)

    Returns:
        Path to opencode.json in the target directory
    """
    return Path(target).resolve() / "opencode.json"


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


def add_mcp_server(
    server_name: str,
    target: str = ".",
    api_key: Optional[str] = None,
    quiet: bool = False,
) -> MCPResult:
    """Add an MCP server configuration to opencode.json.

    Args:
        server_name: Name of the MCP server (e.g., "context7")
        target: Target directory path
        api_key: Optional API key for the server
        quiet: If True, suppress output messages

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

    config_path = get_opencode_config_path(target)

    try:
        # Load existing config
        config = load_opencode_config(config_path)
        existed = config_path.exists()

        # Ensure mcp section exists
        if "mcp" not in config:
            config["mcp"] = {}

        # Build new server config
        new_config: Dict[str, Any] = MCP_SERVERS[server_name].copy()
        if api_key and server_name == "context7":
            new_config["headers"] = {"CONTEXT7_API_KEY": api_key}

        # Check if server already configured with same settings
        if server_name in config["mcp"]:
            existing = config["mcp"][server_name]
            if existing == new_config:
                if not quiet:
                    console.print(
                        f"[yellow]MCP server '{server_name}' already configured "
                        "with same settings[/yellow]"
                    )
                return MCPResult.ALREADY_EXISTS

        # Add server config
        config["mcp"][server_name] = new_config

        # Save config
        save_opencode_config(config_path, config)

        if not quiet:
            if existed:
                console.print(
                    f"[green]✅ Added '{server_name}' MCP to existing opencode.json[/green]"
                )
            else:
                console.print(
                    f"[green]✅ Created opencode.json with '{server_name}' MCP[/green]"
                )

        return MCPResult.UPDATED if existed else MCPResult.SUCCESS

    except PermissionError:
        if not quiet:
            console.print(
                f"[red]Error: Permission denied writing to {config_path}[/red]"
            )
        return MCPResult.ERROR
    except Exception as e:
        if not quiet:
            console.print(f"[red]Error: {e}[/red]")
        return MCPResult.ERROR


def list_mcp_servers(target: str = ".", quiet: bool = False) -> Dict[str, Any]:
    """List configured MCP servers from opencode.json.

    Args:
        target: Target directory path
        quiet: If True, suppress output messages

    Returns:
        Dict of configured MCP servers
    """
    config_path = get_opencode_config_path(target)

    if not config_path.exists():
        if not quiet:
            console.print("[dim]No opencode.json found[/dim]")
        return {}

    config = load_opencode_config(config_path)
    mcp_config = config.get("mcp", {})

    if not quiet:
        if mcp_config:
            console.print("[bold]Configured MCP servers:[/bold]")
            for name, settings in mcp_config.items():
                server_type = settings.get("type", "unknown")
                url = settings.get("url", settings.get("command", "N/A"))
                has_key = "headers" in settings or "--api-key" in str(url)
                key_indicator = " 🔑" if has_key else ""
                console.print(f"  • {name} ({server_type}){key_indicator}")
        else:
            console.print("[dim]No MCP servers configured[/dim]")

    return mcp_config


def get_available_servers() -> List[str]:
    """Get list of available MCP server names.

    Returns:
        List of server names that can be configured
    """
    return list(MCP_SERVERS.keys())
