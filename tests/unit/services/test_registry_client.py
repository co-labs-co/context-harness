"""Unit tests for HttpRegistryClient and related registry abstractions.

Tests cover:
- RegistryAuth (from_dict, to_dict, get_token/username/password)
- RegistryConfig (from_dict, to_dict, factory methods)
- HttpRegistryClient
  - check_auth with various auth types
  - check_access (success / failure)
  - fetch_manifest
  - fetch_file
  - fetch_directory (with listing, without listing, path traversal guards)
  - _is_safe_path_component (security validation)
  - _build_request (auth header construction)
- create_registry_client factory function
"""

import base64
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest import mock

import pytest

from context_harness.services.registry_client import (
    AuthType,
    GitHubRegistryClient,
    HttpRegistryClient,
    RegistryAuth,
    RegistryConfig,
    RegistryType,
    create_registry_client,
)


# ---------------------------------------------------------------------------
# RegistryAuth
# ---------------------------------------------------------------------------


class TestRegistryAuth:
    """Tests for RegistryAuth."""

    def test_default_is_none_auth(self):
        auth = RegistryAuth()
        assert auth.type == AuthType.NONE

    def test_from_dict_bearer(self):
        auth = RegistryAuth.from_dict({"type": "bearer", "token_env": "MY_TOKEN"})
        assert auth.type == AuthType.BEARER
        assert auth.token_env == "MY_TOKEN"

    def test_from_dict_api_key_custom_header(self):
        auth = RegistryAuth.from_dict(
            {"type": "api_key", "token_env": "KEY", "header_name": "X-Custom"}
        )
        assert auth.type == AuthType.API_KEY
        assert auth.header_name == "X-Custom"

    def test_from_dict_basic(self):
        auth = RegistryAuth.from_dict(
            {"type": "basic", "username_env": "USER", "password_env": "PASS"}
        )
        assert auth.type == AuthType.BASIC
        assert auth.username_env == "USER"
        assert auth.password_env == "PASS"

    def test_from_dict_unknown_type_defaults_none(self):
        auth = RegistryAuth.from_dict({"type": "kerberos"})
        assert auth.type == AuthType.NONE

    def test_to_dict_minimal(self):
        auth = RegistryAuth()
        d = auth.to_dict()
        assert d == {"type": "none"}

    def test_to_dict_bearer(self):
        auth = RegistryAuth(type=AuthType.BEARER, token_env="TOK")
        d = auth.to_dict()
        assert d["type"] == "bearer"
        assert d["token_env"] == "TOK"

    def test_to_dict_custom_header_only_if_non_default(self):
        auth = RegistryAuth(type=AuthType.API_KEY, token_env="K")
        d = auth.to_dict()
        assert "header_name" not in d  # default X-API-Key omitted

        auth2 = RegistryAuth(type=AuthType.API_KEY, token_env="K", header_name="X-Alt")
        d2 = auth2.to_dict()
        assert d2["header_name"] == "X-Alt"

    def test_get_token_from_env(self, monkeypatch):
        monkeypatch.setenv("REG_TOKEN", "secret123")
        auth = RegistryAuth(type=AuthType.BEARER, token_env="REG_TOKEN")
        assert auth.get_token() == "secret123"

    def test_get_token_missing_env(self, monkeypatch):
        monkeypatch.delenv("REG_TOKEN", raising=False)
        auth = RegistryAuth(type=AuthType.BEARER, token_env="REG_TOKEN")
        assert auth.get_token() is None

    def test_get_token_no_env_configured(self):
        auth = RegistryAuth()
        assert auth.get_token() is None

    def test_get_username_from_env(self, monkeypatch):
        monkeypatch.setenv("REG_USER", "admin")
        auth = RegistryAuth(type=AuthType.BASIC, username_env="REG_USER")
        assert auth.get_username() == "admin"

    def test_get_password_from_env(self, monkeypatch):
        monkeypatch.setenv("REG_PASS", "hunter2")
        auth = RegistryAuth(type=AuthType.BASIC, password_env="REG_PASS")
        assert auth.get_password() == "hunter2"


# ---------------------------------------------------------------------------
# RegistryConfig
# ---------------------------------------------------------------------------


class TestRegistryConfig:
    """Tests for RegistryConfig."""

    def test_default_is_github(self):
        config = RegistryConfig()
        assert config.type == RegistryType.GITHUB

    def test_from_dict_github(self):
        config = RegistryConfig.from_dict({"type": "github", "url": "owner/repo"})
        assert config.type == RegistryType.GITHUB
        assert config.url == "owner/repo"

    def test_from_dict_http_with_auth(self):
        config = RegistryConfig.from_dict(
            {
                "type": "http",
                "url": "https://registry.example.com",
                "auth": {"type": "bearer", "token_env": "TOK"},
            }
        )
        assert config.type == RegistryType.HTTP
        assert config.auth.type == AuthType.BEARER

    def test_from_dict_unknown_type_defaults_github(self):
        config = RegistryConfig.from_dict({"type": "s3", "url": "bucket/path"})
        assert config.type == RegistryType.GITHUB

    def test_to_dict_github_no_auth(self):
        config = RegistryConfig.github("owner/repo")
        d = config.to_dict()
        assert d == {"type": "github", "url": "owner/repo"}
        assert "auth" not in d

    def test_to_dict_http_with_auth(self):
        auth = RegistryAuth(type=AuthType.BEARER, token_env="TOK")
        config = RegistryConfig.http("https://example.com", auth)
        d = config.to_dict()
        assert d["type"] == "http"
        assert "auth" in d
        assert d["auth"]["type"] == "bearer"

    def test_github_factory(self):
        config = RegistryConfig.github("org/skills")
        assert config.type == RegistryType.GITHUB
        assert config.url == "org/skills"

    def test_http_factory_no_auth(self):
        config = RegistryConfig.http("https://example.com")
        assert config.type == RegistryType.HTTP
        assert config.auth.type == AuthType.NONE


# ---------------------------------------------------------------------------
# HttpRegistryClient._is_safe_path_component
# ---------------------------------------------------------------------------


class TestHttpClientSafePath:
    """Tests for path traversal protection."""

    @pytest.fixture
    def client(self):
        return HttpRegistryClient("https://example.com")

    @pytest.mark.parametrize(
        "component,expected",
        [
            ("SKILL.md", True),
            ("version.txt", True),
            ("references", True),
            ("my-skill-v2", True),
            ("", False),
            ("..", False),
            ("../etc/passwd", False),
            ("foo/bar", False),
            ("foo\\bar", False),
            ("/absolute", False),
            ("\\backslash", False),
            ("..sneaky", False),
            ("path/../traverse", False),
        ],
    )
    def test_is_safe_path_component(self, client, component, expected):
        assert client._is_safe_path_component(component) is expected


# ---------------------------------------------------------------------------
# HttpRegistryClient.check_auth
# ---------------------------------------------------------------------------


class TestHttpClientCheckAuth:
    """Tests for check_auth with different auth types."""

    def test_no_auth_always_true(self):
        client = HttpRegistryClient("https://example.com")
        assert client.check_auth() is True

    def test_bearer_with_token(self, monkeypatch):
        monkeypatch.setenv("MY_TOK", "secret")
        auth = RegistryAuth(type=AuthType.BEARER, token_env="MY_TOK")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is True

    def test_bearer_without_token(self, monkeypatch):
        monkeypatch.delenv("MY_TOK", raising=False)
        auth = RegistryAuth(type=AuthType.BEARER, token_env="MY_TOK")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is False

    def test_api_key_with_token(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "k")
        auth = RegistryAuth(type=AuthType.API_KEY, token_env="API_KEY")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is True

    def test_api_key_without_token(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        auth = RegistryAuth(type=AuthType.API_KEY, token_env="API_KEY")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is False

    def test_basic_with_both_credentials(self, monkeypatch):
        monkeypatch.setenv("U", "user")
        monkeypatch.setenv("P", "pass")
        auth = RegistryAuth(type=AuthType.BASIC, username_env="U", password_env="P")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is True

    def test_basic_missing_password(self, monkeypatch):
        monkeypatch.setenv("U", "user")
        monkeypatch.delenv("P", raising=False)
        auth = RegistryAuth(type=AuthType.BASIC, username_env="U", password_env="P")
        client = HttpRegistryClient("https://example.com", auth)
        assert client.check_auth() is False


# ---------------------------------------------------------------------------
# HttpRegistryClient._build_request (auth headers)
# ---------------------------------------------------------------------------


class TestHttpClientBuildRequest:
    """Tests for _build_request auth header construction."""

    def test_no_auth_no_headers(self):
        client = HttpRegistryClient("https://example.com")
        req = client._build_request("https://example.com/test")
        assert req.get_header("Authorization") is None

    def test_bearer_header(self, monkeypatch):
        monkeypatch.setenv("TOK", "my-bearer-token")
        auth = RegistryAuth(type=AuthType.BEARER, token_env="TOK")
        client = HttpRegistryClient("https://example.com", auth)
        req = client._build_request("https://example.com/test")
        assert req.get_header("Authorization") == "Bearer my-bearer-token"

    def test_api_key_header(self, monkeypatch):
        monkeypatch.setenv("KEY", "my-api-key")
        auth = RegistryAuth(type=AuthType.API_KEY, token_env="KEY")
        client = HttpRegistryClient("https://example.com", auth)
        req = client._build_request("https://example.com/test")
        assert req.get_header("X-api-key") == "my-api-key"

    def test_api_key_custom_header(self, monkeypatch):
        monkeypatch.setenv("KEY", "val")
        auth = RegistryAuth(
            type=AuthType.API_KEY, token_env="KEY", header_name="X-Custom"
        )
        client = HttpRegistryClient("https://example.com", auth)
        req = client._build_request("https://example.com/test")
        assert req.get_header("X-custom") == "val"

    def test_basic_auth_header(self, monkeypatch):
        monkeypatch.setenv("U", "admin")
        monkeypatch.setenv("P", "secret")
        auth = RegistryAuth(type=AuthType.BASIC, username_env="U", password_env="P")
        client = HttpRegistryClient("https://example.com", auth)
        req = client._build_request("https://example.com/test")

        expected = base64.b64encode(b"admin:secret").decode("ascii")
        assert req.get_header("Authorization") == f"Basic {expected}"

    def test_bearer_missing_token_no_header(self, monkeypatch):
        monkeypatch.delenv("TOK", raising=False)
        auth = RegistryAuth(type=AuthType.BEARER, token_env="TOK")
        client = HttpRegistryClient("https://example.com", auth)
        req = client._build_request("https://example.com/test")
        assert req.get_header("Authorization") is None


# ---------------------------------------------------------------------------
# HttpRegistryClient.check_access, fetch_manifest, fetch_file
# (mocked HTTP layer)
# ---------------------------------------------------------------------------


class TestHttpClientNetworkOps:
    """Tests for network operations using mocked urlopen."""

    def test_check_access_success(self):
        client = HttpRegistryClient("https://registry.example.com")
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            return_value=mock_response,
        ):
            assert client.check_access() is True

    def test_check_access_failure(self):
        from urllib.error import URLError

        client = HttpRegistryClient("https://registry.example.com")
        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            side_effect=URLError("connection refused"),
        ):
            assert client.check_access() is False

    def test_fetch_manifest_success(self):
        manifest = json.dumps({"skills": [{"name": "my-skill"}]})
        client = HttpRegistryClient("https://registry.example.com")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = manifest.encode("utf-8")
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            return_value=mock_response,
        ):
            result = client.fetch_manifest()
            assert result is not None
            parsed = json.loads(result)
            assert parsed["skills"][0]["name"] == "my-skill"

    def test_fetch_manifest_failure(self):
        from urllib.error import HTTPError

        client = HttpRegistryClient("https://registry.example.com")
        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            side_effect=HTTPError(None, 404, "Not Found", {}, None),
        ):
            assert client.fetch_manifest() is None

    def test_fetch_file_success(self):
        content = b"# My Skill\nSome content"
        client = HttpRegistryClient("https://registry.example.com")

        mock_response = mock.MagicMock()
        mock_response.read.return_value = content
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            return_value=mock_response,
        ):
            result = client.fetch_file("skill/my-skill/SKILL.md")
            assert result == content

    def test_fetch_file_failure(self):
        from urllib.error import HTTPError

        client = HttpRegistryClient("https://registry.example.com")
        with mock.patch(
            "context_harness.services.registry_client.urlopen",
            side_effect=HTTPError(None, 404, "Not Found", {}, None),
        ):
            assert client.fetch_file("nonexistent") is None

    def test_base_url_trailing_slash_stripped(self):
        client = HttpRegistryClient("https://example.com/skills/")
        assert client.base_url == "https://example.com/skills"


# ---------------------------------------------------------------------------
# HttpRegistryClient.fetch_directory
# ---------------------------------------------------------------------------


class TestHttpClientFetchDirectory:
    """Tests for fetch_directory."""

    def test_fetch_directory_with_listing(self, tmp_path):
        """When .listing.json is available, uses it."""
        client = HttpRegistryClient("https://example.com")

        listing_data = json.dumps(
            {"files": ["SKILL.md", "version.txt", "extra.txt"], "directories": []}
        )

        def mock_fetch_file(path):
            if path.endswith(".listing.json"):
                return listing_data.encode("utf-8")
            elif path.endswith("SKILL.md"):
                return b"# Skill"
            elif path.endswith("version.txt"):
                return b"1.0.0"
            elif path.endswith("extra.txt"):
                return b"extra content"
            return None

        with mock.patch.object(client, "_fetch_file", side_effect=mock_fetch_file):
            dest = tmp_path / "skill-out"
            result = client.fetch_directory("skill/test", dest)

        assert result is True
        assert (dest / "SKILL.md").exists()
        assert (dest / "version.txt").exists()
        assert (dest / "extra.txt").exists()

    def test_fetch_directory_without_listing_falls_back(self, tmp_path):
        """When no .listing.json, fetches common files."""
        client = HttpRegistryClient("https://example.com")

        def mock_fetch_file(path):
            if path.endswith(".listing.json"):
                return None  # No listing available
            elif path.endswith("SKILL.md"):
                return b"# Skill Content"
            elif path.endswith("version.txt"):
                return b"2.0.0"
            return None

        with mock.patch.object(client, "_fetch_file", side_effect=mock_fetch_file):
            dest = tmp_path / "skill-out"
            result = client.fetch_directory("skill/test", dest)

        assert result is True
        assert (dest / "SKILL.md").exists()

    def test_fetch_directory_no_skill_md_returns_false(self, tmp_path):
        """If SKILL.md cannot be fetched, returns False."""
        client = HttpRegistryClient("https://example.com")

        with mock.patch.object(client, "_fetch_file", return_value=None):
            dest = tmp_path / "empty-out"
            result = client.fetch_directory("skill/missing", dest)

        assert result is False

    def test_fetch_directory_skips_unsafe_filenames(self, tmp_path):
        """Path traversal filenames in listing are skipped."""
        client = HttpRegistryClient("https://example.com")

        listing_data = json.dumps(
            {
                "files": ["SKILL.md", "../etc/passwd", "version.txt"],
                "directories": ["../sneaky"],
            }
        )

        def mock_fetch_file(path):
            if path.endswith(".listing.json"):
                return listing_data.encode("utf-8")
            elif path.endswith("SKILL.md"):
                return b"# Skill"
            elif path.endswith("version.txt"):
                return b"1.0.0"
            return None

        with mock.patch.object(client, "_fetch_file", side_effect=mock_fetch_file):
            dest = tmp_path / "safe-out"
            result = client.fetch_directory("skill/test", dest)

        assert result is True
        assert (dest / "SKILL.md").exists()
        # Traversal files should NOT exist
        assert not (dest / ".." / "etc" / "passwd").exists()


# ---------------------------------------------------------------------------
# create_registry_client factory
# ---------------------------------------------------------------------------


class TestCreateRegistryClient:
    """Tests for create_registry_client factory."""

    def test_creates_github_client(self):
        config = RegistryConfig.github("org/repo")
        client = create_registry_client(config)
        assert isinstance(client, GitHubRegistryClient)
        assert client.repo == "org/repo"

    def test_creates_http_client(self):
        config = RegistryConfig.http("https://example.com")
        client = create_registry_client(config)
        assert isinstance(client, HttpRegistryClient)
        assert client.base_url == "https://example.com"

    def test_http_client_receives_auth(self, monkeypatch):
        monkeypatch.setenv("TOK", "val")
        auth = RegistryAuth(type=AuthType.BEARER, token_env="TOK")
        config = RegistryConfig.http("https://example.com", auth)
        client = create_registry_client(config)
        assert isinstance(client, HttpRegistryClient)
        assert client.auth.type == AuthType.BEARER

    def test_unknown_type_defaults_to_github(self):
        """Fallback: unknown registry type creates GitHub client."""
        config = RegistryConfig()
        config.type = RegistryType.GITHUB
        config.url = "fallback/repo"
        client = create_registry_client(config)
        assert isinstance(client, GitHubRegistryClient)
