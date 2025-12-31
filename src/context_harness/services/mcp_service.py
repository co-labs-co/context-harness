"""MCP server service for ContextHarness.

Handles MCP server registry, configuration, and management.
Business logic extracted from mcp_config.py module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from context_harness.primitives import (
    ErrorCode,
    Failure,
    MCPAuthType,
    MCPServer,
    MCPServerConfig,
    MCPServerType,
    OpenCodeConfig,
    Result,
    Success,
)
from context_harness.services.config_service import ConfigService


# MCP Server Registry - known servers with their configurations
MCP_REGISTRY: List[Dict[str, Any]] = [
    {
        "name": "context7",
        "url": "https://mcp.context7.com/mcp",
        "description": "Documentation lookup for libraries and frameworks",
        "server_type": "remote",
        "auth_type": "api-key",
    },
    {
        "name": "atlassian",
        "url": "https://mcp.atlassian.com/v1/mcp",
        "description": "Jira, Confluence, and Compass integration via OAuth 2.1",
        "server_type": "remote",
        "auth_type": "oauth",
    },
]


class MCPService:
    """Service for managing MCP servers.

    Handles:
    - Listing available MCP servers from registry
    - Listing configured MCP servers
    - Adding/removing MCP servers from configuration
    - Validating MCP server configurations

    This service does NOT handle OAuth flows - use OAuthService for that.

    Example:
        service = MCPService()

        # List available servers
        result = service.list_available()
        if isinstance(result, Success):
            for server in result.value:
                print(f"{server.name}: {server.description}")

        # Add a server
        result = service.add("context7", Path("/project"))
    """

    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        registry: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the MCP service.

        Args:
            config_service: ConfigService for reading/writing opencode.json
            registry: Custom MCP registry (uses default if None)
        """
        self.config_service = config_service or ConfigService()
        self._registry = registry or MCP_REGISTRY

    def list_available(self) -> Result[List[MCPServer]]:
        """List all available MCP servers from the registry.

        Returns:
            Result containing list of MCPServer objects
        """
        servers = []
        for entry in self._registry:
            # Parse auth type
            auth_type: Optional[MCPAuthType] = None
            if entry.get("auth_type") == "oauth":
                auth_type = MCPAuthType.OAUTH
            elif entry.get("auth_type") == "api-key":
                auth_type = MCPAuthType.API_KEY

            # Parse server type
            server_type = MCPServerType.REMOTE
            if entry.get("server_type") == "local":
                server_type = MCPServerType.LOCAL

            server = MCPServer(
                name=entry["name"],
                url=entry.get("url", ""),
                description=entry.get("description", ""),
                server_type=server_type,
                auth_type=auth_type,
            )
            servers.append(server)

        return Success(value=servers)

    def get_server_info(self, server_name: str) -> Result[MCPServer]:
        """Get detailed information about a specific MCP server.

        Args:
            server_name: Name of the MCP server

        Returns:
            Result containing MCPServer or Failure
        """
        result = self.list_available()
        if isinstance(result, Failure):
            return result

        for server in result.value:
            if server.name == server_name:
                return Success(value=server)

        available = [s.name for s in result.value]
        return Failure(
            error=f"Unknown MCP server '{server_name}'",
            code=ErrorCode.NOT_FOUND,
            details={
                "server_name": server_name,
                "available": available,
            },
        )

    def list_configured(
        self,
        project_path: Optional[Path] = None,
    ) -> Result[Dict[str, MCPServerConfig]]:
        """List MCP servers configured in opencode.json.

        Args:
            project_path: Project directory path

        Returns:
            Result containing dict of server name -> MCPServerConfig
        """
        result = self.config_service.load(project_path)
        if isinstance(result, Failure):
            # Config not found means no servers configured
            if result.code == ErrorCode.CONFIG_MISSING:
                return Success(value={})
            return result

        config = result.value
        return Success(value=dict(config.mcp))

    def add(
        self,
        server_name: str,
        project_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ) -> Result[MCPServerConfig]:
        """Add an MCP server configuration to opencode.json.

        Args:
            server_name: Name of the MCP server (must be in registry)
            project_path: Project directory path
            api_key: Optional API key for servers requiring API key auth
            bearer_token: Optional Bearer token for OAuth servers

        Returns:
            Result containing the added MCPServerConfig
        """
        # Check if server is in registry
        info_result = self.get_server_info(server_name)
        if isinstance(info_result, Failure):
            return info_result

        server_info = info_result.value

        # Build headers if needed
        headers: Dict[str, str] = {}

        if api_key and server_info.auth_type == MCPAuthType.API_KEY:
            # Context7 uses CONTEXT7_API_KEY header
            if server_name == "context7":
                headers = {"CONTEXT7_API_KEY": api_key}
            else:
                headers = {"Authorization": f"Bearer {api_key}"}

        if bearer_token and server_info.auth_type == MCPAuthType.OAUTH:
            headers = {"Authorization": f"Bearer {bearer_token}"}

        # Create server config to add
        server_config = MCPServerConfig(
            name=server_info.name,
            server_type=server_info.server_type,
            url=server_info.url
            if server_info.server_type == MCPServerType.REMOTE
            else None,
            headers=headers if headers else {},
        )

        # Build config dict for update
        config_dict: Dict[str, Any] = {"type": server_config.server_type.value}

        if server_config.url:
            config_dict["url"] = server_config.url
        if headers:
            config_dict["headers"] = headers

        # Update config
        update_result = self.config_service.update_mcp(
            server_name, config_dict, project_path
        )
        if isinstance(update_result, Failure):
            return update_result

        return Success(
            value=server_config,
            message=f"MCP server '{server_name}' added successfully",
        )

    def remove(
        self,
        server_name: str,
        project_path: Optional[Path] = None,
    ) -> Result[bool]:
        """Remove an MCP server configuration from opencode.json.

        Args:
            server_name: Name of the MCP server to remove
            project_path: Project directory path

        Returns:
            Result containing True if removed successfully
        """
        result = self.config_service.remove_mcp(server_name, project_path)
        if isinstance(result, Failure):
            return result

        return Success(
            value=True,
            message=f"MCP server '{server_name}' removed successfully",
        )

    def is_configured(
        self,
        server_name: str,
        project_path: Optional[Path] = None,
    ) -> bool:
        """Check if an MCP server is configured.

        Args:
            server_name: Name of the MCP server
            project_path: Project directory path

        Returns:
            True if server is configured
        """
        result = self.list_configured(project_path)
        if isinstance(result, Failure):
            return False
        return server_name in result.value

    def requires_auth(self, server_name: str) -> Result[Optional[MCPAuthType]]:
        """Check if an MCP server requires authentication.

        Args:
            server_name: Name of the MCP server

        Returns:
            Result containing the auth type (None if no auth required)
        """
        result = self.get_server_info(server_name)
        if isinstance(result, Failure):
            return result

        return Success(value=result.value.auth_type)

    def update_auth(
        self,
        server_name: str,
        bearer_token: str,
        project_path: Optional[Path] = None,
    ) -> Result[MCPServerConfig]:
        """Update authentication for a configured MCP server.

        Use this after OAuth flow completes to update the server's Bearer token.

        Args:
            server_name: Name of the MCP server
            bearer_token: The OAuth bearer token
            project_path: Project directory path

        Returns:
            Result containing updated MCPServerConfig
        """
        # Check if server is configured
        configured_result = self.list_configured(project_path)
        if isinstance(configured_result, Failure):
            return configured_result

        if server_name not in configured_result.value:
            return Failure(
                error=f"MCP server '{server_name}' is not configured",
                code=ErrorCode.NOT_FOUND,
                details={"server_name": server_name},
            )

        current_config = configured_result.value[server_name]

        # Build updated config
        config_dict: Dict[str, Any] = {"type": current_config.server_type.value}

        if current_config.url:
            config_dict["url"] = current_config.url
        if current_config.command:
            config_dict["command"] = current_config.command
        if current_config.args:
            config_dict["args"] = current_config.args
        if current_config.env:
            config_dict["env"] = current_config.env

        # Update headers with new token
        config_dict["headers"] = {"Authorization": f"Bearer {bearer_token}"}

        # Update config
        update_result = self.config_service.update_mcp(
            server_name, config_dict, project_path
        )
        if isinstance(update_result, Failure):
            return update_result

        # Return updated server config
        updated_config = MCPServerConfig(
            name=current_config.name,
            server_type=current_config.server_type,
            url=current_config.url,
            command=current_config.command,
            args=current_config.args,
            env=current_config.env,
            headers={"Authorization": f"Bearer {bearer_token}"},
        )

        return Success(
            value=updated_config,
            message=f"Authentication updated for '{server_name}'",
        )

    def validate_config(
        self,
        server_name: str,
        project_path: Optional[Path] = None,
    ) -> Result[bool]:
        """Validate an MCP server configuration.

        Checks:
        - Server is in registry
        - Required fields are present
        - Auth is configured if required

        Args:
            server_name: Name of the MCP server
            project_path: Project directory path

        Returns:
            Result containing True if valid, Failure with details if not
        """
        # Check registry
        info_result = self.get_server_info(server_name)
        if isinstance(info_result, Failure):
            return info_result

        server_info = info_result.value

        # Check if configured
        configured_result = self.list_configured(project_path)
        if isinstance(configured_result, Failure):
            return configured_result

        if server_name not in configured_result.value:
            return Failure(
                error=f"MCP server '{server_name}' is not configured",
                code=ErrorCode.VALIDATION_ERROR,
            )

        configured = configured_result.value[server_name]

        # Check required fields
        if server_info.server_type == MCPServerType.REMOTE and not configured.url:
            return Failure(
                error=f"Remote MCP server '{server_name}' missing URL",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if server_info.server_type == MCPServerType.LOCAL and not configured.command:
            return Failure(
                error=f"Local MCP server '{server_name}' missing command",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Check auth
        if server_info.auth_type:
            has_auth = configured.headers is not None and (
                "Authorization" in configured.headers
                or any("API_KEY" in k for k in configured.headers.keys())
            )
            if not has_auth:
                return Failure(
                    error=f"MCP server '{server_name}' requires {server_info.auth_type.value} authentication",
                    code=ErrorCode.AUTH_REQUIRED,
                    details={"auth_type": server_info.auth_type.value},
                )

        return Success(value=True, message=f"MCP server '{server_name}' is valid")
