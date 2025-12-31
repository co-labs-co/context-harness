"""MCP (Model Context Protocol) primitives for ContextHarness.

MCP servers provide external tool integrations for AI agents.
These primitives define the configuration and metadata for MCP servers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MCPServerType(Enum):
    """Type of MCP server deployment."""

    REMOTE = "remote"  # HTTP/SSE remote server
    LOCAL = "local"  # Local stdio process


class MCPAuthType(Enum):
    """Authentication type for MCP servers."""

    NONE = "none"
    API_KEY = "api-key"
    OAUTH = "oauth"


@dataclass
class MCPServer:
    """An MCP server configuration in the registry.

    Represents an available MCP server that can be configured.

    Attributes:
        name: Server identifier (e.g., "context7", "atlassian")
        url: Server URL or command
        description: Human-readable description
        server_type: Remote or local server
        auth_type: Required authentication type
    """

    name: str
    url: str
    description: str
    server_type: MCPServerType = MCPServerType.REMOTE
    auth_type: Optional[MCPAuthType] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for opencode.json.

        Returns:
            Dict suitable for MCP config
        """
        result = {
            "type": self.server_type.value,
            "url": self.url,
        }
        return result

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServer":
        """Create from registry dict.

        Args:
            name: Server name
            data: Registry entry data

        Returns:
            MCPServer instance
        """
        return cls(
            name=name,
            url=data.get("url", ""),
            description=data.get("description", ""),
            server_type=MCPServerType(data.get("type", "remote")),
            auth_type=MCPAuthType(data["auth_type"]) if data.get("auth_type") else None,
        )


@dataclass
class MCPServerConfig:
    """MCP server configuration as stored in opencode.json.

    Represents how an MCP server is configured for a specific project.

    Attributes:
        name: Server identifier
        server_type: Remote or local
        url: Server URL (for remote)
        command: Command to run (for local)
        args: Command arguments (for local)
        env: Environment variables
        headers: HTTP headers (for remote, e.g., API keys)
    """

    name: str
    server_type: MCPServerType
    url: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to opencode.json format.

        Returns:
            Dict for opencode.json mcp section
        """
        result: Dict[str, Any] = {"type": self.server_type.value}

        if self.server_type == MCPServerType.REMOTE:
            if self.url:
                result["url"] = self.url
            if self.headers:
                result["headers"] = self.headers
        else:
            if self.command:
                result["command"] = self.command
            if self.args:
                result["args"] = self.args

        if self.env:
            result["env"] = self.env

        return result

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create from opencode.json dict.

        Args:
            name: Server name
            data: Config dict from opencode.json

        Returns:
            MCPServerConfig instance
        """
        server_type = MCPServerType(data.get("type", "remote"))
        return cls(
            name=name,
            server_type=server_type,
            url=data.get("url"),
            command=data.get("command"),
            args=data.get("args", []),
            env=data.get("env", {}),
            headers=data.get("headers", {}),
        )


@dataclass
class MCPRegistry:
    """Registry of available MCP servers.

    Contains all MCP servers that ContextHarness knows about.

    Attributes:
        servers: List of available servers
    """

    servers: List[MCPServer] = field(default_factory=list)

    def get(self, name: str) -> Optional[MCPServer]:
        """Get server by name.

        Args:
            name: Server name

        Returns:
            MCPServer or None
        """
        for server in self.servers:
            if server.name == name:
                return server
        return None

    def names(self) -> List[str]:
        """Get all server names.

        Returns:
            List of server names
        """
        return [s.name for s in self.servers]
