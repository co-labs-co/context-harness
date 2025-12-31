"""Configuration service for ContextHarness.

Handles reading/writing opencode.json configuration files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from context_harness.primitives import (
    ErrorCode,
    Failure,
    OpenCodeConfig,
    ProjectConfig,
    Result,
    Success,
)


class ConfigService:
    """Service for managing opencode.json configuration.

    This service handles:
    - Loading and parsing opencode.json
    - Saving configuration changes
    - Validating configuration structure

    Example:
        service = ConfigService()
        result = service.load(Path("/project"))
        if isinstance(result, Success):
            config = result.value
            print(config.mcp)
    """

    def __init__(self, project_config: Optional[ProjectConfig] = None):
        """Initialize the config service.

        Args:
            project_config: Project configuration with paths. If None, uses CWD.
        """
        self.project_config = project_config or ProjectConfig.from_cwd()

    def load(self, project_path: Optional[Path] = None) -> Result[OpenCodeConfig]:
        """Load opencode.json configuration.

        Args:
            project_path: Project directory path. Uses project_config if None.

        Returns:
            Result containing OpenCodeConfig or Failure
        """
        if project_path:
            config_path = project_path / "opencode.json"
        else:
            config_path = self.project_config.opencode_json_path

        if not config_path.exists():
            return Failure(
                error=f"Configuration file not found: {config_path}",
                code=ErrorCode.CONFIG_MISSING,
                details={"path": str(config_path)},
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = OpenCodeConfig.from_dict(data)
            return Success(value=config)
        except json.JSONDecodeError as e:
            return Failure(
                error=f"Invalid JSON in configuration file: {e}",
                code=ErrorCode.CONFIG_INVALID,
                details={"path": str(config_path), "error": str(e)},
            )
        except PermissionError:
            return Failure(
                error=f"Permission denied reading: {config_path}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(config_path)},
            )
        except Exception as e:
            return Failure(
                error=f"Error loading configuration: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(config_path), "error": str(e)},
            )

    def save(
        self,
        config: OpenCodeConfig,
        project_path: Optional[Path] = None,
    ) -> Result[Path]:
        """Save opencode.json configuration.

        Args:
            config: Configuration to save
            project_path: Project directory path. Uses project_config if None.

        Returns:
            Result containing the saved file path or Failure
        """
        if project_path:
            config_path = project_path / "opencode.json"
        else:
            config_path = self.project_config.opencode_json_path

        try:
            data = config.to_dict()

            # Ensure $schema is first
            if "$schema" not in data:
                data = {"$schema": "https://opencode.ai/config.json", **data}

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")  # Trailing newline

            return Success(value=config_path)

        except PermissionError:
            return Failure(
                error=f"Permission denied writing to: {config_path}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(config_path)},
            )
        except Exception as e:
            return Failure(
                error=f"Error saving configuration: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(config_path), "error": str(e)},
            )

    def load_or_create(
        self,
        project_path: Optional[Path] = None,
    ) -> Result[OpenCodeConfig]:
        """Load existing config or create empty one.

        Args:
            project_path: Project directory path. Uses project_config if None.

        Returns:
            Result containing OpenCodeConfig (existing or new)
        """
        result = self.load(project_path)
        if isinstance(result, Success):
            return result

        # If config missing, return empty config (not an error)
        if isinstance(result, Failure) and result.code == ErrorCode.CONFIG_MISSING:
            return Success(value=OpenCodeConfig())

        # Return other errors as-is
        return result

    def exists(self, project_path: Optional[Path] = None) -> bool:
        """Check if opencode.json exists.

        Args:
            project_path: Project directory path. Uses project_config if None.

        Returns:
            True if config file exists
        """
        if project_path:
            config_path = project_path / "opencode.json"
        else:
            config_path = self.project_config.opencode_json_path
        return config_path.exists()

    def update_mcp(
        self,
        server_name: str,
        server_config: Dict[str, Any],
        project_path: Optional[Path] = None,
    ) -> Result[OpenCodeConfig]:
        """Update or add an MCP server configuration.

        Args:
            server_name: Name of the MCP server
            server_config: Server configuration dict
            project_path: Project directory path

        Returns:
            Result containing updated OpenCodeConfig
        """
        # Load or create config
        result = self.load_or_create(project_path)
        if isinstance(result, Failure):
            return result

        config = result.value

        # Create updated MCP dict
        from context_harness.primitives.mcp import MCPServerConfig

        new_server = MCPServerConfig.from_dict(server_name, server_config)
        updated_mcp = dict(config.mcp)
        updated_mcp[server_name] = new_server

        # Create new config with updated MCP
        updated_config = OpenCodeConfig(
            schema_version=config.schema_version,
            mcp=updated_mcp,
            agents=config.agents,
            commands=config.commands,
            skills=config.skills,
            project_context=config.project_context,
            raw_data=config.raw_data,
        )

        # Save and return
        save_result = self.save(updated_config, project_path)
        if isinstance(save_result, Failure):
            return save_result

        return Success(value=updated_config)

    def remove_mcp(
        self,
        server_name: str,
        project_path: Optional[Path] = None,
    ) -> Result[OpenCodeConfig]:
        """Remove an MCP server configuration.

        Args:
            server_name: Name of the MCP server to remove
            project_path: Project directory path

        Returns:
            Result containing updated OpenCodeConfig
        """
        # Load config
        result = self.load(project_path)
        if isinstance(result, Failure):
            return result

        config = result.value

        if server_name not in config.mcp:
            return Failure(
                error=f"MCP server '{server_name}' not found in configuration",
                code=ErrorCode.NOT_FOUND,
                details={"server_name": server_name},
            )

        # Create updated MCP dict without the server
        updated_mcp = {k: v for k, v in config.mcp.items() if k != server_name}

        # Create new config with updated MCP
        updated_config = OpenCodeConfig(
            schema_version=config.schema_version,
            mcp=updated_mcp,
            agents=config.agents,
            commands=config.commands,
            skills=config.skills,
            project_context=config.project_context,
            raw_data=config.raw_data,
        )

        # Save and return
        save_result = self.save(updated_config, project_path)
        if isinstance(save_result, Failure):
            return save_result

        return Success(value=updated_config)
