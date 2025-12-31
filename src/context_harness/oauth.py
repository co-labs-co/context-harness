"""OAuth 2.1 authentication flow for MCP servers.

Implements a generic OAuth 2.1 flow with PKCE for authenticating with any MCP server
that requires OAuth (e.g., Atlassian, GitHub, etc.). Uses a local HTTP callback
server to receive the authorization code.

The flow is provider-agnostic - each MCP server can define its own OAuth configuration
in the MCP registry, and this module handles the authentication flow generically.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError

from rich.console import Console

console = Console()


class OAuthError(Exception):
    """Base exception for OAuth errors."""

    pass


class OAuthTimeoutError(OAuthError):
    """Raised when OAuth flow times out waiting for callback."""

    pass


class OAuthCancelledError(OAuthError):
    """Raised when user cancels OAuth flow."""

    pass


class TokenStorageError(OAuthError):
    """Raised when token storage/retrieval fails."""

    pass


class AuthStatus(Enum):
    """Status of OAuth authentication."""

    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATED = "authenticated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"


@dataclass
class PKCEChallenge:
    """PKCE (Proof Key for Code Exchange) challenge pair.

    Used for OAuth 2.1 to prevent authorization code interception attacks.
    """

    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass
class OAuthTokens:
    """OAuth token storage."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    issued_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_in is None:
            return False
        # Add 60 second buffer for clock skew
        return time.time() > (self.issued_at + self.expires_in - 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
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
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            issued_at=data.get("issued_at", time.time()),
        )


@dataclass
class AtlassianResource:
    """An accessible Atlassian cloud resource (site)."""

    id: str  # Cloud ID
    url: str
    name: str
    scopes: List[str]
    avatar_url: Optional[str] = None


def generate_pkce() -> PKCEChallenge:
    """Generate a PKCE code verifier and challenge.

    Uses SHA-256 (S256) method as required by OAuth 2.1 and Atlassian.

    Returns:
        PKCEChallenge with verifier and challenge
    """
    # Generate a random 32-byte (256-bit) verifier
    # Base64url encode without padding to create a 43-character string
    random_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii")

    # Create SHA-256 hash of verifier and base64url encode
    verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode("ascii")
    )

    return PKCEChallenge(
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


def generate_state() -> str:
    """Generate a random state parameter for CSRF protection.

    Returns:
        Random 32-character hex string
    """
    return secrets.token_hex(16)


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback.

    Receives the authorization code from the OAuth provider after user authorization.
    """

    # Class variables to store callback data
    authorization_code: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None
    received_state: Optional[str] = None
    callback_received: threading.Event = threading.Event()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress HTTP server logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request (OAuth callback)."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # Extract parameters
        OAuthCallbackHandler.received_state = params.get("state", [None])[0]

        if "error" in params:
            OAuthCallbackHandler.error = params.get("error", ["unknown"])[0]
            OAuthCallbackHandler.error_description = params.get(
                "error_description", [""]
            )[0]
            self._send_error_response()
        elif "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            self._send_success_response()
        else:
            OAuthCallbackHandler.error = "missing_code"
            OAuthCallbackHandler.error_description = "No authorization code received"
            self._send_error_response()

        OAuthCallbackHandler.callback_received.set()

    def _send_success_response(self) -> None:
        """Send success HTML response."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html = """<!DOCTYPE html>
<html>
<head>
    <title>Authentication Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            max-width: 400px;
        }
        .icon { font-size: 64px; margin-bottom: 20px; }
        h1 { color: #22c55e; margin: 0 0 10px 0; font-size: 24px; }
        p { color: #666; margin: 0; }
        .hint { margin-top: 20px; font-size: 14px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">✅</div>
        <h1>Authentication Successful!</h1>
        <p>You can close this window and return to your terminal.</p>
        <p class="hint">context-harness has received the authorization.</p>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode())

    def _send_error_response(self) -> None:
        """Send error HTML response."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        error = OAuthCallbackHandler.error or "unknown"
        description = OAuthCallbackHandler.error_description or "An error occurred"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Authentication Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            max-width: 400px;
        }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ color: #ef4444; margin: 0 0 10px 0; font-size: 24px; }}
        p {{ color: #666; margin: 0; }}
        .error {{ margin-top: 15px; padding: 10px; background: #fef2f2; border-radius: 6px; }}
        .error code {{ color: #dc2626; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">❌</div>
        <h1>Authentication Failed</h1>
        <p>Unable to complete the authentication process.</p>
        <div class="error">
            <code>{error}: {description}</code>
        </div>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode())

    @classmethod
    def reset(cls) -> None:
        """Reset handler state for new OAuth flow."""
        cls.authorization_code = None
        cls.error = None
        cls.error_description = None
        cls.received_state = None
        cls.callback_received = threading.Event()


class OAuthCallbackServer:
    """Local HTTP server to receive OAuth callback.

    Starts on a random available port and waits for the OAuth callback.
    This acts as a local OAuth proxy, handling the browser redirect flow.
    """

    def __init__(self, timeout: int = 300):
        """Initialize callback server.

        Args:
            timeout: Maximum seconds to wait for callback (default: 5 minutes)
        """
        self.timeout = timeout
        self.server: Optional[socketserver.TCPServer] = None
        self.port: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    def start(self) -> int:
        """Start the callback server on a random port.

        Returns:
            The port number the server is listening on
        """
        OAuthCallbackHandler.reset()
        self._shutdown_event.clear()

        # Find an available port - use SO_REUSEADDR to prevent "address in use" errors
        self.server = socketserver.TCPServer(("127.0.0.1", 0), OAuthCallbackHandler)
        self.server.socket.setsockopt(
            __import__("socket").SOL_SOCKET,
            __import__("socket").SO_REUSEADDR,
            1,
        )
        self.port = self.server.server_address[1]

        # Set a socket timeout so handle_request doesn't block forever
        self.server.socket.settimeout(1.0)

        # Start server in background thread
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

        return self.port

    def _serve(self) -> None:
        """Serve requests until callback received or shutdown."""
        if not self.server:
            return

        # Poll for requests with timeout, checking shutdown event
        while not self._shutdown_event.is_set():
            try:
                self.server.handle_request()
                # If we received the callback, we're done
                if OAuthCallbackHandler.callback_received.is_set():
                    break
            except Exception:
                # Socket timeout or other error - check if we should continue
                if self._shutdown_event.is_set():
                    break

    def wait_for_callback(self, expected_state: str) -> str:
        """Wait for OAuth callback and return authorization code.

        Args:
            expected_state: The state parameter to verify

        Returns:
            The authorization code

        Raises:
            OAuthTimeoutError: If callback not received within timeout
            OAuthCancelledError: If user denied access
            OAuthError: If callback contains an error or state mismatch
        """
        # Wait for callback with timeout
        received = OAuthCallbackHandler.callback_received.wait(timeout=self.timeout)

        if not received:
            raise OAuthTimeoutError(
                f"OAuth callback not received within {self.timeout} seconds. "
                "Please try again."
            )

        # Check for errors
        if OAuthCallbackHandler.error:
            if OAuthCallbackHandler.error == "access_denied":
                raise OAuthCancelledError("Authorization was denied by the user.")
            raise OAuthError(
                f"OAuth error: {OAuthCallbackHandler.error} - "
                f"{OAuthCallbackHandler.error_description}"
            )

        # Verify state
        if OAuthCallbackHandler.received_state != expected_state:
            raise OAuthError("State mismatch - possible CSRF attack. Please try again.")

        if not OAuthCallbackHandler.authorization_code:
            raise OAuthError("No authorization code received.")

        return OAuthCallbackHandler.authorization_code

    def stop(self) -> None:
        """Stop the callback server."""
        self._shutdown_event.set()
        if self.server:
            try:
                self.server.server_close()
            except Exception:
                pass
            self.server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @property
    def redirect_uri(self) -> str:
        """Get the redirect URI for this server."""
        if self.port is None:
            raise OAuthError("Server not started")
        return f"http://localhost:{self.port}/callback"


class TokenStorage:
    """Secure storage for OAuth tokens.

    Uses the system keyring when available, falls back to file-based storage.
    Tokens are stored per-service in the user's home directory.
    """

    SERVICE_PREFIX = "context-harness"
    TOKEN_DIR = ".context-harness/tokens"

    def __init__(self, use_keyring: bool = True):
        """Initialize token storage.

        Args:
            use_keyring: Whether to attempt using system keyring
        """
        self._keyring_available = False
        self._keyring = None

        if use_keyring:
            try:
                import keyring

                self._keyring = keyring
                # Test if keyring is functional
                self._keyring.get_password(self.SERVICE_PREFIX, "__test__")
                self._keyring_available = True
            except Exception:
                # Keyring not available or not functional
                self._keyring_available = False

    def _get_token_path(self, service: str) -> Path:
        """Get path for file-based token storage."""
        token_dir = Path.home() / self.TOKEN_DIR
        token_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions on token directory
        token_dir.chmod(0o700)
        return token_dir / f"{service}.json"

    def save_tokens(self, service: str, tokens: OAuthTokens) -> None:
        """Save tokens for a service.

        Args:
            service: Service name (e.g., "atlassian")
            tokens: OAuth tokens to save
        """
        token_data = json.dumps(tokens.to_dict())

        if self._keyring_available and self._keyring:
            try:
                self._keyring.set_password(
                    f"{self.SERVICE_PREFIX}-{service}", "oauth_tokens", token_data
                )
                return
            except Exception:
                # Fall back to file storage
                pass

        # File-based storage
        token_path = self._get_token_path(service)
        token_path.write_text(token_data)
        token_path.chmod(0o600)  # Restrictive permissions

    def load_tokens(self, service: str) -> Optional[OAuthTokens]:
        """Load tokens for a service.

        Args:
            service: Service name (e.g., "atlassian")

        Returns:
            OAuthTokens if found, None otherwise
        """
        token_data: Optional[str] = None

        if self._keyring_available and self._keyring:
            try:
                token_data = self._keyring.get_password(
                    f"{self.SERVICE_PREFIX}-{service}", "oauth_tokens"
                )
            except Exception:
                pass

        if not token_data:
            # Try file-based storage
            token_path = self._get_token_path(service)
            if token_path.exists():
                try:
                    token_data = token_path.read_text()
                except Exception:
                    return None

        if token_data:
            try:
                return OAuthTokens.from_dict(json.loads(token_data))
            except (json.JSONDecodeError, KeyError):
                return None

        return None

    def delete_tokens(self, service: str) -> bool:
        """Delete tokens for a service.

        Args:
            service: Service name (e.g., "atlassian")

        Returns:
            True if tokens were deleted, False if not found
        """
        deleted = False

        if self._keyring_available and self._keyring:
            try:
                self._keyring.delete_password(
                    f"{self.SERVICE_PREFIX}-{service}", "oauth_tokens"
                )
                deleted = True
            except Exception:
                pass

        # Also try to delete file
        token_path = self._get_token_path(service)
        if token_path.exists():
            token_path.unlink()
            deleted = True

        return deleted

    def get_auth_status(self, service: str) -> AuthStatus:
        """Check authentication status for a service.

        Args:
            service: Service name (e.g., "atlassian")

        Returns:
            AuthStatus indicating current state
        """
        tokens = self.load_tokens(service)
        if tokens is None:
            return AuthStatus.NOT_AUTHENTICATED
        if tokens.is_expired():
            return AuthStatus.TOKEN_EXPIRED
        return AuthStatus.AUTHENTICATED


@dataclass
class OAuthConfig:
    """Generic OAuth configuration for any MCP server.

    This dataclass can represent OAuth configuration for any provider.
    Provider-specific configurations (like Atlassian) can be created
    using factory methods or by passing values directly.
    """

    # Required fields
    service_name: str  # e.g., "atlassian", "github", "slack"
    client_id: str
    auth_url: str  # Authorization endpoint
    token_url: str  # Token endpoint

    # Optional fields with sensible defaults
    client_secret: Optional[str] = None  # Optional for public clients
    scopes: List[str] = field(default_factory=list)
    audience: Optional[str] = None  # Some providers require this
    resources_url: Optional[str] = None  # URL to fetch accessible resources
    extra_auth_params: Dict[str, str] = field(
        default_factory=dict
    )  # Provider-specific params

    # Display information
    display_name: Optional[str] = None  # Human-readable name for UI
    setup_url: Optional[str] = None  # URL where users create OAuth apps


# Pre-defined OAuth configurations for known providers
OAUTH_PROVIDERS: Dict[str, "OAuthConfig"] = {}


def register_oauth_provider(config: OAuthConfig) -> None:
    """Register an OAuth provider configuration.

    Args:
        config: The OAuth configuration to register
    """
    OAUTH_PROVIDERS[config.service_name] = config


def get_oauth_config(
    service_name: str, client_id: str, client_secret: Optional[str] = None
) -> OAuthConfig:
    """Get OAuth configuration for a service, with client credentials.

    Args:
        service_name: Name of the service (e.g., "atlassian")
        client_id: OAuth client ID
        client_secret: OAuth client secret (optional for public clients)

    Returns:
        OAuthConfig with client credentials populated

    Raises:
        OAuthError: If service is not a registered OAuth provider
    """
    if service_name not in OAUTH_PROVIDERS:
        raise OAuthError(f"Unknown OAuth provider: {service_name}")

    # Create a copy with the client credentials
    base = OAUTH_PROVIDERS[service_name]
    return OAuthConfig(
        service_name=base.service_name,
        client_id=client_id,
        client_secret=client_secret,
        auth_url=base.auth_url,
        token_url=base.token_url,
        scopes=base.scopes.copy(),
        audience=base.audience,
        resources_url=base.resources_url,
        extra_auth_params=base.extra_auth_params.copy(),
        display_name=base.display_name,
        setup_url=base.setup_url,
    )


# Register Atlassian as a known provider
register_oauth_provider(
    OAuthConfig(
        service_name="atlassian",
        client_id="",  # Will be overwritten when getting config
        auth_url="https://auth.atlassian.com/authorize",
        token_url="https://auth.atlassian.com/oauth/token",
        scopes=[
            "read:jira-work",
            "read:jira-user",
            "read:confluence-content.all",
            "read:confluence-space.summary",
            "offline_access",  # Required for refresh tokens
        ],
        audience="api.atlassian.com",
        resources_url="https://api.atlassian.com/oauth/token/accessible-resources",
        display_name="Atlassian",
        setup_url="https://developer.atlassian.com/console/myapps/",
    )
)


@dataclass
class AtlassianOAuthConfig:
    """Configuration for Atlassian OAuth flow.

    DEPRECATED: Use OAuthConfig with service_name="atlassian" instead.
    Kept for backward compatibility.
    """

    client_id: str
    client_secret: Optional[str] = None  # Optional for public clients
    scopes: List[str] = field(
        default_factory=lambda: [
            "read:jira-work",
            "read:jira-user",
            "read:confluence-content.all",
            "read:confluence-space.summary",
            "offline_access",  # Required for refresh tokens
        ]
    )
    auth_url: str = "https://auth.atlassian.com/authorize"
    token_url: str = "https://auth.atlassian.com/oauth/token"
    resources_url: str = "https://api.atlassian.com/oauth/token/accessible-resources"
    audience: str = "api.atlassian.com"

    def to_generic(self) -> OAuthConfig:
        """Convert to generic OAuthConfig."""
        return OAuthConfig(
            service_name="atlassian",
            client_id=self.client_id,
            client_secret=self.client_secret,
            auth_url=self.auth_url,
            token_url=self.token_url,
            scopes=self.scopes.copy(),
            audience=self.audience,
            resources_url=self.resources_url,
            display_name="Atlassian",
            setup_url="https://developer.atlassian.com/console/myapps/",
        )


class AtlassianOAuthFlow:
    """OAuth 2.1 flow for Atlassian services (Jira, Confluence, Compass).

    Implements the full OAuth 2.1 authorization code flow with PKCE.
    """

    def __init__(
        self,
        config: AtlassianOAuthConfig,
        token_storage: Optional[TokenStorage] = None,
        callback_timeout: int = 300,
    ):
        """Initialize Atlassian OAuth flow.

        Args:
            config: OAuth configuration
            token_storage: Token storage instance (creates default if None)
            callback_timeout: Timeout for OAuth callback in seconds
        """
        self.config = config
        self.storage = token_storage or TokenStorage()
        self.callback_timeout = callback_timeout
        self._pkce: Optional[PKCEChallenge] = None
        self._state: Optional[str] = None

    def get_auth_status(self) -> AuthStatus:
        """Check current authentication status.

        Returns:
            AuthStatus for Atlassian service
        """
        return self.storage.get_auth_status("atlassian")

    def get_tokens(self) -> Optional[OAuthTokens]:
        """Get current tokens if authenticated.

        Returns:
            OAuthTokens if authenticated, None otherwise
        """
        return self.storage.load_tokens("atlassian")

    def build_authorization_url(self, redirect_uri: str) -> str:
        """Build the authorization URL for browser redirect.

        Args:
            redirect_uri: The callback URI

        Returns:
            Full authorization URL
        """
        # Generate PKCE challenge
        self._pkce = generate_pkce()
        self._state = generate_state()

        params = {
            "audience": self.config.audience,
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
            "redirect_uri": redirect_uri,
            "state": self._state,
            "response_type": "code",
            "prompt": "consent",
            "code_challenge": self._pkce.code_challenge,
            "code_challenge_method": self._pkce.code_challenge_method,
        }

        return f"{self.config.auth_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> OAuthTokens:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            redirect_uri: The same redirect URI used in authorization

        Returns:
            OAuthTokens from the token exchange

        Raises:
            OAuthError: If token exchange fails
        """
        if self._pkce is None:
            raise OAuthError(
                "PKCE not initialized - call build_authorization_url first"
            )

        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._pkce.code_verifier,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        return self._request_tokens(data)

    def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            New OAuthTokens

        Raises:
            OAuthError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "refresh_token": refresh_token,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        return self._request_tokens(data)

    def _request_tokens(self, data: Dict[str, str]) -> OAuthTokens:
        """Make token request to Atlassian.

        Args:
            data: Form data for token request

        Returns:
            OAuthTokens from response

        Raises:
            OAuthError: If request fails
        """
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(
            self.config.token_url,
            data=encoded_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            tokens = OAuthTokens(
                access_token=response_data["access_token"],
                token_type=response_data.get("token_type", "Bearer"),
                expires_in=response_data.get("expires_in"),
                refresh_token=response_data.get("refresh_token"),
                scope=response_data.get("scope"),
            )

            # Save tokens
            self.storage.save_tokens("atlassian", tokens)
            return tokens

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get(
                    "error_description", error_data.get("error", str(e))
                )
            except json.JSONDecodeError:
                error_msg = error_body or str(e)
            raise OAuthError(f"Token exchange failed: {error_msg}")

        except URLError as e:
            raise OAuthError(f"Network error during token exchange: {e}")

    def get_accessible_resources(
        self, access_token: Optional[str] = None
    ) -> List[AtlassianResource]:
        """Get list of Atlassian cloud resources accessible with current token.

        Args:
            access_token: Access token (uses stored token if None)

        Returns:
            List of accessible Atlassian resources

        Raises:
            OAuthError: If request fails or not authenticated
        """
        if access_token is None:
            tokens = self.get_tokens()
            if tokens is None:
                raise OAuthError("Not authenticated")
            access_token = tokens.access_token

        request = urllib.request.Request(
            self.config.resources_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                resources_data = json.loads(response.read().decode("utf-8"))

            return [
                AtlassianResource(
                    id=r["id"],
                    url=r["url"],
                    name=r["name"],
                    scopes=r.get("scopes", []),
                    avatar_url=r.get("avatarUrl"),
                )
                for r in resources_data
            ]

        except HTTPError as e:
            if e.code == 401:
                raise OAuthError("Access token expired or invalid")
            raise OAuthError(f"Failed to get accessible resources: {e}")

        except URLError as e:
            raise OAuthError(f"Network error: {e}")

    def authenticate(
        self,
        open_browser: bool = True,
        browser_callback: Optional[Callable[[str], None]] = None,
    ) -> OAuthTokens:
        """Run the full OAuth authentication flow.

        Args:
            open_browser: Whether to automatically open the browser
            browser_callback: Optional callback with auth URL (for custom handling)

        Returns:
            OAuthTokens after successful authentication

        Raises:
            OAuthError: If authentication fails
            OAuthTimeoutError: If user doesn't complete flow in time
            OAuthCancelledError: If user cancels
        """
        # Start callback server
        server = OAuthCallbackServer(timeout=self.callback_timeout)
        port = server.start()

        try:
            # Build authorization URL
            auth_url = self.build_authorization_url(server.redirect_uri)

            console.print("\n[bold blue]🔐 Atlassian Authentication[/bold blue]\n")

            if browser_callback:
                browser_callback(auth_url)
            elif open_browser:
                console.print("Opening browser for authentication...")
                console.print(f"[dim]If browser doesn't open, visit:[/dim]")
                console.print(f"[cyan]{auth_url}[/cyan]\n")
                webbrowser.open(auth_url)
            else:
                console.print("Please visit this URL to authenticate:")
                console.print(f"[cyan]{auth_url}[/cyan]\n")

            console.print("[dim]Waiting for authentication...[/dim]")

            # Wait for callback
            code = server.wait_for_callback(self._state or "")

            console.print("[green]✓ Authorization received[/green]")

            # Exchange code for tokens
            console.print("[dim]Exchanging code for tokens...[/dim]")
            tokens = self.exchange_code_for_tokens(code, server.redirect_uri)

            console.print("[green]✓ Authentication successful![/green]\n")

            return tokens

        finally:
            server.stop()

    def logout(self) -> bool:
        """Remove stored tokens (logout).

        Returns:
            True if tokens were removed, False if not logged in
        """
        return self.storage.delete_tokens("atlassian")

    def ensure_valid_token(self) -> OAuthTokens:
        """Ensure we have a valid (non-expired) token, refreshing if needed.

        Returns:
            Valid OAuthTokens

        Raises:
            OAuthError: If not authenticated or refresh fails
        """
        tokens = self.get_tokens()
        if tokens is None:
            raise OAuthError(
                "Not authenticated. Run 'context-harness mcp auth atlassian' first."
            )

        if tokens.is_expired():
            if tokens.refresh_token:
                console.print("[dim]Access token expired, refreshing...[/dim]")
                try:
                    tokens = self.refresh_tokens(tokens.refresh_token)
                    console.print("[green]✓ Token refreshed[/green]")
                except OAuthError:
                    raise OAuthError(
                        "Token refresh failed. Please re-authenticate with "
                        "'context-harness mcp auth atlassian'"
                    )
            else:
                raise OAuthError(
                    "Access token expired and no refresh token available. "
                    "Please re-authenticate."
                )

        return tokens


# Convenience function for CLI usage
def get_atlassian_oauth_flow(client_id: Optional[str] = None) -> AtlassianOAuthFlow:
    """Get an AtlassianOAuthFlow instance.

    Args:
        client_id: Atlassian OAuth client ID (uses env var if not provided)

    Returns:
        Configured AtlassianOAuthFlow

    Raises:
        OAuthError: If client_id not provided and not in environment
    """
    if client_id is None:
        client_id = os.environ.get("ATLASSIAN_CLIENT_ID")

    if not client_id:
        raise OAuthError(
            "Atlassian client ID not configured. "
            "Set ATLASSIAN_CLIENT_ID environment variable or provide --client-id."
        )

    client_secret = os.environ.get("ATLASSIAN_CLIENT_SECRET")

    config = AtlassianOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
    )

    return AtlassianOAuthFlow(config)


# =============================================================================
# Generic MCP OAuth Flow
# =============================================================================


class MCPOAuthFlow:
    """Generic OAuth 2.1 flow for any MCP server.

    This is a provider-agnostic OAuth flow that works with any MCP server
    that requires OAuth authentication. It uses OAuthConfig to configure
    the flow for the specific provider.

    Usage:
        # Get config for a known provider
        config = get_oauth_config("atlassian", client_id="...")

        # Or create custom config
        config = OAuthConfig(
            service_name="my-service",
            client_id="...",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes=["read", "write"],
        )

        # Create flow and authenticate
        flow = MCPOAuthFlow(config)
        tokens = flow.authenticate()
    """

    def __init__(
        self,
        config: OAuthConfig,
        token_storage: Optional[TokenStorage] = None,
        callback_timeout: int = 300,
    ):
        """Initialize MCP OAuth flow.

        Args:
            config: OAuth configuration for the provider
            token_storage: Token storage instance (creates default if None)
            callback_timeout: Timeout for OAuth callback in seconds
        """
        self.config = config
        self.storage = token_storage or TokenStorage()
        self.callback_timeout = callback_timeout
        self._pkce: Optional[PKCEChallenge] = None
        self._state: Optional[str] = None

    @property
    def service_name(self) -> str:
        """Get the service name for this flow."""
        return self.config.service_name

    def get_auth_status(self) -> AuthStatus:
        """Check current authentication status.

        Returns:
            AuthStatus for this service
        """
        return self.storage.get_auth_status(self.service_name)

    def get_tokens(self) -> Optional[OAuthTokens]:
        """Get current tokens if authenticated.

        Returns:
            OAuthTokens if authenticated, None otherwise
        """
        return self.storage.load_tokens(self.service_name)

    def build_authorization_url(self, redirect_uri: str) -> str:
        """Build the authorization URL for browser redirect.

        Args:
            redirect_uri: The callback URI

        Returns:
            Full authorization URL
        """
        # Generate PKCE challenge
        self._pkce = generate_pkce()
        self._state = generate_state()

        params = {
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
            "redirect_uri": redirect_uri,
            "state": self._state,
            "response_type": "code",
            "code_challenge": self._pkce.code_challenge,
            "code_challenge_method": self._pkce.code_challenge_method,
        }

        # Add audience if configured (required by some providers like Atlassian)
        if self.config.audience:
            params["audience"] = self.config.audience

        # Add any extra provider-specific params
        params.update(self.config.extra_auth_params)

        return f"{self.config.auth_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> OAuthTokens:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            redirect_uri: The same redirect URI used in authorization

        Returns:
            OAuthTokens from the token exchange

        Raises:
            OAuthError: If token exchange fails
        """
        if self._pkce is None:
            raise OAuthError(
                "PKCE not initialized - call build_authorization_url first"
            )

        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._pkce.code_verifier,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        return self._request_tokens(data)

    def refresh_tokens(self, refresh_token: str) -> OAuthTokens:
        """Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            New OAuthTokens

        Raises:
            OAuthError: If refresh fails
        """
        data = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "refresh_token": refresh_token,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        return self._request_tokens(data)

    def _request_tokens(self, data: Dict[str, str]) -> OAuthTokens:
        """Make token request to OAuth provider.

        Args:
            data: Form data for token request

        Returns:
            OAuthTokens from response

        Raises:
            OAuthError: If request fails
        """
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(
            self.config.token_url,
            data=encoded_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            tokens = OAuthTokens(
                access_token=response_data["access_token"],
                token_type=response_data.get("token_type", "Bearer"),
                expires_in=response_data.get("expires_in"),
                refresh_token=response_data.get("refresh_token"),
                scope=response_data.get("scope"),
            )

            # Save tokens
            self.storage.save_tokens(self.service_name, tokens)
            return tokens

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get(
                    "error_description", error_data.get("error", str(e))
                )
            except json.JSONDecodeError:
                error_msg = error_body or str(e)
            raise OAuthError(f"Token exchange failed: {error_msg}")

        except URLError as e:
            raise OAuthError(f"Network error during token exchange: {e}")

    def authenticate(
        self,
        open_browser: bool = True,
        browser_callback: Optional[Callable[[str], None]] = None,
    ) -> OAuthTokens:
        """Run the full OAuth authentication flow.

        Args:
            open_browser: Whether to automatically open the browser
            browser_callback: Optional callback with auth URL (for custom handling)

        Returns:
            OAuthTokens after successful authentication

        Raises:
            OAuthError: If authentication fails
            OAuthTimeoutError: If user doesn't complete flow in time
            OAuthCancelledError: If user cancels
        """
        # Start callback server
        server = OAuthCallbackServer(timeout=self.callback_timeout)
        port = server.start()

        try:
            # Build authorization URL
            auth_url = self.build_authorization_url(server.redirect_uri)

            display_name = self.config.display_name or self.service_name.title()
            console.print(
                f"\n[bold blue]🔐 {display_name} Authentication[/bold blue]\n"
            )

            if browser_callback:
                browser_callback(auth_url)
            elif open_browser:
                console.print("Opening browser for authentication...")
                console.print(f"[dim]If browser doesn't open, visit:[/dim]")
                console.print(f"[cyan]{auth_url}[/cyan]\n")
                webbrowser.open(auth_url)
            else:
                console.print("Please visit this URL to authenticate:")
                console.print(f"[cyan]{auth_url}[/cyan]\n")

            console.print("[dim]Waiting for authentication...[/dim]")

            # Wait for callback
            code = server.wait_for_callback(self._state or "")

            console.print("[green]✓ Authorization received[/green]")

            # Exchange code for tokens
            console.print("[dim]Exchanging code for tokens...[/dim]")
            tokens = self.exchange_code_for_tokens(code, server.redirect_uri)

            console.print("[green]✓ Authentication successful![/green]\n")

            return tokens

        finally:
            server.stop()

    def logout(self) -> bool:
        """Remove stored tokens (logout).

        Returns:
            True if tokens were removed, False if not logged in
        """
        return self.storage.delete_tokens(self.service_name)

    def ensure_valid_token(self) -> OAuthTokens:
        """Ensure we have a valid (non-expired) token, refreshing if needed.

        Returns:
            Valid OAuthTokens

        Raises:
            OAuthError: If not authenticated or refresh fails
        """
        tokens = self.get_tokens()
        if tokens is None:
            raise OAuthError(
                f"Not authenticated. Run 'context-harness mcp auth {self.service_name}' first."
            )

        if tokens.is_expired():
            if tokens.refresh_token:
                console.print("[dim]Access token expired, refreshing...[/dim]")
                try:
                    tokens = self.refresh_tokens(tokens.refresh_token)
                    console.print("[green]✓ Token refreshed[/green]")
                except OAuthError:
                    raise OAuthError(
                        f"Token refresh failed. Please re-authenticate with "
                        f"'context-harness mcp auth {self.service_name}'"
                    )
            else:
                raise OAuthError(
                    "Access token expired and no refresh token available. "
                    "Please re-authenticate."
                )

        return tokens


def get_oauth_flow(
    service_name: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> MCPOAuthFlow:
    """Get an OAuth flow instance for a service.

    This is the main entry point for OAuth authentication. It will:
    1. Look up the service in registered OAuth providers
    2. Get client credentials from environment if not provided
    3. Return a configured MCPOAuthFlow instance

    Args:
        service_name: Name of the service (e.g., "atlassian")
        client_id: OAuth client ID (uses env var if not provided)
        client_secret: OAuth client secret (uses env var if not provided)

    Returns:
        Configured MCPOAuthFlow instance

    Raises:
        OAuthError: If service not found or credentials missing
    """
    if service_name not in OAUTH_PROVIDERS:
        raise OAuthError(
            f"Unknown OAuth provider: {service_name}. "
            f"Available providers: {', '.join(OAUTH_PROVIDERS.keys())}"
        )

    # Get client ID from environment if not provided
    if client_id is None:
        env_var = f"{service_name.upper()}_CLIENT_ID"
        client_id = os.environ.get(env_var)
        if not client_id:
            base_config = OAUTH_PROVIDERS[service_name]
            setup_info = ""
            if base_config.setup_url:
                setup_info = f"\nCreate an OAuth app at: {base_config.setup_url}"
            raise OAuthError(
                f"{service_name.title()} client ID not configured. "
                f"Set {env_var} environment variable or provide --client-id.{setup_info}"
            )

    # Get client secret from environment if not provided
    if client_secret is None:
        env_var = f"{service_name.upper()}_CLIENT_SECRET"
        client_secret = os.environ.get(env_var)

    # Get config with credentials
    config = get_oauth_config(service_name, client_id, client_secret)

    return MCPOAuthFlow(config)


# =============================================================================
# MCP OAuth Discovery
# =============================================================================


@dataclass
class MCPOAuthMetadata:
    """OAuth metadata discovered from an MCP server.

    Per MCP specification, servers return OAuth requirements via:
    - 401 response with WWW-Authenticate header
    - /.well-known/oauth-protected-resource endpoint
    """

    authorization_endpoint: str
    token_endpoint: str
    scopes_supported: List[str] = field(default_factory=list)
    resource_server: Optional[str] = None
    issuer: Optional[str] = None


def parse_www_authenticate(header: str) -> Dict[str, str]:
    """Parse WWW-Authenticate header to extract OAuth parameters.

    Per RFC 6750 and MCP spec, the header may contain:
    - Bearer realm="..."
    - Bearer resource_metadata="..."

    Args:
        header: The WWW-Authenticate header value

    Returns:
        Dict of parsed parameters
    """
    params = {}

    # Handle "Bearer ..." format
    if header.lower().startswith("bearer "):
        header = header[7:]

    # Parse key="value" pairs
    import re

    pattern = r'(\w+)="([^"]*)"'
    for match in re.finditer(pattern, header):
        params[match.group(1)] = match.group(2)

    return params


def discover_mcp_oauth(mcp_url: str, timeout: int = 30) -> Optional[MCPOAuthMetadata]:
    """Discover OAuth requirements for an MCP server.

    Follows the MCP specification for OAuth discovery:
    1. Connect to MCP endpoint
    2. If 401, parse WWW-Authenticate header
    3. Fetch protected resource metadata
    4. Return OAuth endpoints

    Args:
        mcp_url: The MCP server URL (e.g., https://mcp.atlassian.com/v1/mcp)
        timeout: Request timeout in seconds

    Returns:
        MCPOAuthMetadata if OAuth is required, None if not
    """
    try:
        # Try to connect to the MCP endpoint
        request = urllib.request.Request(
            mcp_url,
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-03-26",
            },
        )

        try:
            urllib.request.urlopen(request, timeout=timeout)
            # If we get here without error, no OAuth required
            return None
        except HTTPError as e:
            if e.code != 401:
                # Not an auth error
                return None

            # Parse WWW-Authenticate header
            www_auth = e.headers.get("WWW-Authenticate", "")
            params = parse_www_authenticate(www_auth)

            # Check for resource_metadata URL
            resource_metadata_url = params.get("resource_metadata")

            if resource_metadata_url:
                # Fetch protected resource metadata
                return _fetch_resource_metadata(resource_metadata_url, timeout)

            # Fallback: try well-known endpoint
            base_url = _get_base_url(mcp_url)
            well_known_url = f"{base_url}/.well-known/oauth-protected-resource"

            try:
                return _fetch_resource_metadata(well_known_url, timeout)
            except Exception:
                pass

            # Last resort: try authorization server metadata
            well_known_oauth = f"{base_url}/.well-known/oauth-authorization-server"
            try:
                return _fetch_auth_server_metadata(well_known_oauth, timeout)
            except Exception:
                pass

            return None

    except URLError:
        return None


def _get_base_url(url: str) -> str:
    """Extract base URL (scheme + host) from a URL."""
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _fetch_resource_metadata(url: str, timeout: int) -> Optional[MCPOAuthMetadata]:
    """Fetch OAuth Protected Resource Metadata (RFC 9728)."""
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))

    # Get authorization server URL
    auth_servers = data.get("authorization_servers", [])
    if not auth_servers:
        return None

    # Fetch auth server metadata
    return _fetch_auth_server_metadata(auth_servers[0], timeout)


def _fetch_auth_server_metadata(url: str, timeout: int) -> Optional[MCPOAuthMetadata]:
    """Fetch OAuth Authorization Server Metadata (RFC 8414)."""
    # Ensure we're fetching the well-known endpoint
    if "/.well-known/" not in url:
        parsed = urllib.parse.urlparse(url)
        url = (
            f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server"
        )

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))

    return MCPOAuthMetadata(
        authorization_endpoint=data.get("authorization_endpoint", ""),
        token_endpoint=data.get("token_endpoint", ""),
        scopes_supported=data.get("scopes_supported", []),
        issuer=data.get("issuer"),
    )


def check_mcp_auth_required(mcp_url: str, timeout: int = 10) -> bool:
    """Quick check if an MCP server requires authentication.

    Args:
        mcp_url: The MCP server URL
        timeout: Request timeout in seconds

    Returns:
        True if authentication is required (401 response), False otherwise
    """
    try:
        request = urllib.request.Request(
            mcp_url,
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-03-26",
            },
        )
        urllib.request.urlopen(request, timeout=timeout)
        return False
    except HTTPError as e:
        return e.code == 401
    except URLError:
        return False


def get_mcp_bearer_token(service: str) -> Optional[str]:
    """Get stored bearer token for an MCP service.

    This is a convenience function for MCP clients to get the stored
    OAuth token for authenticated requests.

    Args:
        service: Service name (e.g., "atlassian")

    Returns:
        Bearer token string if authenticated, None otherwise
    """
    storage = TokenStorage()
    tokens = storage.load_tokens(service)
    if tokens is None:
        return None
    if tokens.is_expired():
        return None
    return tokens.access_token
