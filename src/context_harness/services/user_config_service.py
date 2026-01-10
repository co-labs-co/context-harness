"""User configuration service for ContextHarness.

Handles reading/writing user-level configuration (~/.context-harness/config.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Result,
    Success,
    UserConfig,
)


class UserConfigService:
    """Service for managing user-level configuration.

    This service handles:
    - Loading and parsing ~/.context-harness/config.json
    - Saving user configuration changes
    - Creating the config directory if needed

    Example:
        service = UserConfigService()
        result = service.load()
        if isinstance(result, Success):
            config = result.value
            print(config.skills_registry)
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the user config service.

        Args:
            config_path: Override config file path (for testing)
        """
        self._config_path = config_path or UserConfig.config_path()

    @property
    def config_path(self) -> Path:
        """Get the config file path."""
        return self._config_path

    @property
    def config_dir(self) -> Path:
        """Get the config directory path."""
        return self._config_path.parent

    def load(self) -> Result[UserConfig]:
        """Load user configuration.

        Returns:
            Result containing UserConfig or Failure
        """
        if not self._config_path.exists():
            # Return empty config if file doesn't exist (not an error)
            return Success(value=UserConfig())

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = UserConfig.from_dict(data)
            return Success(value=config)
        except json.JSONDecodeError as e:
            return Failure(
                error=f"Invalid JSON in user config: {e}",
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
                error=f"Error loading user config: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(self._config_path), "error": str(e)},
            )

    def save(self, config: UserConfig) -> Result[Path]:
        """Save user configuration.

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
                error=f"Error saving user config: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(self._config_path), "error": str(e)},
            )

    def exists(self) -> bool:
        """Check if user config file exists.

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
