"""Project-level ContextHarness configuration service.

Handles reading/writing project-level configuration (.context-harness/config.json).
This replaces the previous pattern of storing skillsRegistry in opencode.json,
which caused schema validation errors since opencode.json has a strict schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from context_harness.primitives import (
    ErrorCode,
    Failure,
    ProjectHarnessConfig,
    Result,
    Success,
)


class ProjectHarnessConfigService:
    """Service for managing project-level ContextHarness configuration.

    This service handles:
    - Loading and parsing .context-harness/config.json
    - Saving project-level configuration changes
    - Creating the config file if needed

    The .context-harness/config.json file stores project-specific settings
    that don't belong in opencode.json (which has its own schema).

    Example:
        service = ProjectHarnessConfigService()
        result = service.load()
        if isinstance(result, Success):
            config = result.value
            print(config.skills_registry)
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the project harness config service.

        Args:
            config_path: Override config file path (for testing).
                         Defaults to .context-harness/config.json in CWD.
        """
        if config_path:
            self._config_path = config_path
        else:
            self._config_path = Path.cwd() / ".context-harness" / "config.json"

    @property
    def config_path(self) -> Path:
        """Get the config file path."""
        return self._config_path

    @property
    def config_dir(self) -> Path:
        """Get the config directory path."""
        return self._config_path.parent

    def load(self) -> Result[ProjectHarnessConfig]:
        """Load project-level configuration.

        Returns:
            Result containing ProjectHarnessConfig or Failure
        """
        if not self._config_path.exists():
            # Return empty config if file doesn't exist (not an error)
            return Success(value=ProjectHarnessConfig())

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = ProjectHarnessConfig.from_dict(data)
            return Success(value=config)
        except json.JSONDecodeError as e:
            return Failure(
                error=f"Invalid JSON in project config: {e}",
                code=ErrorCode.CONFIG_INVALID,
                details={"path": str(self._config_path), "error": str(e)},
            )
        except PermissionError:
            return Failure(
                error=f"Permission denied reading: {self._config_path}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(self._config_path)},
            )
        except Exception as e:
            return Failure(
                error=f"Error loading project config: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(self._config_path), "error": str(e)},
            )

    def save(self, config: ProjectHarnessConfig) -> Result[Path]:
        """Save project-level configuration.

        Args:
            config: Configuration to save

        Returns:
            Result containing the saved file path or Failure
        """
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)

            data = config.to_dict()

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")  # Trailing newline

            return Success(value=self._config_path)

        except PermissionError:
            return Failure(
                error=f"Permission denied writing to: {self._config_path}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(self._config_path)},
            )
        except Exception as e:
            return Failure(
                error=f"Error saving project config: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(self._config_path), "error": str(e)},
            )

    def exists(self) -> bool:
        """Check if project config file exists.

        Returns:
            True if config file exists
        """
        return self._config_path.exists()

    def ensure_config_dir(self) -> Result[Path]:
        """Ensure the config directory exists.

        Returns:
            Result containing the directory path or Failure
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return Success(value=self.config_dir)
        except PermissionError:
            return Failure(
                error=f"Permission denied creating: {self.config_dir}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(self.config_dir)},
            )
        except Exception as e:
            return Failure(
                error=f"Error creating config directory: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(self.config_dir), "error": str(e)},
            )
