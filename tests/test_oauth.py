"""Tests for OAuth module."""

import base64
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from context_harness.oauth import (
    PKCEChallenge,
    OAuthTokens,
    AtlassianResource,
    AtlassianOAuthConfig,
    AtlassianOAuthFlow,
    OAuthCallbackHandler,
    OAuthCallbackServer,
    TokenStorage,
    AuthStatus,
    OAuthError,
    OAuthTimeoutError,
    OAuthCancelledError,
    MCPOAuthMetadata,
    # Generic OAuth classes
    OAuthConfig,
    MCPOAuthFlow,
    OAUTH_PROVIDERS,
    register_oauth_provider,
    get_oauth_config,
    get_oauth_flow,
    # Functions
    generate_pkce,
    generate_state,
    get_atlassian_oauth_flow,
    parse_www_authenticate,
    check_mcp_auth_required,
    get_mcp_bearer_token,
)


class TestGeneratePKCE:
    """Tests for PKCE generation."""

    def test_pkce_generates_verifier(self):
        """Test that PKCE generates a code verifier."""
        pkce = generate_pkce()
        assert pkce.code_verifier is not None
        assert len(pkce.code_verifier) == 43  # 32 bytes base64url encoded

    def test_pkce_generates_challenge(self):
        """Test that PKCE generates a code challenge."""
        pkce = generate_pkce()
        assert pkce.code_challenge is not None
        assert len(pkce.code_challenge) == 43  # SHA-256 base64url encoded

    def test_pkce_uses_s256_method(self):
        """Test that PKCE uses SHA-256 method."""
        pkce = generate_pkce()
        assert pkce.code_challenge_method == "S256"

    def test_pkce_challenge_is_sha256_of_verifier(self):
        """Test that the challenge is the SHA-256 hash of the verifier."""
        pkce = generate_pkce()

        # Verify the challenge is SHA-256(verifier) base64url encoded
        expected_hash = hashlib.sha256(pkce.code_verifier.encode("ascii")).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(expected_hash).rstrip(b"=").decode("ascii")
        )

        assert pkce.code_challenge == expected_challenge

    def test_pkce_generates_unique_values(self):
        """Test that each PKCE generation produces unique values."""
        pkce1 = generate_pkce()
        pkce2 = generate_pkce()

        assert pkce1.code_verifier != pkce2.code_verifier
        assert pkce1.code_challenge != pkce2.code_challenge

    def test_pkce_verifier_is_url_safe(self):
        """Test that verifier only contains URL-safe characters."""
        for _ in range(10):  # Test multiple times for randomness
            pkce = generate_pkce()
            # URL-safe base64 only uses A-Z, a-z, 0-9, -, _
            assert all(c.isalnum() or c in "-_" for c in pkce.code_verifier)


class TestGenerateState:
    """Tests for state parameter generation."""

    def test_state_generates_hex_string(self):
        """Test that state is a hex string."""
        state = generate_state()
        assert all(c in "0123456789abcdef" for c in state)

    def test_state_has_correct_length(self):
        """Test that state has expected length (32 chars = 16 bytes)."""
        state = generate_state()
        assert len(state) == 32

    def test_state_generates_unique_values(self):
        """Test that state generation produces unique values."""
        states = [generate_state() for _ in range(100)]
        assert len(set(states)) == 100  # All unique


class TestOAuthTokens:
    """Tests for OAuthTokens dataclass."""

    def test_tokens_creation(self):
        """Test basic token creation."""
        tokens = OAuthTokens(access_token="test_access_token")
        assert tokens.access_token == "test_access_token"
        assert tokens.token_type == "Bearer"

    def test_tokens_with_all_fields(self):
        """Test tokens with all fields populated."""
        tokens = OAuthTokens(
            access_token="access",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh",
            scope="read write",
            issued_at=1000.0,
        )
        assert tokens.access_token == "access"
        assert tokens.expires_in == 3600
        assert tokens.refresh_token == "refresh"
        assert tokens.scope == "read write"
        assert tokens.issued_at == 1000.0

    def test_tokens_not_expired_without_expiry(self):
        """Test that tokens without expiry are never expired."""
        tokens = OAuthTokens(access_token="test", expires_in=None)
        assert not tokens.is_expired()

    def test_tokens_not_expired_when_fresh(self):
        """Test that fresh tokens are not expired."""
        tokens = OAuthTokens(
            access_token="test",
            expires_in=3600,
            issued_at=time.time(),
        )
        assert not tokens.is_expired()

    def test_tokens_expired_when_past_expiry(self):
        """Test that old tokens are expired."""
        tokens = OAuthTokens(
            access_token="test",
            expires_in=3600,
            issued_at=time.time() - 4000,  # Issued 4000 seconds ago
        )
        assert tokens.is_expired()

    def test_tokens_expired_within_buffer(self):
        """Test that tokens expiring within 60s buffer are considered expired."""
        tokens = OAuthTokens(
            access_token="test",
            expires_in=3600,
            issued_at=time.time() - 3550,  # 50 seconds until nominal expiry
        )
        assert tokens.is_expired()  # Within 60s buffer

    def test_tokens_to_dict(self):
        """Test token serialization to dict."""
        tokens = OAuthTokens(
            access_token="access",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh",
            scope="read",
            issued_at=1000.0,
        )
        d = tokens.to_dict()

        assert d["access_token"] == "access"
        assert d["token_type"] == "Bearer"
        assert d["expires_in"] == 3600
        assert d["refresh_token"] == "refresh"
        assert d["scope"] == "read"
        assert d["issued_at"] == 1000.0

    def test_tokens_from_dict(self):
        """Test token deserialization from dict."""
        data = {
            "access_token": "access",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh",
            "scope": "read",
            "issued_at": 1000.0,
        }
        tokens = OAuthTokens.from_dict(data)

        assert tokens.access_token == "access"
        assert tokens.token_type == "Bearer"
        assert tokens.expires_in == 3600
        assert tokens.refresh_token == "refresh"
        assert tokens.scope == "read"
        assert tokens.issued_at == 1000.0

    def test_tokens_from_dict_minimal(self):
        """Test token deserialization with minimal data."""
        data = {"access_token": "access"}
        tokens = OAuthTokens.from_dict(data)

        assert tokens.access_token == "access"
        assert tokens.token_type == "Bearer"  # Default
        assert tokens.expires_in is None
        assert tokens.refresh_token is None


class TestAtlassianResource:
    """Tests for AtlassianResource dataclass."""

    def test_resource_creation(self):
        """Test basic resource creation."""
        resource = AtlassianResource(
            id="cloud-123",
            url="https://mysite.atlassian.net",
            name="My Site",
            scopes=["read:jira-work"],
        )
        assert resource.id == "cloud-123"
        assert resource.url == "https://mysite.atlassian.net"
        assert resource.name == "My Site"
        assert resource.scopes == ["read:jira-work"]
        assert resource.avatar_url is None


class TestTokenStorage:
    """Tests for TokenStorage class."""

    def test_storage_uses_file_fallback(self):
        """Test that storage falls back to file when keyring unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)

                tokens = OAuthTokens(access_token="test_token", expires_in=3600)
                storage.save_tokens("atlassian", tokens)

                loaded = storage.load_tokens("atlassian")
                assert loaded is not None
                assert loaded.access_token == "test_token"

    def test_storage_delete_tokens(self):
        """Test that tokens can be deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)

                tokens = OAuthTokens(access_token="test_token")
                storage.save_tokens("atlassian", tokens)

                assert storage.delete_tokens("atlassian")
                assert storage.load_tokens("atlassian") is None

    def test_storage_delete_nonexistent_returns_false(self):
        """Test that deleting nonexistent tokens returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                assert not storage.delete_tokens("nonexistent")

    def test_storage_auth_status_not_authenticated(self):
        """Test auth status when no tokens stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                assert (
                    storage.get_auth_status("atlassian") == AuthStatus.NOT_AUTHENTICATED
                )

    def test_storage_auth_status_authenticated(self):
        """Test auth status when valid tokens stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(access_token="test", expires_in=3600)
                storage.save_tokens("atlassian", tokens)

                assert storage.get_auth_status("atlassian") == AuthStatus.AUTHENTICATED

    def test_storage_auth_status_expired(self):
        """Test auth status when tokens expired."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(
                    access_token="test",
                    expires_in=3600,
                    issued_at=time.time() - 4000,
                )
                storage.save_tokens("atlassian", tokens)

                assert storage.get_auth_status("atlassian") == AuthStatus.TOKEN_EXPIRED

    def test_storage_creates_token_directory(self):
        """Test that storage creates the token directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(access_token="test")
                storage.save_tokens("atlassian", tokens)

                token_dir = Path(tmpdir) / ".context-harness/tokens"
                assert token_dir.exists()

    def test_storage_load_invalid_json_returns_none(self):
        """Test that loading invalid JSON returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)

                # Create invalid token file
                token_dir = Path(tmpdir) / ".context-harness/tokens"
                token_dir.mkdir(parents=True)
                (token_dir / "atlassian.json").write_text("invalid json")

                assert storage.load_tokens("atlassian") is None


class TestOAuthCallbackHandler:
    """Tests for OAuthCallbackHandler."""

    def test_handler_reset(self):
        """Test that handler state can be reset."""
        OAuthCallbackHandler.authorization_code = "old_code"
        OAuthCallbackHandler.error = "old_error"
        OAuthCallbackHandler.received_state = "old_state"

        OAuthCallbackHandler.reset()

        assert OAuthCallbackHandler.authorization_code is None
        assert OAuthCallbackHandler.error is None
        assert OAuthCallbackHandler.received_state is None
        assert not OAuthCallbackHandler.callback_received.is_set()


class TestOAuthCallbackServer:
    """Tests for OAuthCallbackServer."""

    def test_server_starts_on_random_port(self):
        """Test that server starts on a random available port."""
        server = OAuthCallbackServer(timeout=5)
        port = server.start()

        try:
            assert port > 0
            assert port < 65536
            assert server.port == port
        finally:
            server.stop()

    def test_server_redirect_uri(self):
        """Test that server provides correct redirect URI."""
        server = OAuthCallbackServer(timeout=5)
        port = server.start()

        try:
            assert server.redirect_uri == f"http://localhost:{port}/callback"
        finally:
            server.stop()

    def test_server_redirect_uri_raises_if_not_started(self):
        """Test that redirect_uri raises if server not started."""
        server = OAuthCallbackServer(timeout=5)

        with pytest.raises(OAuthError):
            _ = server.redirect_uri

    def test_server_stop_is_safe_when_not_started(self):
        """Test that stopping an unstarted server doesn't raise."""
        server = OAuthCallbackServer(timeout=5)
        server.stop()  # Should not raise

    def test_server_can_be_stopped_immediately(self):
        """Test that server can be stopped without waiting for callback."""
        server = OAuthCallbackServer(timeout=5)
        server.start()
        server.stop()  # Should complete quickly
        assert server.server is None


class TestAtlassianOAuthConfig:
    """Tests for AtlassianOAuthConfig."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = AtlassianOAuthConfig(client_id="test_client")

        assert config.client_id == "test_client"
        assert config.client_secret is None
        assert "read:jira-work" in config.scopes
        assert "offline_access" in config.scopes
        assert config.auth_url == "https://auth.atlassian.com/authorize"
        assert config.token_url == "https://auth.atlassian.com/oauth/token"
        assert config.audience == "api.atlassian.com"

    def test_config_custom_scopes(self):
        """Test custom scopes override defaults."""
        config = AtlassianOAuthConfig(
            client_id="test",
            scopes=["read:jira-work"],
        )
        assert config.scopes == ["read:jira-work"]


class TestAtlassianOAuthFlow:
    """Tests for AtlassianOAuthFlow."""

    def test_flow_builds_authorization_url(self):
        """Test that flow builds correct authorization URL."""
        config = AtlassianOAuthConfig(client_id="test_client_id")
        flow = AtlassianOAuthFlow(config)

        url = flow.build_authorization_url("http://localhost:8000/callback")

        assert "https://auth.atlassian.com/authorize" in url
        assert "client_id=test_client_id" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
        assert "response_type=code" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "state=" in url
        assert "audience=api.atlassian.com" in url

    def test_flow_get_auth_status(self):
        """Test flow auth status check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                config = AtlassianOAuthConfig(client_id="test")
                storage = TokenStorage(use_keyring=False)
                flow = AtlassianOAuthFlow(config, token_storage=storage)

                assert flow.get_auth_status() == AuthStatus.NOT_AUTHENTICATED

    def test_flow_logout(self):
        """Test flow logout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                config = AtlassianOAuthConfig(client_id="test")
                storage = TokenStorage(use_keyring=False)
                flow = AtlassianOAuthFlow(config, token_storage=storage)

                # Save some tokens first
                storage.save_tokens("atlassian", OAuthTokens(access_token="test"))

                assert flow.logout()  # Should succeed
                assert not flow.logout()  # Should fail - already logged out


class TestGetAtlassianOAuthFlow:
    """Tests for get_atlassian_oauth_flow convenience function."""

    def test_get_flow_with_client_id(self):
        """Test getting flow with explicit client ID."""
        flow = get_atlassian_oauth_flow(client_id="my_client_id")
        assert flow.config.client_id == "my_client_id"

    def test_get_flow_from_env(self):
        """Test getting flow from environment variable."""
        with mock.patch.dict(os.environ, {"ATLASSIAN_CLIENT_ID": "env_client_id"}):
            flow = get_atlassian_oauth_flow()
            assert flow.config.client_id == "env_client_id"

    def test_get_flow_raises_without_client_id(self):
        """Test that error is raised without client ID."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure ATLASSIAN_CLIENT_ID is not set
            os.environ.pop("ATLASSIAN_CLIENT_ID", None)

            with pytest.raises(OAuthError) as exc_info:
                get_atlassian_oauth_flow()

            assert "client_id" in str(exc_info.value).lower().replace(" ", "_")

    def test_get_flow_with_client_secret(self):
        """Test getting flow with client secret from env."""
        with mock.patch.dict(
            os.environ,
            {
                "ATLASSIAN_CLIENT_ID": "test_id",
                "ATLASSIAN_CLIENT_SECRET": "test_secret",
            },
        ):
            flow = get_atlassian_oauth_flow()
            assert flow.config.client_id == "test_id"
            assert flow.config.client_secret == "test_secret"


class TestMCPOAuthDiscovery:
    """Tests for MCP OAuth discovery functions."""

    def test_parse_www_authenticate_bearer(self):
        """Test parsing Bearer WWW-Authenticate header."""
        header = 'Bearer realm="api.atlassian.com"'
        params = parse_www_authenticate(header)
        assert params.get("realm") == "api.atlassian.com"

    def test_parse_www_authenticate_resource_metadata(self):
        """Test parsing resource_metadata from WWW-Authenticate."""
        header = (
            'Bearer resource_metadata="https://mcp.atlassian.com/.well-known/'
            'oauth-protected-resource"'
        )
        params = parse_www_authenticate(header)
        assert "resource_metadata" in params
        assert ".well-known" in params["resource_metadata"]

    def test_parse_www_authenticate_multiple_params(self):
        """Test parsing multiple parameters."""
        header = 'Bearer realm="api", resource_metadata="https://example.com/meta"'
        params = parse_www_authenticate(header)
        assert params.get("realm") == "api"
        assert params.get("resource_metadata") == "https://example.com/meta"

    def test_check_mcp_auth_required_returns_false_on_success(self):
        """Test that check_mcp_auth_required returns False when no auth needed."""
        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = check_mcp_auth_required("https://example.com/mcp")
            assert result is False

    def test_check_mcp_auth_required_returns_true_on_401(self):
        """Test that check_mcp_auth_required returns True on 401."""
        from urllib.error import HTTPError

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url="https://example.com/mcp",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=None,
            )

            result = check_mcp_auth_required("https://example.com/mcp")
            assert result is True

    def test_check_mcp_auth_required_returns_false_on_other_error(self):
        """Test that check_mcp_auth_required returns False on non-401 error."""
        from urllib.error import HTTPError

        with mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url="https://example.com/mcp",
                code=500,
                msg="Server Error",
                hdrs={},
                fp=None,
            )

            result = check_mcp_auth_required("https://example.com/mcp")
            assert result is False


class TestGetMCPBearerToken:
    """Tests for get_mcp_bearer_token function."""

    def test_returns_none_when_not_authenticated(self):
        """Test returns None when no tokens stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                result = get_mcp_bearer_token("atlassian")
                assert result is None

    def test_returns_token_when_authenticated(self):
        """Test returns token when valid tokens stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(access_token="test_token", expires_in=3600)
                storage.save_tokens("atlassian", tokens)

                result = get_mcp_bearer_token("atlassian")
                assert result == "test_token"

    def test_returns_none_when_token_expired(self):
        """Test returns None when tokens expired."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(
                    access_token="test_token",
                    expires_in=3600,
                    issued_at=time.time() - 4000,  # Expired
                )
                storage.save_tokens("atlassian", tokens)

                result = get_mcp_bearer_token("atlassian")
                assert result is None


class TestMCPAuthCLI:
    """Tests for mcp auth CLI command."""

    def test_mcp_auth_help(self, cli_runner):
        """Test mcp auth help output."""
        from context_harness.cli import main

        result = cli_runner.invoke(main, ["mcp", "auth", "--help"])
        assert result.exit_code == 0
        assert "Authenticate with an MCP server" in result.output
        assert "--client-id" in result.output
        assert "--status" in result.output
        assert "--logout" in result.output

    def test_mcp_auth_invalid_server(self, cli_runner):
        """Test mcp auth with invalid server."""
        from context_harness.cli import main

        result = cli_runner.invoke(main, ["mcp", "auth", "invalid_server"])
        assert result.exit_code == 1
        assert "Unknown MCP server" in result.output

    def test_mcp_auth_non_oauth_server(self, cli_runner):
        """Test mcp auth with server that doesn't use OAuth."""
        from context_harness.cli import main

        result = cli_runner.invoke(main, ["mcp", "auth", "context7"])
        assert result.exit_code == 1
        assert "does not use OAuth" in result.output

    def test_mcp_auth_atlassian_no_client_id(self, cli_runner, monkeypatch):
        """Test mcp auth atlassian without client ID."""
        from context_harness.cli import main

        # Ensure no client ID in environment
        monkeypatch.delenv("ATLASSIAN_CLIENT_ID", raising=False)

        result = cli_runner.invoke(main, ["mcp", "auth", "atlassian"])
        assert result.exit_code == 1
        # Check for client_id mention in output (case insensitive)
        assert "client" in result.output.lower()

    def test_mcp_auth_atlassian_status_not_authenticated(
        self, cli_runner, monkeypatch, tmp_path
    ):
        """Test mcp auth atlassian --status when not authenticated."""
        from context_harness.cli import main

        monkeypatch.setenv("ATLASSIAN_CLIENT_ID", "test_id")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = cli_runner.invoke(main, ["mcp", "auth", "atlassian", "--status"])
        assert result.exit_code == 0
        assert "Not authenticated" in result.output

    def test_mcp_auth_atlassian_logout_not_logged_in(
        self, cli_runner, monkeypatch, tmp_path
    ):
        """Test mcp auth atlassian --logout when not logged in."""
        from context_harness.cli import main

        monkeypatch.setenv("ATLASSIAN_CLIENT_ID", "test_id")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = cli_runner.invoke(main, ["mcp", "auth", "atlassian", "--logout"])
        assert result.exit_code == 0
        assert "Not currently logged in" in result.output


# Fixtures


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()


# =============================================================================
# Tests for Generic OAuth Configuration and Flow
# =============================================================================


class TestOAuthConfig:
    """Tests for OAuthConfig dataclass."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
        )
        assert config.service_name == "test-service"
        assert config.client_id == "test_client"
        assert config.auth_url == "https://auth.example.com/authorize"
        assert config.token_url == "https://auth.example.com/token"

    def test_config_with_all_fields(self):
        """Test config with all optional fields."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            client_secret="test_secret",
            scopes=["read", "write"],
            audience="api.example.com",
            resources_url="https://api.example.com/resources",
            extra_auth_params={"prompt": "consent"},
            display_name="Test Service",
            setup_url="https://developer.example.com/apps",
        )
        assert config.client_secret == "test_secret"
        assert config.scopes == ["read", "write"]
        assert config.audience == "api.example.com"
        assert config.resources_url == "https://api.example.com/resources"
        assert config.extra_auth_params == {"prompt": "consent"}
        assert config.display_name == "Test Service"
        assert config.setup_url == "https://developer.example.com/apps"


class TestOAuthProviderRegistry:
    """Tests for OAuth provider registry."""

    def test_atlassian_is_registered(self):
        """Test that Atlassian is pre-registered."""
        assert "atlassian" in OAUTH_PROVIDERS
        atlassian = OAUTH_PROVIDERS["atlassian"]
        assert atlassian.service_name == "atlassian"
        assert atlassian.auth_url == "https://auth.atlassian.com/authorize"
        assert atlassian.token_url == "https://auth.atlassian.com/oauth/token"
        assert "read:jira-work" in atlassian.scopes

    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        custom_config = OAuthConfig(
            service_name="custom-test",
            client_id="",
            auth_url="https://auth.custom.com/authorize",
            token_url="https://auth.custom.com/token",
            scopes=["read"],
        )
        register_oauth_provider(custom_config)

        assert "custom-test" in OAUTH_PROVIDERS
        assert (
            OAUTH_PROVIDERS["custom-test"].auth_url
            == "https://auth.custom.com/authorize"
        )

        # Cleanup
        del OAUTH_PROVIDERS["custom-test"]

    def test_get_oauth_config(self):
        """Test getting config with credentials."""
        config = get_oauth_config("atlassian", "my_client_id", "my_secret")

        assert config.service_name == "atlassian"
        assert config.client_id == "my_client_id"
        assert config.client_secret == "my_secret"
        assert config.auth_url == "https://auth.atlassian.com/authorize"

    def test_get_oauth_config_unknown_provider_raises(self):
        """Test that unknown provider raises error."""
        with pytest.raises(OAuthError) as exc_info:
            get_oauth_config("unknown-provider", "client_id")
        assert "Unknown OAuth provider" in str(exc_info.value)


class TestMCPOAuthFlow:
    """Tests for MCPOAuthFlow generic class."""

    def test_flow_creation(self):
        """Test creating a generic OAuth flow."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes=["read"],
        )
        flow = MCPOAuthFlow(config)

        assert flow.service_name == "test-service"
        assert flow.config.client_id == "test_client"

    def test_flow_builds_authorization_url(self):
        """Test that flow builds correct authorization URL."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client_id",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes=["read", "write"],
        )
        flow = MCPOAuthFlow(config)

        url = flow.build_authorization_url("http://localhost:8000/callback")

        assert "https://auth.example.com/authorize" in url
        assert "client_id=test_client_id" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
        assert "response_type=code" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "state=" in url
        # Scopes should be URL-encoded space-separated
        assert "scope=read+write" in url or "scope=read%20write" in url

    def test_flow_builds_authorization_url_with_audience(self):
        """Test that flow includes audience when configured."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            audience="api.example.com",
        )
        flow = MCPOAuthFlow(config)

        url = flow.build_authorization_url("http://localhost:8000/callback")
        assert "audience=api.example.com" in url

    def test_flow_builds_authorization_url_with_extra_params(self):
        """Test that flow includes extra auth params."""
        config = OAuthConfig(
            service_name="test-service",
            client_id="test_client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            extra_auth_params={"prompt": "consent", "custom": "value"},
        )
        flow = MCPOAuthFlow(config)

        url = flow.build_authorization_url("http://localhost:8000/callback")
        assert "prompt=consent" in url
        assert "custom=value" in url

    def test_flow_get_auth_status(self):
        """Test flow auth status check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                config = OAuthConfig(
                    service_name="test-service",
                    client_id="test_client",
                    auth_url="https://auth.example.com/authorize",
                    token_url="https://auth.example.com/token",
                )
                storage = TokenStorage(use_keyring=False)
                flow = MCPOAuthFlow(config, token_storage=storage)

                assert flow.get_auth_status() == AuthStatus.NOT_AUTHENTICATED

    def test_flow_get_tokens_returns_none_when_not_authenticated(self):
        """Test that get_tokens returns None when not authenticated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                config = OAuthConfig(
                    service_name="test-service",
                    client_id="test_client",
                    auth_url="https://auth.example.com/authorize",
                    token_url="https://auth.example.com/token",
                )
                storage = TokenStorage(use_keyring=False)
                flow = MCPOAuthFlow(config, token_storage=storage)

                assert flow.get_tokens() is None

    def test_flow_logout(self):
        """Test flow logout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                config = OAuthConfig(
                    service_name="test-service",
                    client_id="test_client",
                    auth_url="https://auth.example.com/authorize",
                    token_url="https://auth.example.com/token",
                )
                storage = TokenStorage(use_keyring=False)
                flow = MCPOAuthFlow(config, token_storage=storage)

                # Save some tokens first
                storage.save_tokens("test-service", OAuthTokens(access_token="test"))

                assert flow.logout()  # Should succeed
                assert not flow.logout()  # Should fail - already logged out


class TestGetOAuthFlow:
    """Tests for get_oauth_flow convenience function."""

    def test_get_flow_with_client_id(self):
        """Test getting flow with explicit client ID."""
        flow = get_oauth_flow("atlassian", client_id="my_client_id")
        assert flow.config.client_id == "my_client_id"
        assert flow.service_name == "atlassian"

    def test_get_flow_from_env(self):
        """Test getting flow from environment variable."""
        with mock.patch.dict(os.environ, {"ATLASSIAN_CLIENT_ID": "env_client_id"}):
            flow = get_oauth_flow("atlassian")
            assert flow.config.client_id == "env_client_id"

    def test_get_flow_raises_without_client_id(self):
        """Test that error is raised without client ID."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure ATLASSIAN_CLIENT_ID is not set
            os.environ.pop("ATLASSIAN_CLIENT_ID", None)

            with pytest.raises(OAuthError) as exc_info:
                get_oauth_flow("atlassian")

            assert "client" in str(exc_info.value).lower().replace(" ", "_")

    def test_get_flow_raises_for_unknown_provider(self):
        """Test that error is raised for unknown provider."""
        with pytest.raises(OAuthError) as exc_info:
            get_oauth_flow("unknown-provider", client_id="test")

        assert "Unknown OAuth provider" in str(exc_info.value)

    def test_get_flow_with_client_secret(self):
        """Test getting flow with client secret."""
        flow = get_oauth_flow(
            "atlassian",
            client_id="test_id",
            client_secret="test_secret",
        )
        assert flow.config.client_id == "test_id"
        assert flow.config.client_secret == "test_secret"


class TestAtlassianOAuthConfigToGeneric:
    """Tests for AtlassianOAuthConfig.to_generic() method."""

    def test_to_generic_conversion(self):
        """Test converting AtlassianOAuthConfig to generic OAuthConfig."""
        atlassian_config = AtlassianOAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
        )
        generic = atlassian_config.to_generic()

        assert generic.service_name == "atlassian"
        assert generic.client_id == "test_client"
        assert generic.client_secret == "test_secret"
        assert generic.auth_url == "https://auth.atlassian.com/authorize"
        assert generic.token_url == "https://auth.atlassian.com/oauth/token"
        assert "read:jira-work" in generic.scopes


class TestTokenStorageMultipleServices:
    """Tests for TokenStorage with multiple services."""

    def test_storage_isolates_services(self):
        """Test that tokens are isolated per service."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)

                # Store tokens for different services
                storage.save_tokens(
                    "atlassian", OAuthTokens(access_token="atlassian_token")
                )
                storage.save_tokens("github", OAuthTokens(access_token="github_token"))

                # Verify isolation
                atlassian = storage.load_tokens("atlassian")
                github = storage.load_tokens("github")

                assert atlassian is not None
                assert atlassian.access_token == "atlassian_token"
                assert github is not None
                assert github.access_token == "github_token"

    def test_deleting_one_service_doesnt_affect_others(self):
        """Test that deleting tokens for one service doesn't affect others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)

                storage.save_tokens(
                    "atlassian", OAuthTokens(access_token="atlassian_token")
                )
                storage.save_tokens("github", OAuthTokens(access_token="github_token"))

                # Delete one service
                storage.delete_tokens("atlassian")

                # Verify other service is unaffected
                assert storage.load_tokens("atlassian") is None
                github = storage.load_tokens("github")
                assert github is not None
                assert github.access_token == "github_token"


class TestGetMCPBearerTokenGeneric:
    """Tests for get_mcp_bearer_token with multiple services."""

    def test_returns_token_for_any_service(self):
        """Test returns token for any registered service."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(Path, "home", return_value=Path(tmpdir)):
                storage = TokenStorage(use_keyring=False)
                tokens = OAuthTokens(access_token="custom_token", expires_in=3600)
                storage.save_tokens("custom-service", tokens)

                result = get_mcp_bearer_token("custom-service")
                assert result == "custom_token"
