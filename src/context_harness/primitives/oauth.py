"""OAuth primitives for ContextHarness.

OAuth primitives for authenticating with MCP servers and other services.
These are pure data structures with no I/O operations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AuthStatus(Enum):
    """Status of OAuth authentication."""

    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATED = "authenticated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"


@dataclass(frozen=True)
class PKCEChallenge:
    """PKCE (Proof Key for Code Exchange) challenge pair.

    Used for OAuth 2.1 to prevent authorization code interception attacks.

    Attributes:
        code_verifier: Random string used to generate challenge
        code_challenge: SHA-256 hash of verifier, base64url encoded
        code_challenge_method: Always "S256" for SHA-256
    """

    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass
class OAuthTokens:
    """OAuth token storage.

    Holds access and refresh tokens with expiration tracking.

    Attributes:
        access_token: The access token for API calls
        token_type: Token type (usually "Bearer")
        expires_in: Token lifetime in seconds (from when issued)
        refresh_token: Token for refreshing access token
        scope: Granted scopes
        issued_at: Unix timestamp when token was issued
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    issued_at: float = field(default_factory=time.time)

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if the access token has expired.

        Args:
            buffer_seconds: Buffer time before actual expiration

        Returns:
            True if token is expired or will expire within buffer
        """
        if self.expires_in is None:
            return False
        return time.time() > (self.issued_at + self.expires_in - buffer_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dict suitable for JSON serialization
        """
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "issued_at": self.issued_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthTokens":
        """Create from dictionary.

        Args:
            data: Token data dict

        Returns:
            OAuthTokens instance
        """
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            issued_at=data.get("issued_at", time.time()),
        )

    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> "OAuthTokens":
        """Create from OAuth token response.

        Args:
            response: Raw token endpoint response

        Returns:
            OAuthTokens instance with issued_at set to now
        """
        return cls(
            access_token=response["access_token"],
            token_type=response.get("token_type", "Bearer"),
            expires_in=response.get("expires_in"),
            refresh_token=response.get("refresh_token"),
            scope=response.get("scope"),
            issued_at=time.time(),
        )


@dataclass
class OAuthConfig:
    """Configuration for an OAuth provider.

    Generic OAuth configuration that works with any provider.
    Provider-specific configs can be created via factory methods.

    Attributes:
        service_name: Provider identifier (e.g., "atlassian", "github")
        client_id: OAuth client ID
        auth_url: Authorization endpoint URL
        token_url: Token endpoint URL
        client_secret: OAuth client secret (optional for public clients)
        scopes: List of OAuth scopes to request
        audience: Audience parameter (required by some providers)
        resources_url: URL to fetch accessible resources (e.g., Atlassian sites)
        extra_auth_params: Additional params for authorization request
        display_name: Human-readable name for UI
        setup_url: URL where users create OAuth apps
    """

    service_name: str
    client_id: str
    auth_url: str
    token_url: str
    client_secret: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    audience: Optional[str] = None
    resources_url: Optional[str] = None
    extra_auth_params: Dict[str, str] = field(default_factory=dict)
    display_name: Optional[str] = None
    setup_url: Optional[str] = None


@dataclass
class OAuthProvider:
    """OAuth provider template.

    Defines the OAuth configuration template for a provider.
    The client_id is left empty and filled in at runtime.

    Attributes:
        service_name: Provider identifier
        auth_url: Authorization endpoint
        token_url: Token endpoint
        scopes: Default scopes to request
        audience: Audience parameter
        resources_url: Resources endpoint
        display_name: Human-readable name
        setup_url: URL for creating OAuth apps
    """

    service_name: str
    auth_url: str
    token_url: str
    scopes: List[str] = field(default_factory=list)
    audience: Optional[str] = None
    resources_url: Optional[str] = None
    display_name: Optional[str] = None
    setup_url: Optional[str] = None

    def to_config(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
    ) -> OAuthConfig:
        """Create OAuthConfig with credentials.

        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret (optional)

        Returns:
            Complete OAuthConfig for this provider
        """
        return OAuthConfig(
            service_name=self.service_name,
            client_id=client_id,
            client_secret=client_secret,
            auth_url=self.auth_url,
            token_url=self.token_url,
            scopes=self.scopes.copy(),
            audience=self.audience,
            resources_url=self.resources_url,
            display_name=self.display_name,
            setup_url=self.setup_url,
        )


# Well-known OAuth providers
ATLASSIAN_PROVIDER = OAuthProvider(
    service_name="atlassian",
    auth_url="https://auth.atlassian.com/authorize",
    token_url="https://auth.atlassian.com/oauth/token",
    scopes=[
        "read:jira-work",
        "read:jira-user",
        "read:confluence-content.all",
        "read:confluence-space.summary",
        "offline_access",
    ],
    audience="api.atlassian.com",
    resources_url="https://api.atlassian.com/oauth/token/accessible-resources",
    display_name="Atlassian",
    setup_url="https://developer.atlassian.com/console/myapps/",
)


@dataclass
class OAuthResource:
    """An accessible OAuth resource (e.g., Atlassian site).

    Represents a resource the user has access to after OAuth.

    Attributes:
        id: Resource identifier (e.g., cloud ID)
        url: Resource URL
        name: Human-readable name
        scopes: Granted scopes for this resource
        avatar_url: Avatar/icon URL
    """

    id: str
    url: str
    name: str
    scopes: List[str] = field(default_factory=list)
    avatar_url: Optional[str] = None
