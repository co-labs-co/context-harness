"""SDK Client for ContextHarness.

High-level client that wraps services for programmatic access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

from context_harness.primitives import (
    AuthStatus,
    ErrorCode,
    Failure,
    MCPServer,
    MCPServerConfig,
    OAuthTokens,
    OpenCodeConfig,
    Result,
    Skill,
    SkillMetadata,
    Success,
)
from context_harness.services import (
    ConfigService,
    MCPService,
    OAuthService,
    SkillService,
)
from context_harness.storage import FileStorage, MemoryStorage, StorageProtocol


class ConfigClient:
    """Client for configuration operations.

    Provides a convenient interface for managing opencode.json configuration.

    Example:
        client = Client()
        config = client.config.load()
        if isinstance(config, Success):
            print(f"Project: {config.value.project.name}")
    """

    def __init__(self, service: ConfigService, working_dir: Path):
        self._service = service
        self._working_dir = working_dir

    @property
    def config_path(self) -> Path:
        """Get the path to opencode.json."""
        return self._working_dir / "opencode.json"

    def load(self) -> Result[OpenCodeConfig]:
        """Load configuration from opencode.json.

        Returns:
            Result containing OpenCodeConfig or Failure
        """
        return self._service.load(self._working_dir)

    def save(self, config: OpenCodeConfig) -> Result[Path]:
        """Save configuration to opencode.json.

        Args:
            config: Configuration to save

        Returns:
            Result containing saved path or Failure
        """
        return self._service.save(config, self._working_dir)

    def exists(self) -> bool:
        """Check if opencode.json exists."""
        return self._service.exists(self._working_dir)

    def add_mcp_server(
        self, name: str, server: MCPServerConfig
    ) -> Result[OpenCodeConfig]:
        """Add an MCP server to configuration.

        Args:
            name: Server name
            server: Server configuration

        Returns:
            Result containing updated config
        """
        config_result = self.load()
        if isinstance(config_result, Failure):
            # Create new config if doesn't exist
            config = OpenCodeConfig()
        else:
            config = config_result.value

        result = self._service.add_mcp_server(config, name, server)
        if isinstance(result, Success):
            self.save(result.value)
        return result

    def remove_mcp_server(self, name: str) -> Result[OpenCodeConfig]:
        """Remove an MCP server from configuration.

        Args:
            name: Server name to remove

        Returns:
            Result containing updated config
        """
        config_result = self.load()
        if isinstance(config_result, Failure):
            return config_result

        result = self._service.remove_mcp_server(config_result.value, name)
        if isinstance(result, Success):
            self.save(result.value)
        return result


class MCPClient:
    """Client for MCP server operations.

    Provides access to the MCP server registry and configuration.

    Example:
        client = Client()
        servers = client.mcp.list_available()
        if isinstance(servers, Success):
            for server in servers.value:
                print(f"{server.name}: {server.description}")
    """

    def __init__(self, service: MCPService):
        self._service = service

    def list_available(self) -> Result[List[MCPServer]]:
        """List available MCP servers from the registry.

        Returns:
            Result containing list of MCPServer
        """
        return self._service.list_available()

    def get(self, name: str) -> Result[MCPServer]:
        """Get a specific MCP server by name.

        Args:
            name: Server name

        Returns:
            Result containing MCPServer
        """
        return self._service.get_server_info(name)

    def search(self, query: str) -> Result[List[MCPServer]]:
        """Search for MCP servers matching a query.

        Note: Currently returns all servers filtered by name/description.
        The underlying service doesn't have a dedicated search method yet.

        Args:
            query: Search query

        Returns:
            Result containing matching servers
        """
        result = self._service.list_available()
        if isinstance(result, Failure):
            return result
        # Filter by query in name or description
        query_lower = query.lower()
        filtered = [
            s
            for s in result.value
            if query_lower in s.name.lower() or query_lower in s.description.lower()
        ]
        return Success(value=filtered)


class OAuthClient:
    """Client for OAuth operations.

    Provides OAuth authentication flows for MCP servers.

    Example:
        client = Client()
        status = client.oauth.get_status("atlassian")
        if isinstance(status, Success):
            if status.value == AuthStatus.NOT_AUTHENTICATED:
                client.oauth.authenticate("atlassian")
    """

    def __init__(self, service: OAuthService):
        self._service = service

    def get_status(self, service_name: str) -> Result[AuthStatus]:
        """Get authentication status for a service.

        Args:
            service_name: OAuth service name (e.g., "atlassian")

        Returns:
            Result containing AuthStatus
        """
        return self._service.get_status(service_name)

    def get_tokens(self, service_name: str) -> Result[OAuthTokens]:
        """Get stored tokens for a service.

        Args:
            service_name: OAuth service name

        Returns:
            Result containing OAuthTokens
        """
        return self._service.get_tokens(service_name)

    def authenticate(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        open_browser: bool = True,
    ) -> Result[OAuthTokens]:
        """Run OAuth authentication flow.

        Args:
            service_name: OAuth service name
            client_id: OAuth client ID (uses env var if not provided)
            client_secret: OAuth client secret (optional)
            open_browser: Whether to open browser automatically

        Returns:
            Result containing OAuthTokens
        """
        return self._service.authenticate(
            service_name,
            client_id=client_id,
            client_secret=client_secret,
            open_browser=open_browser,
        )

    def refresh(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Result[OAuthTokens]:
        """Refresh OAuth tokens.

        Args:
            service_name: OAuth service name
            client_id: OAuth client ID
            client_secret: OAuth client secret

        Returns:
            Result containing new OAuthTokens
        """
        return self._service.refresh_tokens(
            service_name, client_id=client_id, client_secret=client_secret
        )

    def ensure_valid(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Result[OAuthTokens]:
        """Ensure we have valid tokens, refreshing if needed.

        Args:
            service_name: OAuth service name
            client_id: OAuth client ID
            client_secret: OAuth client secret

        Returns:
            Result containing valid OAuthTokens
        """
        return self._service.ensure_valid_token(
            service_name, client_id=client_id, client_secret=client_secret
        )

    def logout(self, service_name: str) -> Result[bool]:
        """Remove stored tokens (logout).

        Args:
            service_name: OAuth service name

        Returns:
            Result containing True if logged out
        """
        return self._service.logout(service_name)


class SkillClient:
    """Client for skill operations.

    Provides skill listing, installation, and extraction.

    Example:
        client = Client()
        skills = client.skills.list_local()
        if isinstance(skills, Success):
            for skill in skills.value:
                print(f"{skill.name}: {skill.description}")
    """

    def __init__(self, service: SkillService, working_dir: Path):
        self._service = service
        self._working_dir = working_dir

    @property
    def skills_dir(self) -> Path:
        """Get the skills directory path."""
        return self._working_dir / ".opencode" / "skill"

    def list_local(self) -> Result[List[Skill]]:
        """List locally installed skills.

        Returns:
            Result containing list of Skill
        """
        return self._service.list_local(self._working_dir)

    def list_remote(self) -> Result[List[Skill]]:
        """List available skills from the remote registry.

        Returns:
            Result containing list of Skill
        """
        return self._service.list_remote()

    def get(self, name: str) -> Result[Skill]:
        """Get a skill by name from the remote registry.

        Args:
            name: Skill name

        Returns:
            Result containing Skill
        """
        return self._service.get_info(name)

    def install(self, skill_name: str, force: bool = False) -> Result[Skill]:
        """Install a skill from the remote registry.

        Args:
            skill_name: Name of the skill to install
            force: If True, overwrite existing skill

        Returns:
            Result containing installed Skill
        """
        return self._service.install(skill_name, self._working_dir, force=force)

    def validate(self, skill_path: Path) -> Result[SkillMetadata]:
        """Validate a skill directory.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Result containing SkillMetadata if valid
        """
        return self._service.validate(skill_path)


class Client:
    """High-level SDK client for ContextHarness.

    Provides a convenient interface to all ContextHarness functionality.
    The client assembles services and provides sub-clients for each domain.

    Example:
        # Basic usage
        client = Client()

        # Load configuration
        config = client.config.load()

        # List MCP servers
        servers = client.mcp.list_available()

        # Check OAuth status
        status = client.oauth.get_status("atlassian")

        # List local skills
        skills = client.skills.list_local()

    Attributes:
        config: Configuration client
        mcp: MCP server client
        oauth: OAuth client
        skills: Skill client
    """

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        storage: Optional[StorageProtocol] = None,
    ):
        """Initialize the SDK client.

        Args:
            working_dir: Working directory (defaults to current directory)
            storage: Storage backend (defaults to FileStorage)
        """
        self._working_dir = working_dir or Path.cwd()
        self._storage = storage or FileStorage(self._working_dir)

        # Initialize services
        self._config_service = ConfigService()
        self._mcp_service = MCPService()
        self._oauth_service = OAuthService()
        self._skill_service = SkillService()

        # Create sub-clients
        self.config = ConfigClient(self._config_service, self._working_dir)
        self.mcp = MCPClient(self._mcp_service)
        self.oauth = OAuthClient(self._oauth_service)
        self.skills = SkillClient(self._skill_service, self._working_dir)

    @property
    def working_dir(self) -> Path:
        """Get the working directory."""
        return self._working_dir

    @property
    def storage(self) -> StorageProtocol:
        """Get the storage backend."""
        return self._storage

    @classmethod
    def create(
        cls,
        working_dir: Optional[Path] = None,
        use_memory_storage: bool = False,
    ) -> "Client":
        """Create a client with optional configuration.

        Args:
            working_dir: Working directory
            use_memory_storage: Use in-memory storage (for testing)

        Returns:
            Configured Client instance
        """
        wd = working_dir or Path.cwd()
        storage: StorageProtocol
        if use_memory_storage:
            storage = MemoryStorage()
        else:
            storage = FileStorage(wd)

        return cls(working_dir=wd, storage=storage)


# Convenience function for quick access
def create_client(
    working_dir: Optional[Path] = None,
    use_memory_storage: bool = False,
) -> Client:
    """Create a ContextHarness SDK client.

    Args:
        working_dir: Working directory (defaults to current directory)
        use_memory_storage: Use in-memory storage (for testing)

    Returns:
        Configured Client instance

    Example:
        from context_harness.interfaces.sdk import create_client

        client = create_client()
        config = client.config.load()
    """
    return Client.create(working_dir=working_dir, use_memory_storage=use_memory_storage)
