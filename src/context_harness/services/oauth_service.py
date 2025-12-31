"""OAuth service for ContextHarness.

Handles OAuth authentication flows for MCP servers.
Business logic extracted from oauth.py module.

This service provides a clean interface for OAuth operations without
coupling to CLI frameworks (Rich, Click). It returns Result types
and lets interfaces handle presentation.
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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol
from urllib.error import HTTPError, URLError

from context_harness.primitives import (
    AuthStatus,
    ErrorCode,
    Failure,
    OAuthConfig,
    OAuthProvider,
    OAuthTokens,
    PKCEChallenge,
    Result,
    Success,
)


class TokenStorageProtocol(Protocol):
    """Protocol for OAuth token storage backends.

    Allows for dependency injection and testing with different
    storage implementations (file, keyring, memory, etc.).
    """

    def save_tokens(self, service: str, tokens: OAuthTokens) -> None:
        """Save tokens for a service."""
        ...

    def load_tokens(self, service: str) -> Optional[OAuthTokens]:
        """Load tokens for a service."""
        ...

    def delete_tokens(self, service: str) -> bool:
        """Delete tokens for a service."""
        ...


class FileTokenStorage:
    """File-based token storage with optional keyring support.

    Stores OAuth tokens in ~/.context-harness/tokens/.
    Uses system keyring when available for additional security.
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
                # Keyring access failed; fall back to file-based storage
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
                data = json.loads(token_data)
                return OAuthTokens(
                    access_token=data["access_token"],
                    token_type=data.get("token_type", "Bearer"),
                    expires_in=data.get("expires_in"),
                    refresh_token=data.get("refresh_token"),
                    scope=data.get("scope"),
                    issued_at=data.get("issued_at", time.time()),
                )
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
                # Keyring deletion failed; continue with file-based cleanup
                pass

        # Also try to delete file
        token_path = self._get_token_path(service)
        if token_path.exists():
            token_path.unlink()
            deleted = True

        return deleted


class MemoryTokenStorage:
    """In-memory token storage for testing."""

    def __init__(self) -> None:
        self._tokens: Dict[str, OAuthTokens] = {}

    def save_tokens(self, service: str, tokens: OAuthTokens) -> None:
        self._tokens[service] = tokens

    def load_tokens(self, service: str) -> Optional[OAuthTokens]:
        return self._tokens.get(service)

    def delete_tokens(self, service: str) -> bool:
        if service in self._tokens:
            del self._tokens[service]
            return True
        return False


# Pre-defined OAuth provider configurations
OAUTH_PROVIDERS: Dict[str, OAuthConfig] = {
    "atlassian": OAuthConfig(
        service_name="atlassian",
        client_id="",  # Will be set from env or parameter
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
    ),
}


def _generate_pkce() -> PKCEChallenge:
    """Generate a PKCE code verifier and challenge.

    Uses SHA-256 (S256) method as required by OAuth 2.1.

    Returns:
        PKCEChallenge with verifier and challenge
    """
    random_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii")

    verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode("ascii")
    )

    return PKCEChallenge(
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


def _generate_state() -> str:
    """Generate a random state parameter for CSRF protection."""
    return secrets.token_hex(16)


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

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

        _OAuthCallbackHandler.received_state = params.get("state", [None])[0]

        if "error" in params:
            _OAuthCallbackHandler.error = params.get("error", ["unknown"])[0]
            _OAuthCallbackHandler.error_description = params.get(
                "error_description", [""]
            )[0]
            self._send_error_response()
        elif "code" in params:
            _OAuthCallbackHandler.authorization_code = params["code"][0]
            self._send_success_response()
        else:
            _OAuthCallbackHandler.error = "missing_code"
            _OAuthCallbackHandler.error_description = "No authorization code received"
            self._send_error_response()

        _OAuthCallbackHandler.callback_received.set()

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

        error = _OAuthCallbackHandler.error or "unknown"
        description = _OAuthCallbackHandler.error_description or "An error occurred"

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


class OAuthService:
    """Service for OAuth authentication flows.

    Handles:
    - OAuth 2.1 authorization code flow with PKCE
    - Token storage and retrieval
    - Token refresh
    - Authentication status checking

    This service is provider-agnostic and works with any OAuth provider
    configured in OAUTH_PROVIDERS.

    Example:
        service = OAuthService()

        # Check status
        result = service.get_status("atlassian")

        # Authenticate
        result = service.authenticate("atlassian", client_id="...")
        if isinstance(result, Success):
            tokens = result.value
            print(f"Access token: {tokens.access_token}")

        # Get bearer token for API requests
        result = service.get_bearer_token("atlassian")
    """

    PREFERRED_PORTS = [8080, 3000, 57548]

    def __init__(
        self,
        token_storage: Optional[TokenStorageProtocol] = None,
        callback_timeout: int = 300,
    ):
        """Initialize the OAuth service.

        Args:
            token_storage: Token storage backend (uses FileTokenStorage if None)
            callback_timeout: Timeout for OAuth callback in seconds
        """
        self.storage = token_storage or FileTokenStorage()
        self.callback_timeout = callback_timeout
        self._pkce: Optional[PKCEChallenge] = None
        self._state: Optional[str] = None

    def list_providers(self) -> Result[List[OAuthProvider]]:
        """List available OAuth providers.

        Returns:
            Result containing list of OAuthProvider objects
        """
        providers = []
        for name, config in OAUTH_PROVIDERS.items():
            provider = OAuthProvider(
                service_name=name,
                auth_url=config.auth_url,
                token_url=config.token_url,
                scopes=config.scopes,
                audience=config.audience,
                resources_url=config.resources_url,
                display_name=config.display_name or name.title(),
                setup_url=config.setup_url,
            )
            providers.append(provider)

        return Success(value=providers)

    def get_status(self, service_name: str) -> Result[AuthStatus]:
        """Get authentication status for a service.

        Args:
            service_name: Name of the OAuth service (e.g., "atlassian")

        Returns:
            Result containing AuthStatus
        """
        if service_name not in OAUTH_PROVIDERS:
            return Failure(
                error=f"Unknown OAuth provider: {service_name}",
                code=ErrorCode.NOT_FOUND,
                details={
                    "service_name": service_name,
                    "available": list(OAUTH_PROVIDERS.keys()),
                },
            )

        tokens = self.storage.load_tokens(service_name)
        if tokens is None:
            return Success(value=AuthStatus.NOT_AUTHENTICATED)

        if tokens.is_expired():
            return Success(value=AuthStatus.TOKEN_EXPIRED)

        return Success(value=AuthStatus.AUTHENTICATED)

    def get_tokens(self, service_name: str) -> Result[OAuthTokens]:
        """Get stored tokens for a service.

        Args:
            service_name: Name of the OAuth service

        Returns:
            Result containing OAuthTokens or Failure if not authenticated
        """
        tokens = self.storage.load_tokens(service_name)
        if tokens is None:
            return Failure(
                error=f"Not authenticated with {service_name}",
                code=ErrorCode.AUTH_REQUIRED,
                details={"service_name": service_name},
            )

        return Success(value=tokens)

    def get_bearer_token(self, service_name: str) -> Result[str]:
        """Get a valid bearer token for API requests.

        This is a convenience method for getting just the access token.
        Returns Failure if not authenticated or token is expired.

        Args:
            service_name: Name of the OAuth service

        Returns:
            Result containing bearer token string
        """
        tokens = self.storage.load_tokens(service_name)
        if tokens is None:
            return Failure(
                error=f"Not authenticated with {service_name}",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if tokens.is_expired():
            return Failure(
                error=f"Token expired for {service_name}",
                code=ErrorCode.TOKEN_EXPIRED,
            )

        return Success(value=tokens.access_token)

    def authenticate(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        open_browser: bool = True,
        browser_callback: Optional[Callable[[str], None]] = None,
    ) -> Result[OAuthTokens]:
        """Run the full OAuth authentication flow.

        Args:
            service_name: Name of the OAuth service (e.g., "atlassian")
            client_id: OAuth client ID (uses env var if not provided)
            client_secret: OAuth client secret (optional)
            open_browser: Whether to automatically open the browser
            browser_callback: Optional callback with auth URL (for custom handling)

        Returns:
            Result containing OAuthTokens after successful authentication
        """
        # Get provider config
        if service_name not in OAUTH_PROVIDERS:
            return Failure(
                error=f"Unknown OAuth provider: {service_name}",
                code=ErrorCode.NOT_FOUND,
                details={"available": list(OAUTH_PROVIDERS.keys())},
            )

        base_config = OAUTH_PROVIDERS[service_name]

        # Get client ID from environment if not provided
        if client_id is None:
            env_var = f"{service_name.upper()}_CLIENT_ID"
            client_id = os.environ.get(env_var)
            if not client_id:
                setup_info = ""
                if base_config.setup_url:
                    setup_info = f" Create an OAuth app at: {base_config.setup_url}"
                return Failure(
                    error=f"{service_name.title()} client ID not configured. "
                    f"Set {env_var} environment variable or provide client_id.{setup_info}",
                    code=ErrorCode.CONFIG_MISSING,
                )

        # Get client secret from environment if not provided
        if client_secret is None:
            env_var = f"{service_name.upper()}_CLIENT_SECRET"
            client_secret = os.environ.get(env_var)

        # Create config with credentials
        config = OAuthConfig(
            service_name=base_config.service_name,
            client_id=client_id,
            client_secret=client_secret,
            auth_url=base_config.auth_url,
            token_url=base_config.token_url,
            scopes=base_config.scopes,
            audience=base_config.audience,
            resources_url=base_config.resources_url,
            display_name=base_config.display_name,
            setup_url=base_config.setup_url,
        )

        # Start callback server
        server, port = self._start_callback_server()
        redirect_uri = f"http://localhost:{port}/callback"

        try:
            # Build authorization URL
            auth_url = self._build_authorization_url(config, redirect_uri)

            if browser_callback:
                browser_callback(auth_url)
            elif open_browser:
                webbrowser.open(auth_url)

            # Wait for callback
            code_result = self._wait_for_callback(self._state or "")
            if isinstance(code_result, Failure):
                return code_result

            code = code_result.value

            # Exchange code for tokens
            tokens_result = self._exchange_code_for_tokens(config, code, redirect_uri)
            if isinstance(tokens_result, Failure):
                return tokens_result

            tokens = tokens_result.value

            # Save tokens
            self.storage.save_tokens(service_name, tokens)

            return Success(
                value=tokens,
                message=f"Successfully authenticated with {service_name}",
            )

        finally:
            self._stop_callback_server(server)

    def refresh_tokens(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Result[OAuthTokens]:
        """Refresh access token using stored refresh token.

        Args:
            service_name: Name of the OAuth service
            client_id: OAuth client ID (uses env var if not provided)
            client_secret: OAuth client secret (optional)

        Returns:
            Result containing new OAuthTokens
        """
        # Get current tokens
        tokens = self.storage.load_tokens(service_name)
        if tokens is None:
            return Failure(
                error=f"Not authenticated with {service_name}",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if not tokens.refresh_token:
            return Failure(
                error="No refresh token available",
                code=ErrorCode.TOKEN_EXPIRED,
            )

        # Get provider config
        if service_name not in OAUTH_PROVIDERS:
            return Failure(
                error=f"Unknown OAuth provider: {service_name}",
                code=ErrorCode.NOT_FOUND,
            )

        base_config = OAUTH_PROVIDERS[service_name]

        # Get client credentials
        if client_id is None:
            env_var = f"{service_name.upper()}_CLIENT_ID"
            client_id = os.environ.get(env_var)
            if not client_id:
                return Failure(
                    error=f"Client ID required for token refresh",
                    code=ErrorCode.CONFIG_MISSING,
                )

        if client_secret is None:
            env_var = f"{service_name.upper()}_CLIENT_SECRET"
            client_secret = os.environ.get(env_var)

        # Refresh tokens
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": tokens.refresh_token,
        }

        if client_secret:
            data["client_secret"] = client_secret

        try:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            request = urllib.request.Request(
                base_config.token_url,
                data=encoded_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            new_tokens = OAuthTokens(
                access_token=response_data["access_token"],
                token_type=response_data.get("token_type", "Bearer"),
                expires_in=response_data.get("expires_in"),
                refresh_token=response_data.get("refresh_token", tokens.refresh_token),
                scope=response_data.get("scope"),
                issued_at=time.time(),
            )

            # Save new tokens
            self.storage.save_tokens(service_name, new_tokens)

            return Success(
                value=new_tokens,
                message="Token refreshed successfully",
            )

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get(
                    "error_description", error_data.get("error", str(e))
                )
            except json.JSONDecodeError:
                error_msg = error_body or str(e)
            return Failure(
                error=f"Token refresh failed: {error_msg}",
                code=ErrorCode.TOKEN_REFRESH_FAILED,
            )

        except URLError as e:
            return Failure(
                error=f"Network error during token refresh: {e}",
                code=ErrorCode.NETWORK_ERROR,
            )

    def ensure_valid_token(
        self,
        service_name: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Result[OAuthTokens]:
        """Ensure we have a valid (non-expired) token, refreshing if needed.

        Args:
            service_name: Name of the OAuth service
            client_id: OAuth client ID for refresh (uses env var if not provided)
            client_secret: OAuth client secret (optional)

        Returns:
            Result containing valid OAuthTokens
        """
        tokens = self.storage.load_tokens(service_name)
        if tokens is None:
            return Failure(
                error=f"Not authenticated with {service_name}. "
                f"Run 'context-harness mcp auth {service_name}' first.",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if not tokens.is_expired():
            return Success(value=tokens)

        # Token expired, try to refresh
        if tokens.refresh_token:
            return self.refresh_tokens(service_name, client_id, client_secret)

        return Failure(
            error="Access token expired and no refresh token available. "
            "Please re-authenticate.",
            code=ErrorCode.TOKEN_EXPIRED,
        )

    def logout(self, service_name: str) -> Result[bool]:
        """Remove stored tokens (logout).

        Args:
            service_name: Name of the OAuth service

        Returns:
            Result containing True if tokens were removed
        """
        deleted = self.storage.delete_tokens(service_name)
        if deleted:
            return Success(
                value=True,
                message=f"Logged out from {service_name}",
            )
        return Success(
            value=False,
            message=f"No stored credentials for {service_name}",
        )

    def _start_callback_server(
        self,
    ) -> tuple[socketserver.TCPServer, int]:
        """Start the OAuth callback server."""
        _OAuthCallbackHandler.reset()

        # Try preferred ports first
        for port in self.PREFERRED_PORTS:
            try:
                server = socketserver.TCPServer(
                    ("127.0.0.1", port), _OAuthCallbackHandler
                )
                server.socket.setsockopt(
                    __import__("socket").SOL_SOCKET,
                    __import__("socket").SO_REUSEADDR,
                    1,
                )
                server.socket.settimeout(1.0)
                return server, port
            except OSError:
                continue

        # Fall back to random port
        server = socketserver.TCPServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        server.socket.setsockopt(
            __import__("socket").SOL_SOCKET,
            __import__("socket").SO_REUSEADDR,
            1,
        )
        server.socket.settimeout(1.0)
        port = server.server_address[1]
        return server, port

    def _stop_callback_server(self, server: socketserver.TCPServer) -> None:
        """Stop the callback server."""
        try:
            server.server_close()
        except Exception:
            # Best-effort shutdown: ignore errors when closing the callback server
            pass

    def _build_authorization_url(
        self,
        config: OAuthConfig,
        redirect_uri: str,
    ) -> str:
        """Build the authorization URL for browser redirect."""
        self._pkce = _generate_pkce()
        self._state = _generate_state()

        params = {
            "client_id": config.client_id,
            "scope": " ".join(config.scopes),
            "redirect_uri": redirect_uri,
            "state": self._state,
            "response_type": "code",
            "code_challenge": self._pkce.code_challenge,
            "code_challenge_method": self._pkce.code_challenge_method,
        }

        if config.audience:
            params["audience"] = config.audience

        params.update(config.extra_auth_params)

        return f"{config.auth_url}?{urllib.parse.urlencode(params)}"

    def _wait_for_callback(self, expected_state: str) -> Result[str]:
        """Wait for OAuth callback and return authorization code."""
        received = _OAuthCallbackHandler.callback_received.wait(
            timeout=self.callback_timeout
        )

        if not received:
            return Failure(
                error=f"OAuth callback not received within {self.callback_timeout} seconds",
                code=ErrorCode.TIMEOUT,
            )

        if _OAuthCallbackHandler.error:
            if _OAuthCallbackHandler.error == "access_denied":
                return Failure(
                    error="Authorization was denied by the user",
                    code=ErrorCode.AUTH_CANCELLED,
                )
            return Failure(
                error=f"OAuth error: {_OAuthCallbackHandler.error} - "
                f"{_OAuthCallbackHandler.error_description}",
                code=ErrorCode.AUTH_FAILED,
            )

        if _OAuthCallbackHandler.received_state != expected_state:
            return Failure(
                error="State mismatch - possible CSRF attack",
                code=ErrorCode.AUTH_FAILED,
            )

        if not _OAuthCallbackHandler.authorization_code:
            return Failure(
                error="No authorization code received",
                code=ErrorCode.AUTH_FAILED,
            )

        return Success(value=_OAuthCallbackHandler.authorization_code)

    def _exchange_code_for_tokens(
        self,
        config: OAuthConfig,
        code: str,
        redirect_uri: str,
    ) -> Result[OAuthTokens]:
        """Exchange authorization code for tokens."""
        if self._pkce is None:
            return Failure(
                error="PKCE not initialized",
                code=ErrorCode.UNKNOWN,
            )

        data = {
            "grant_type": "authorization_code",
            "client_id": config.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": self._pkce.code_verifier,
        }

        if config.client_secret:
            data["client_secret"] = config.client_secret

        try:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            request = urllib.request.Request(
                config.token_url,
                data=encoded_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            tokens = OAuthTokens(
                access_token=response_data["access_token"],
                token_type=response_data.get("token_type", "Bearer"),
                expires_in=response_data.get("expires_in"),
                refresh_token=response_data.get("refresh_token"),
                scope=response_data.get("scope"),
                issued_at=time.time(),
            )

            return Success(value=tokens)

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get(
                    "error_description", error_data.get("error", str(e))
                )
            except json.JSONDecodeError:
                error_msg = error_body or str(e)
            return Failure(
                error=f"Token exchange failed: {error_msg}",
                code=ErrorCode.AUTH_FAILED,
            )

        except URLError as e:
            return Failure(
                error=f"Network error during token exchange: {e}",
                code=ErrorCode.NETWORK_ERROR,
            )
