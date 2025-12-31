"""Unit tests for ConfigService."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from context_harness.primitives import (
    ErrorCode,
    Failure,
    OpenCodeConfig,
    Success,
)
from context_harness.services import ConfigService


class TestConfigServiceLoad:
    """Tests for ConfigService.load()."""

    def test_load_existing_config(self, tmp_path: Path) -> None:
        """Should load valid opencode.json."""
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

        service = ConfigService()
        result = service.load(tmp_path)

        assert isinstance(result, Success)
        assert "context7" in result.value.mcp

    def test_load_missing_config(self, tmp_path: Path) -> None:
        """Should return Failure for missing config."""
        service = ConfigService()
        result = service.load(tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.CONFIG_MISSING

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Should return Failure for invalid JSON."""
        config_path = tmp_path / "opencode.json"
        config_path.write_text("{ invalid json }")

        service = ConfigService()
        result = service.load(tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.CONFIG_INVALID


class TestConfigServiceSave:
    """Tests for ConfigService.save()."""

    def test_save_new_config(self, tmp_path: Path) -> None:
        """Should save new opencode.json."""
        config = OpenCodeConfig()

        service = ConfigService()
        result = service.save(config, tmp_path)

        assert isinstance(result, Success)
        assert (tmp_path / "opencode.json").exists()

        # Verify content
        saved_data = json.loads((tmp_path / "opencode.json").read_text())
        assert "$schema" in saved_data

    def test_save_with_mcp(self, tmp_path: Path) -> None:
        """Should save config with MCP servers."""
        from context_harness.primitives import MCPServerConfig, MCPServerType

        config = OpenCodeConfig(
            mcp={
                "context7": MCPServerConfig(
                    name="context7",
                    server_type=MCPServerType.REMOTE,
                    url="https://mcp.context7.com/mcp",
                )
            }
        )

        service = ConfigService()
        result = service.save(config, tmp_path)

        assert isinstance(result, Success)

        # Verify content
        saved_data = json.loads((tmp_path / "opencode.json").read_text())
        assert "mcp" in saved_data
        assert "context7" in saved_data["mcp"]


class TestConfigServiceLoadOrCreate:
    """Tests for ConfigService.load_or_create()."""

    def test_load_or_create_existing(self, tmp_path: Path) -> None:
        """Should load existing config."""
        config_data = {"$schema": "https://opencode.ai/config.json"}
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = ConfigService()
        result = service.load_or_create(tmp_path)

        assert isinstance(result, Success)

    def test_load_or_create_missing(self, tmp_path: Path) -> None:
        """Should return empty config when missing."""
        service = ConfigService()
        result = service.load_or_create(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value.mcp) == 0


class TestConfigServiceMCPOperations:
    """Tests for MCP-related ConfigService methods."""

    def test_update_mcp_new_server(self, tmp_path: Path) -> None:
        """Should add new MCP server."""
        service = ConfigService()
        result = service.update_mcp(
            "context7",
            {
                "type": "remote",
                "url": "https://mcp.context7.com/mcp",
            },
            tmp_path,
        )

        assert isinstance(result, Success)
        assert "context7" in result.value.mcp

    def test_update_mcp_existing_server(self, tmp_path: Path) -> None:
        """Should update existing MCP server."""
        # Create initial config
        config_data = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "context7": {
                    "type": "remote",
                    "url": "https://old-url.com",
                }
            },
        }
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = ConfigService()
        result = service.update_mcp(
            "context7",
            {
                "type": "remote",
                "url": "https://mcp.context7.com/mcp",
            },
            tmp_path,
        )

        assert isinstance(result, Success)
        assert result.value.mcp["context7"].url == "https://mcp.context7.com/mcp"

    def test_remove_mcp_existing(self, tmp_path: Path) -> None:
        """Should remove existing MCP server."""
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

        service = ConfigService()
        result = service.remove_mcp("context7", tmp_path)

        assert isinstance(result, Success)
        assert "context7" not in result.value.mcp

    def test_remove_mcp_not_found(self, tmp_path: Path) -> None:
        """Should return Failure for non-existent server."""
        config_data = {"$schema": "https://opencode.ai/config.json", "mcp": {}}
        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps(config_data))

        service = ConfigService()
        result = service.remove_mcp("nonexistent", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND


class TestConfigServiceExists:
    """Tests for ConfigService.exists()."""

    def test_exists_true(self, tmp_path: Path) -> None:
        """Should return True when config exists."""
        config_path = tmp_path / "opencode.json"
        config_path.write_text("{}")

        service = ConfigService()
        assert service.exists(tmp_path) is True

    def test_exists_false(self, tmp_path: Path) -> None:
        """Should return False when config missing."""
        service = ConfigService()
        assert service.exists(tmp_path) is False
