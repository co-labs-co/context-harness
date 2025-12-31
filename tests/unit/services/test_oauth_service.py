"""Tests for OAuthService.

Tests use MemoryTokenStorage for isolation.
Network-dependent tests (authenticate, refresh) are marked as integration tests.
"""

from __future__ import annotations

import time

from context_harness.primitives import (
    AuthStatus,
    ErrorCode,
    Failure,
    OAuthTokens,
    Success,
)
from context_harness.services.oauth_service import (
    MemoryTokenStorage,
    OAuthService,
    OAUTH_PROVIDERS,
)


class TestMemoryTokenStorage:
    """Tests for MemoryTokenStorage."""

    def test_save_and_load_tokens(self) -> None:
        """Test saving and loading tokens."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="test-access-token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test-refresh-token",
            scope="read:test",
            issued_at=time.time(),
        )

        storage.save_tokens("test-service", tokens)
        loaded = storage.load_tokens("test-service")

        assert loaded is not None
        assert loaded.access_token == "test-access-token"
        assert loaded.refresh_token == "test-refresh-token"

    def test_load_nonexistent_tokens(self) -> None:
        """Test loading tokens that don't exist."""
        storage = MemoryTokenStorage()
        loaded = storage.load_tokens("nonexistent")

        assert loaded is None

    def test_delete_existing_tokens(self) -> None:
        """Test deleting existing tokens."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="test-access-token",
            token_type="Bearer",
        )
        storage.save_tokens("test-service", tokens)

        result = storage.delete_tokens("test-service")

        assert result is True
        assert storage.load_tokens("test-service") is None

    def test_delete_nonexistent_tokens(self) -> None:
        """Test deleting tokens that don't exist."""
        storage = MemoryTokenStorage()

        result = storage.delete_tokens("nonexistent")

        assert result is False


class TestOAuthServiceListProviders:
    """Tests for OAuthService.list_providers()."""

    def test_list_providers_returns_providers(self) -> None:
        """Test listing available OAuth providers."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.list_providers()

        assert isinstance(result, Success)
        providers = result.value
        assert len(providers) >= 1

        # Check atlassian is in the list
        provider_names = [p.service_name for p in providers]
        assert "atlassian" in provider_names

    def test_list_providers_includes_urls(self) -> None:
        """Test that providers include required URLs."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.list_providers()
        assert isinstance(result, Success)

        for provider in result.value:
            assert provider.auth_url, f"Missing auth_url for {provider.service_name}"
            assert provider.token_url, f"Missing token_url for {provider.service_name}"


class TestOAuthServiceGetStatus:
    """Tests for OAuthService.get_status()."""

    def test_get_status_not_authenticated(self) -> None:
        """Test status when not authenticated."""
        storage = MemoryTokenStorage()
        service = OAuthService(token_storage=storage)

        result = service.get_status("atlassian")

        assert isinstance(result, Success)
        assert result.value == AuthStatus.NOT_AUTHENTICATED

    def test_get_status_authenticated(self) -> None:
        """Test status when authenticated with valid token."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="valid-token",
            token_type="Bearer",
            expires_in=3600,  # 1 hour
            issued_at=time.time(),  # Just issued
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.get_status("atlassian")

        assert isinstance(result, Success)
        assert result.value == AuthStatus.AUTHENTICATED

    def test_get_status_token_expired(self) -> None:
        """Test status when token is expired."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="expired-token",
            token_type="Bearer",
            expires_in=3600,  # 1 hour
            issued_at=time.time() - 7200,  # Issued 2 hours ago
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.get_status("atlassian")

        assert isinstance(result, Success)
        assert result.value == AuthStatus.TOKEN_EXPIRED

    def test_get_status_unknown_provider(self) -> None:
        """Test status for unknown provider."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.get_status("unknown-provider")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND
        assert "unknown-provider" in result.error


class TestOAuthServiceGetTokens:
    """Tests for OAuthService.get_tokens()."""

    def test_get_tokens_when_authenticated(self) -> None:
        """Test getting tokens when authenticated."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="my-access-token",
            token_type="Bearer",
            refresh_token="my-refresh-token",
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.get_tokens("atlassian")

        assert isinstance(result, Success)
        assert result.value.access_token == "my-access-token"
        assert result.value.refresh_token == "my-refresh-token"

    def test_get_tokens_when_not_authenticated(self) -> None:
        """Test getting tokens when not authenticated."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.get_tokens("atlassian")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED


class TestOAuthServiceGetBearerToken:
    """Tests for OAuthService.get_bearer_token()."""

    def test_get_bearer_token_valid(self) -> None:
        """Test getting bearer token when valid."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="bearer-token-123",
            token_type="Bearer",
            expires_in=3600,
            issued_at=time.time(),
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.get_bearer_token("atlassian")

        assert isinstance(result, Success)
        assert result.value == "bearer-token-123"

    def test_get_bearer_token_not_authenticated(self) -> None:
        """Test getting bearer token when not authenticated."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.get_bearer_token("atlassian")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED

    def test_get_bearer_token_expired(self) -> None:
        """Test getting bearer token when expired."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="expired-token",
            token_type="Bearer",
            expires_in=3600,
            issued_at=time.time() - 7200,  # Expired
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.get_bearer_token("atlassian")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.TOKEN_EXPIRED


class TestOAuthServiceLogout:
    """Tests for OAuthService.logout()."""

    def test_logout_when_authenticated(self) -> None:
        """Test logout removes tokens."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="token-to-delete",
            token_type="Bearer",
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.logout("atlassian")

        assert isinstance(result, Success)
        assert result.value is True

        # Verify tokens are gone
        assert storage.load_tokens("atlassian") is None

    def test_logout_when_not_authenticated(self) -> None:
        """Test logout when not authenticated (no-op)."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.logout("atlassian")

        assert isinstance(result, Success)
        assert result.value is False


class TestOAuthServiceEnsureValidToken:
    """Tests for OAuthService.ensure_valid_token()."""

    def test_ensure_valid_token_when_valid(self) -> None:
        """Test ensure_valid_token returns tokens when valid."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="valid-token",
            token_type="Bearer",
            expires_in=3600,
            issued_at=time.time(),
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.ensure_valid_token("atlassian")

        assert isinstance(result, Success)
        assert result.value.access_token == "valid-token"

    def test_ensure_valid_token_not_authenticated(self) -> None:
        """Test ensure_valid_token fails when not authenticated."""
        service = OAuthService(token_storage=MemoryTokenStorage())

        result = service.ensure_valid_token("atlassian")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED

    def test_ensure_valid_token_expired_no_refresh(self) -> None:
        """Test ensure_valid_token fails when expired with no refresh token."""
        storage = MemoryTokenStorage()
        tokens = OAuthTokens(
            access_token="expired-token",
            token_type="Bearer",
            expires_in=3600,
            issued_at=time.time() - 7200,
            refresh_token=None,  # No refresh token
        )
        storage.save_tokens("atlassian", tokens)
        service = OAuthService(token_storage=storage)

        result = service.ensure_valid_token("atlassian")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.TOKEN_EXPIRED


class TestOAuthProvidersConfig:
    """Tests for OAuth provider configurations."""

    def test_atlassian_config_exists(self) -> None:
        """Test Atlassian provider configuration exists."""
        assert "atlassian" in OAUTH_PROVIDERS

    def test_atlassian_config_has_required_fields(self) -> None:
        """Test Atlassian provider has required fields."""
        config = OAUTH_PROVIDERS["atlassian"]

        assert config.auth_url
        assert config.token_url
        assert len(config.scopes) > 0
        assert "offline_access" in config.scopes  # Required for refresh tokens
