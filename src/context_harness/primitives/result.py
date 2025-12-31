"""Result types for ContextHarness operations.

Provides a functional Result pattern for explicit error handling
without relying on exceptions for control flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar, Union

T = TypeVar("T")


class ErrorCode(Enum):
    """Standard error codes for ContextHarness operations."""

    # General errors
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"

    # Authentication errors
    AUTH_REQUIRED = "auth_required"
    AUTH_FAILED = "auth_failed"
    AUTH_EXPIRED = "auth_expired"
    AUTH_CANCELLED = "auth_cancelled"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"

    # Network errors
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"

    # Configuration errors
    CONFIG_INVALID = "config_invalid"
    CONFIG_MISSING = "config_missing"

    # Skill errors
    SKILL_NOT_FOUND = "skill_not_found"
    SKILL_INVALID = "skill_invalid"
    SKILL_INSTALL_FAILED = "skill_install_failed"

    # Session errors
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_CORRUPTED = "session_corrupted"

    # MCP errors
    MCP_SERVER_NOT_FOUND = "mcp_server_not_found"
    MCP_CONFIG_ERROR = "mcp_config_error"


@dataclass(frozen=True)
class Success(Generic[T]):
    """Successful operation result.

    Attributes:
        value: The result value
        message: Optional success message for display
    """

    value: T
    message: Optional[str] = None


@dataclass(frozen=True)
class Failure:
    """Failed operation result.

    Attributes:
        error: Human-readable error message
        code: Standardized error code
        details: Optional additional error context
    """

    error: str
    code: ErrorCode
    details: Optional[Dict[str, Any]] = None


# Result is either Success or Failure
Result = Union[Success[T], Failure]


def is_success(result: Result[T]) -> bool:
    """Check if a result is a Success.

    Args:
        result: The result to check

    Returns:
        True if the result is a Success, False otherwise
    """
    return isinstance(result, Success)


def is_failure(result: Result[T]) -> bool:
    """Check if a result is a Failure.

    Args:
        result: The result to check

    Returns:
        True if the result is a Failure, False otherwise
    """
    return isinstance(result, Failure)


def success(value: T, message: Optional[str] = None) -> Success[T]:
    """Create a Success result.

    Args:
        value: The success value
        message: Optional message

    Returns:
        A Success instance
    """
    return Success(value=value, message=message)


def failure(
    error: str,
    code: ErrorCode = ErrorCode.UNKNOWN,
    details: Optional[Dict[str, Any]] = None,
) -> Failure:
    """Create a Failure result.

    Args:
        error: Error message
        code: Error code
        details: Optional details

    Returns:
        A Failure instance
    """
    return Failure(error=error, code=code, details=details)
