"""Unit tests for MCPService."""

from __future__ import annotations

import json
from pathlib import Path

from context_harness.primitives import (
    ErrorCode,
    Failure,
    MCPAuthType,
    MCPServerType,
    Success,
)
from context_harness.services import MCPService


class TestMCPServiceListAvailable:
    """Tests for MCPService.list_available()."""

    def test_list_available_returns_servers(self) -> None:
        """Should return list of available MCP servers."""
        service = MCPService()
        result = service.list_available()

        assert isinstance(result, Success)
        assert len(result.value) > 0

        # Check known servers
        names = [s.name for s in result.value]
        assert "context7" in names
        assert "atlassian" in names

    def test_list_available_with_custom_registry(self) -> None:
        """Should use custom registry when provided."""
        custom_registry = [
            {
                "name": "custom-server",
                "url": "https://custom.example.com/mcp",
                "description": "A custom MCP server",
                "server_type": "remote",
                "auth_type": None,
            }
        ]

        service = MCPService(registry=custom_registry)
        result = service.list_available()

        assert isinstance(result, Success)
        assert len(result.value) == 1
        assert result.value[0].name == "custom-server"


class TestMCPServiceGetServerInfo:
    """Tests for MCPService.get_server_info()."""

    def test_get_server_info_existing(self) -> None:
        """Should return info for existing server."""
        service = MCPService()
        result = service.get_server_info("context7")

        assert isinstance(result, Success)
        assert result.value.name == "context7"
        assert result.value.server_type == MCPServerType.REMOTE
        assert result.value.auth_type == MCPAuthType.API_KEY

    def test_get_server_info_oauth_server(self) -> None:
        """Should return OAuth auth type for Atlassian."""
        service = MCPService()
        result = service.get_server_info("atlassian")

        assert isinstance(result, Success)
        assert result.value.auth_type == MCPAuthType.OAUTH

    def test_get_server_info_not_found(self) -> None:
        """Should return Failure for unknown server."""
        service = MCPService()
        result = service.get_server_info("nonexistent")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND
        assert "available" in result.details


class TestMCPServiceAdd:
    """Tests for MCPService.add()."""

    def test_add_server(self, tmp_path: Path) -> None:
        """Should add MCP server to config."""
        service = MCPService()
        result = service.add("context7", tmp_path)

        assert isinstance(result, Success)
        assert result.value.name == "context7"

        # Verify config file was created
        config_path = tmp_path / "opencode.json"
        assert config_path.exists()

        config_data = json.loads(config_path.read_text())
        assert "context7" in config_data["mcp"]

    def test_add_server_with_api_key(self, tmp_path: Path) -> None:
        """Should add server with API key header."""
        service = MCPService()
        result = service.add("context7", tmp_path, api_key="test-key")

        assert isinstance(result, Success)
        assert result.value.headers is not None
        assert "CONTEXT7_API_KEY" in result.value.headers

        # Verify in saved config
        config_path = tmp_path / "opencode.json"
        config_data = json.loads(config_path.read_text())
        assert "headers" in config_data["mcp"]["context7"]

    def test_add_server_not_in_registry(self, tmp_path: Path) -> None:
        """Should return Failure for unknown server."""
        service = MCPService()
        result = service.add("unknown-server", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND


class TestMCPServiceRemove:
    """Tests for MCPService.remove()."""

    def test_remove_server(self, tmp_path: Path) -> None:
        """Should remove MCP server from config."""
        # Create initial config
        config_data = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "context7": {
                    "type": "remote",
                    "url": "https://mcp.context7.com/mcp",
                }
            },
        }
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = MCPService()
        result = service.remove("context7", tmp_path)

        assert isinstance(result, Success)

        # Verify config was updated (mcp may be empty or missing)
        config_data = json.loads(config_path.read_text())
        mcp_servers = config_data.get("mcp", {})
        assert "context7" not in mcp_servers


class TestMCPServiceListConfigured:
    """Tests for MCPService.list_configured()."""

    def test_list_configured_with_servers(self, tmp_path: Path) -> None:
        """Should list configured servers."""
        config_data = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "context7": {
                    "type": "remote",
                    "url": "https://mcp.context7.com/mcp",
                }
            },
        }
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = MCPService()
        result = service.list_configured(tmp_path)

        assert isinstance(result, Success)
        assert "context7" in result.value

    def test_list_configured_no_config(self, tmp_path: Path) -> None:
        """Should return empty dict when no config."""
        service = MCPService()
        result = service.list_configured(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 0


class TestMCPServiceIsConfigured:
    """Tests for MCPService.is_configured()."""

    def test_is_configured_true(self, tmp_path: Path) -> None:
        """Should return True for configured server."""
        config_data = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "context7": {
                    "type": "remote",
                    "url": "https://mcp.context7.com/mcp",
                }
            },
        }
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = MCPService()
        assert service.is_configured("context7", tmp_path) is True

    def test_is_configured_false(self, tmp_path: Path) -> None:
        """Should return False for non-configured server."""
        service = MCPService()
        assert service.is_configured("context7", tmp_path) is False


class TestMCPServiceRequiresAuth:
    """Tests for MCPService.requires_auth()."""

    def test_requires_auth_api_key(self) -> None:
        """Should return API_KEY auth type for context7."""
        service = MCPService()
        result = service.requires_auth("context7")

        assert isinstance(result, Success)
        assert result.value == MCPAuthType.API_KEY

    def test_requires_auth_oauth(self) -> None:
        """Should return OAUTH auth type for atlassian."""
        service = MCPService()
        result = service.requires_auth("atlassian")

        assert isinstance(result, Success)
        assert result.value == MCPAuthType.OAUTH

    def test_requires_auth_not_found(self) -> None:
        """Should return Failure for unknown server."""
        service = MCPService()
        result = service.requires_auth("unknown")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND
