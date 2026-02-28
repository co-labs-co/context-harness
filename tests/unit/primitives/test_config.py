"""Unit tests for primitives.config module."""

import pytest
from pathlib import Path

from context_harness.primitives.config import (
    AgentConfig,
    CommandConfig,
    OpenCodeConfig,
    ProjectConfig,
)
from context_harness.primitives.mcp import MCPServerType


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_create_minimal(self):
        """Test creating AgentConfig with no arguments."""
        config = AgentConfig()
        assert config.system_prompt is None
        assert config.tools is None
        assert config.model is None

    def test_create_full(self):
        """Test creating AgentConfig with all fields."""
        config = AgentConfig(
            system_prompt="agent.md",
            tools=["read", "write", "bash"],
            model="claude-3.5-sonnet",
        )
        assert config.system_prompt == "agent.md"
        assert config.tools == ["read", "write", "bash"]
        assert config.model == "claude-3.5-sonnet"

    def test_frozen(self):
        """Test that AgentConfig is immutable."""
        config = AgentConfig(system_prompt="test.md")
        with pytest.raises(AttributeError):
            config.system_prompt = "other.md"


class TestCommandConfig:
    """Tests for CommandConfig dataclass."""

    def test_create_minimal(self):
        """Test creating CommandConfig with required fields only."""
        config = CommandConfig(description="Test command")
        assert config.description == "Test command"
        assert config.agent is None
        assert config.prompt is None

    def test_create_full(self):
        """Test creating CommandConfig with all fields."""
        config = CommandConfig(
            description="Run tests",
            agent="test-agent",
            prompt="Run all tests and report results",
        )
        assert config.description == "Run tests"
        assert config.agent == "test-agent"
        assert config.prompt == "Run all tests and report results"

    def test_frozen(self):
        """Test that CommandConfig is immutable."""
        config = CommandConfig(description="test")
        with pytest.raises(AttributeError):
            config.description = "other"


class TestOpenCodeConfig:
    """Tests for OpenCodeConfig dataclass."""

    def test_create_empty(self):
        """Test creating empty OpenCodeConfig."""
        config = OpenCodeConfig()
        assert config.schema_version == "1.0"
        assert config.mcp == {}
        assert config.agents == {}
        assert config.commands == {}
        assert config.skills == {}
        assert config.project_context is None
        assert config.raw_data == {}

    def test_from_dict_empty(self):
        """Test parsing empty dict."""
        config = OpenCodeConfig.from_dict({})
        assert config.schema_version == "1.0"
        assert config.mcp == {}

    def test_from_dict_with_mcp(self):
        """Test parsing MCP configuration."""
        data = {
            "mcp": {
                "context7": {
                    "url": "https://mcp.context7.com/sse",
                    "type": "remote",
                },
                "local-server": {
                    "command": "npx",
                    "args": ["-y", "@local/server"],
                    "type": "local",
                },
            }
        }
        config = OpenCodeConfig.from_dict(data)

        assert "context7" in config.mcp
        assert config.mcp["context7"].url == "https://mcp.context7.com/sse"
        assert config.mcp["context7"].server_type == MCPServerType.REMOTE

        assert "local-server" in config.mcp
        assert config.mcp["local-server"].command == "npx"
        assert config.mcp["local-server"].args == ["-y", "@local/server"]
        assert config.mcp["local-server"].server_type == MCPServerType.LOCAL

    def test_from_dict_with_agents(self):
        """Test parsing agent configuration."""
        data = {
            "agents": {
                "main": {
                    "systemPrompt": ".opencode/agents/main.md",
                    "tools": ["read", "write"],
                    "model": "claude-3.5-sonnet",
                }
            }
        }
        config = OpenCodeConfig.from_dict(data)

        assert "main" in config.agents
        assert config.agents["main"].system_prompt == ".opencode/agents/main.md"
        assert config.agents["main"].tools == ["read", "write"]
        assert config.agents["main"].model == "claude-3.5-sonnet"

    def test_from_dict_with_commands(self):
        """Test parsing command configuration."""
        data = {
            "commands": {
                "test": {
                    "description": "Run tests",
                    "agent": "test-agent",
                    "prompt": "Run pytest",
                }
            }
        }
        config = OpenCodeConfig.from_dict(data)

        assert "test" in config.commands
        assert config.commands["test"].description == "Run tests"
        assert config.commands["test"].agent == "test-agent"
        assert config.commands["test"].prompt == "Run pytest"

    def test_from_dict_preserves_raw_data(self):
        """Test that raw_data preserves original dict."""
        data = {
            "$schema": "https://opencode.ai/schema.json",
            "mcp": {"test": {"url": "http://test.com"}},
            "customField": "custom value",
        }
        config = OpenCodeConfig.from_dict(data)
        assert config.raw_data == data
        assert config.raw_data["customField"] == "custom value"

    def test_to_dict_roundtrip(self):
        """Test that to_dict produces valid config for MCP."""
        data = {
            "mcp": {
                "context7": {
                    "url": "https://mcp.context7.com/sse",
                    "type": "remote",
                    "headers": {"Authorization": "Bearer token"},
                }
            }
        }
        config = OpenCodeConfig.from_dict(data)
        result = config.to_dict()

        assert "mcp" in result
        assert "context7" in result["mcp"]
        assert result["mcp"]["context7"]["url"] == "https://mcp.context7.com/sse"
        assert result["mcp"]["context7"]["type"] == "remote"

    def test_to_dict_includes_schema(self):
        """Test that to_dict includes schema version."""
        config = OpenCodeConfig(schema_version="https://opencode.ai/schema.json")
        result = config.to_dict()
        assert result["$schema"] == "https://opencode.ai/schema.json"


class TestProjectConfig:
    """Tests for ProjectConfig dataclass."""

    def test_from_project_root(self):
        """Test creating ProjectConfig from project root."""
        root = Path("/home/user/myproject")
        config = ProjectConfig.from_project_root(root)

        assert config.project_root == root
        assert config.context_harness_dir == root / ".context-harness"
        assert config.opencode_dir == root / ".opencode"
        assert config.claude_dir == root / ".claude"
        assert config.sessions_dir == root / ".context-harness" / "sessions"
        assert config.templates_dir == root / ".context-harness" / "templates"
        assert (
            config.skills_dir == root / ".opencode" / "skill"
        )  # singular for OpenCode
        assert (
            config.claude_skills_dir == root / ".claude" / "skills"
        )  # plural for Claude
        assert config.baseline_dir == root / ".context-harness" / "baseline"
        assert (
            config.project_context_path
            == root / ".context-harness" / "PROJECT-CONTEXT.md"
        )
        assert config.opencode_json_path == root / "opencode.json"
        assert config.mcp_json_path == root / ".mcp.json"
        assert config.agents_md_path == root / "AGENTS.md"
        assert config.claude_md_path == root / "CLAUDE.md"
        assert config.harness_config_path == root / ".context-harness" / "config.json"

    def test_session_path(self):
        """Test getting session directory path."""
        config = ProjectConfig.from_project_root(Path("/project"))
        path = config.session_path("login-feature")
        assert path == Path("/project/.context-harness/sessions/login-feature")

    def test_session_file(self):
        """Test getting session file path."""
        config = ProjectConfig.from_project_root(Path("/project"))
        path = config.session_file("login-feature")
        assert path == Path(
            "/project/.context-harness/sessions/login-feature/SESSION.md"
        )

    def test_ensure_directories(self):
        """Test getting list of directories to create."""
        config = ProjectConfig.from_project_root(Path("/project"))
        dirs = config.ensure_directories()

        assert len(dirs) == 6
        assert config.context_harness_dir in dirs
        assert config.sessions_dir in dirs
        assert config.templates_dir in dirs
        assert config.opencode_dir in dirs
        assert config.skills_dir in dirs
        assert config.baseline_dir in dirs

    def test_frozen(self):
        """Test that ProjectConfig is immutable."""
        config = ProjectConfig.from_project_root(Path("/project"))
        with pytest.raises(AttributeError):
            config.project_root = Path("/other")
