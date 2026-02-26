"""Tests for the CLI module."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from context_harness.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestCLI:
    """Tests for the main CLI."""

    def test_main_help(self, runner):
        """Test that --help works."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "ContextHarness CLI" in result.output

    def test_main_version(self, runner):
        """Test that --version works."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "context-harness" in result.output


class TestInitCommand:
    """Tests for the init command."""

    def test_init_help(self, runner):
        """Test that init --help works."""
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize ContextHarness" in result.output
        assert "--force" in result.output
        assert "--target" in result.output
        assert "--tool" in result.output

    def test_init_creates_directories(self, runner, tmp_path):
        """Test that init creates the expected directories."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".context-harness").is_dir()
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".opencode" / "agent").is_dir()
        assert (tmp_path / ".opencode" / "command").is_dir()
        # Claude Code directories should also be created by default
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / ".claude" / "agents").is_dir()
        assert (tmp_path / ".claude" / "commands").is_dir()

    def test_init_creates_files(self, runner, tmp_path):
        """Test that init creates the expected files."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Check .context-harness files
        assert (tmp_path / ".context-harness" / "README.md").is_file()
        assert (
            tmp_path / ".context-harness" / "templates" / "session-template.md"
        ).is_file()

        # Check .opencode/agent files
        assert (tmp_path / ".opencode" / "agent" / "context-harness.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "compaction-guide.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "contexts-subagent.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "docs-subagent.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "research-subagent.md").is_file()

        # Check .opencode/command files
        assert (tmp_path / ".opencode" / "command" / "ctx.md").is_file()
        assert (tmp_path / ".opencode" / "command" / "compact.md").is_file()
        assert (tmp_path / ".opencode" / "command" / "contexts.md").is_file()
        assert (tmp_path / ".opencode" / "command" / "issue.md").is_file()
        assert (tmp_path / ".opencode" / "command" / "pr.md").is_file()

    def test_init_fails_if_exists(self, runner, tmp_path):
        """Test that init fails if directories already exist."""
        # Create the directory first
        (tmp_path / ".context-harness").mkdir()

        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 1
        assert "already exist" in result.output

    def test_init_force_overwrites(self, runner, tmp_path):
        """Test that init --force overwrites existing files."""
        # Create the directory first
        (tmp_path / ".context-harness").mkdir()
        (tmp_path / ".context-harness" / "README.md").write_text(
            "old content", encoding="utf-8"
        )

        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert "successfully" in result.output

        # Verify the file was overwritten (use utf-8 encoding for Windows compatibility)
        content = (tmp_path / ".context-harness" / "README.md").read_text(
            encoding="utf-8"
        )
        assert "old content" not in content
        assert "ContextHarness" in content

    def test_init_idempotent_with_force(self, runner, tmp_path):
        """Test that init --force can be run multiple times."""
        # Run init twice with --force
        result1 = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result1.exit_code == 0

        result2 = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result2.exit_code == 0

        # Verify files still exist and are valid
        assert (tmp_path / ".context-harness" / "README.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "context-harness.md").is_file()

    def test_init_current_directory(self, runner, tmp_path):
        """Test that init works in current directory by default."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            # Check in current working directory (the isolated filesystem)
            cwd = Path(os.getcwd())
            assert (cwd / ".context-harness").is_dir()
            assert (cwd / ".opencode").is_dir()

    def test_init_output_messages(self, runner, tmp_path):
        """Test that init shows appropriate output messages."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert "ContextHarness" in result.output
        assert "successfully" in result.output
        assert "Next steps" in result.output

    def test_init_force_preserves_sessions(self, runner, tmp_path):
        """Test that init --force preserves existing sessions."""
        # First init
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Create a session with some content
        sessions_dir = tmp_path / ".context-harness" / "sessions" / "my-feature"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "SESSION.md"
        session_file.write_text("# My important session data\n", encoding="utf-8")

        # Run init --force (should preserve sessions)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify session was preserved
        assert sessions_dir.is_dir()
        assert session_file.is_file()
        content = session_file.read_text(encoding="utf-8")
        assert "My important session data" in content

    def test_init_force_updates_agent_files(self, runner, tmp_path):
        """Test that init --force updates agent files to latest version."""
        # First init
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Modify an agent file (simulating old version)
        agent_file = tmp_path / ".opencode" / "agent" / "context-harness.md"
        agent_file.write_text("# Old agent content\n", encoding="utf-8")

        # Run init --force (should update agent files)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify agent file was updated
        content = agent_file.read_text(encoding="utf-8")
        assert "Old agent content" not in content
        assert "ContextHarness" in content

    def test_init_force_preserves_user_skills(self, runner, tmp_path):
        """Test that init --force preserves user-created skills."""
        # First init
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Create a user skill (not part of template)
        user_skill_dir = tmp_path / ".opencode" / "skill" / "my-custom-skill"
        user_skill_dir.mkdir(parents=True)
        skill_file = user_skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: my-custom-skill\ndescription: My custom skill\n---\n# My Custom Skill\n",
            encoding="utf-8",
        )

        # Run init --force (should preserve user skill)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify user skill was preserved
        assert user_skill_dir.is_dir()
        assert skill_file.is_file()
        content = skill_file.read_text(encoding="utf-8")
        assert "my-custom-skill" in content

        # Verify template skill was updated
        template_skill = tmp_path / ".opencode" / "skill" / "skill-creator" / "SKILL.md"
        assert template_skill.is_file()

    def test_init_force_updates_template_skills(self, runner, tmp_path):
        """Test that init --force updates template skills to latest version."""
        # First init
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Modify a template skill (simulating old version)
        skill_file = tmp_path / ".opencode" / "skill" / "skill-creator" / "SKILL.md"
        skill_file.write_text("# Old skill content\n", encoding="utf-8")

        # Run init --force (should update template skill)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify template skill was updated
        content = skill_file.read_text(encoding="utf-8")
        assert "Old skill content" not in content
        assert "skill-creator" in content.lower() or "Skill Creator" in content

    def test_init_creates_contextignore(self, runner, tmp_path):
        """Test that init creates .contextignore file."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        contextignore = tmp_path / ".contextignore"
        assert contextignore.is_file()

    def test_init_force_preserves_contextignore(self, runner, tmp_path):
        """Test that init --force preserves existing .contextignore file."""
        # First init
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Customize .contextignore with user patterns
        contextignore = tmp_path / ".contextignore"
        custom_content = """# My custom ignore patterns
apps/legacy-app/
packages/deprecated/
*.generated.ts
"""
        contextignore.write_text(custom_content, encoding="utf-8")

        # Run init --force (should preserve .contextignore)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify .contextignore was preserved
        assert contextignore.is_file()
        content = contextignore.read_text(encoding="utf-8")
        assert "My custom ignore patterns" in content
        assert "apps/legacy-app/" in content
        assert "packages/deprecated/" in content

    def test_init_command_files_have_correct_frontmatter(self, runner, tmp_path):
        """Test that command files have correct frontmatter for OpenCode."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Check ctx.md
        ctx_content = (tmp_path / ".opencode" / "command" / "ctx.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in ctx_content
        assert "agent: context-harness" in ctx_content
        assert "$ARGUMENTS" in ctx_content  # Uses arguments placeholder

        # Check compact.md
        compact_content = (tmp_path / ".opencode" / "command" / "compact.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in compact_content
        assert "agent: context-harness" in compact_content

        # Check contexts.md (routes to contexts-subagent for context efficiency)
        contexts_content = (
            tmp_path / ".opencode" / "command" / "contexts.md"
        ).read_text(encoding="utf-8")
        assert "description:" in contexts_content
        assert "agent: contexts-subagent" in contexts_content

        # Check issue.md (GitHub issue management)
        issue_content = (tmp_path / ".opencode" / "command" / "issue.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in issue_content
        assert "agent: context-harness" in issue_content

        # Check pr.md (Pull request creation)
        pr_content = (tmp_path / ".opencode" / "command" / "pr.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in pr_content
        assert "agent: context-harness" in pr_content


class TestInitToolFlag:
    """Tests for the --tool flag on init command."""

    def test_init_tool_opencode_only(self, runner, tmp_path):
        """Test that --tool opencode creates only OpenCode directories."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "opencode"]
        )
        assert result.exit_code == 0

        # OpenCode directories should exist
        assert (tmp_path / ".context-harness").is_dir()
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".opencode" / "agent").is_dir()
        assert (tmp_path / ".opencode" / "command").is_dir()
        assert (tmp_path / ".opencode" / "skill").is_dir()

        # Claude Code directories should NOT exist
        assert not (tmp_path / ".claude").exists()
        assert not (tmp_path / ".mcp.json").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_init_tool_claude_code_only(self, runner, tmp_path):
        """Test that --tool claude-code creates only Claude Code directories."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "claude-code"]
        )
        assert result.exit_code == 0

        # Claude Code directories should exist
        assert (tmp_path / ".context-harness").is_dir()
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / ".claude" / "agents").is_dir()
        assert (tmp_path / ".claude" / "commands").is_dir()
        assert (tmp_path / ".claude" / "skills").is_dir()
        assert (tmp_path / ".mcp.json").is_file()
        assert (tmp_path / "CLAUDE.md").is_file()

        # OpenCode directories should NOT exist
        assert not (tmp_path / ".opencode").exists()
        assert not (tmp_path / "AGENTS.md").exists()
        assert not (tmp_path / "opencode.json").exists()

    def test_init_tool_both(self, runner, tmp_path):
        """Test that --tool both creates both OpenCode and Claude Code directories."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "both"]
        )
        assert result.exit_code == 0

        # OpenCode directories should exist
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".opencode" / "agent").is_dir()

        # Claude Code directories should exist
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / ".claude" / "agents").is_dir()
        assert (tmp_path / ".mcp.json").is_file()
        assert (tmp_path / "CLAUDE.md").is_file()

        # Shared directory should exist
        assert (tmp_path / ".context-harness").is_dir()

    def test_init_default_is_both(self, runner, tmp_path):
        """Test that init without --tool defaults to both."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Both tools should be installed
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".claude").is_dir()
        assert (tmp_path / "CLAUDE.md").is_file()
        assert (tmp_path / ".mcp.json").is_file()

    def test_init_force_upgrades_opencode_to_both(self, runner, tmp_path):
        """Test that --force on OpenCode-only install adds Claude Code."""
        # First install OpenCode only
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "opencode"]
        )
        assert result.exit_code == 0
        assert (tmp_path / ".opencode").is_dir()
        assert not (tmp_path / ".claude").exists()

        # Force reinstall without --tool (should upgrade to both)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Now both should exist
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".claude").is_dir()

    def test_init_force_upgrades_claude_to_both(self, runner, tmp_path):
        """Test that --force on Claude-only install adds OpenCode."""
        # First install Claude Code only
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "claude-code"]
        )
        assert result.exit_code == 0
        assert (tmp_path / ".claude").is_dir()
        assert not (tmp_path / ".opencode").exists()

        # Force reinstall without --tool (should upgrade to both)
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Now both should exist
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".claude").is_dir()

    def test_init_force_with_specific_tool(self, runner, tmp_path):
        """Test that --force with --tool only updates that tool."""
        # First install both
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Modify an OpenCode agent file
        agent_file = tmp_path / ".opencode" / "agent" / "context-harness.md"
        agent_file.write_text("# Modified OpenCode", encoding="utf-8")

        # Modify a Claude Code agent file
        claude_agent = tmp_path / ".claude" / "agents" / "context-harness.md"
        claude_agent.write_text("# Modified Claude", encoding="utf-8")

        # Force reinstall Claude Code only
        result = runner.invoke(
            main,
            ["init", "--force", "--target", str(tmp_path), "--tool", "claude-code"],
        )
        assert result.exit_code == 0

        # OpenCode file should still be modified
        assert agent_file.read_text(encoding="utf-8") == "# Modified OpenCode"

        # Claude Code file should be updated
        claude_content = claude_agent.read_text(encoding="utf-8")
        assert "Modified Claude" not in claude_content

    def test_init_force_preserves_claude_user_skills(self, runner, tmp_path):
        """Test that --force preserves user-created skills in .claude/skills/."""
        # First install both
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Create a user skill in Claude Code
        user_skill_dir = tmp_path / ".claude" / "skills" / "my-claude-skill"
        user_skill_dir.mkdir(parents=True)
        skill_file = user_skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\nname: my-claude-skill\ndescription: My custom skill\n---\n# My Claude Skill\n",
            encoding="utf-8",
        )

        # Run init --force
        result = runner.invoke(main, ["init", "--force", "--target", str(tmp_path)])
        assert result.exit_code == 0

        # Verify user skill was preserved
        assert user_skill_dir.is_dir()
        assert skill_file.is_file()
        content = skill_file.read_text(encoding="utf-8")
        assert "my-claude-skill" in content

    def test_init_claude_command_files_have_correct_frontmatter(self, runner, tmp_path):
        """Test that Claude Code command files have correct frontmatter."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "claude-code"]
        )
        assert result.exit_code == 0

        # Check ctx.md
        ctx_content = (tmp_path / ".claude" / "commands" / "ctx.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in ctx_content
        assert "allowed-tools:" in ctx_content

        # Check compact.md
        compact_content = (tmp_path / ".claude" / "commands" / "compact.md").read_text(
            encoding="utf-8"
        )
        assert "description:" in compact_content

        # Check contexts.md
        contexts_content = (
            tmp_path / ".claude" / "commands" / "contexts.md"
        ).read_text(encoding="utf-8")
        assert "description:" in contexts_content

    def test_init_claude_mcp_json_structure(self, runner, tmp_path):
        """Test that .mcp.json has correct structure for Claude Code."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "claude-code"]
        )
        assert result.exit_code == 0

        mcp_path = tmp_path / ".mcp.json"
        assert mcp_path.is_file()

        config = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert "mcpServers" in config
        assert "context7" in config["mcpServers"]
        # Claude Code uses command-based format
        assert config["mcpServers"]["context7"]["command"] == "npx"
        assert "@context7/mcp-server" in config["mcpServers"]["context7"]["args"]

    def test_init_invalid_tool_rejected(self, runner, tmp_path):
        """Test that invalid --tool values are rejected."""
        result = runner.invoke(
            main, ["init", "--target", str(tmp_path), "--tool", "invalid"]
        )
        assert result.exit_code != 0
        # Click should reject the invalid choice
        assert "Invalid value" in result.output or "invalid" in result.output.lower()


class TestMCPCommand:
    """Tests for the mcp command group."""

    def test_mcp_help(self, runner):
        """Test that mcp --help works."""
        result = runner.invoke(main, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "Manage MCP server configurations" in result.output

    def test_mcp_add_help(self, runner):
        """Test that mcp add --help works."""
        result = runner.invoke(main, ["mcp", "add", "--help"])
        assert result.exit_code == 0
        assert "Add an MCP server" in result.output
        assert "--api-key" in result.output
        assert "--target" in result.output

    def test_mcp_list_help(self, runner):
        """Test that mcp list --help works."""
        result = runner.invoke(main, ["mcp", "list", "--help"])
        assert result.exit_code == 0
        assert "List configured MCP servers" in result.output
        assert "--target" in result.output

    def test_mcp_add_context7_creates_opencode_json(self, runner, tmp_path):
        """Test that mcp add context7 creates opencode.json."""
        result = runner.invoke(
            main, ["mcp", "add", "context7", "--target", str(tmp_path)]
        )
        assert result.exit_code == 0

        config_path = tmp_path / "opencode.json"
        assert config_path.is_file()

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert "$schema" in config
        assert "mcp" in config
        assert "context7" in config["mcp"]
        assert config["mcp"]["context7"]["type"] == "remote"
        assert "context7.com" in config["mcp"]["context7"]["url"]

    def test_mcp_add_context7_with_api_key(self, runner, tmp_path):
        """Test that mcp add context7 --api-key adds the API key."""
        result = runner.invoke(
            main,
            [
                "mcp",
                "add",
                "context7",
                "--api-key",
                "test-key-123",
                "--target",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0

        config_path = tmp_path / "opencode.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        assert "headers" in config["mcp"]["context7"]
        assert (
            config["mcp"]["context7"]["headers"]["CONTEXT7_API_KEY"] == "test-key-123"
        )

    def test_mcp_add_preserves_existing_config(self, runner, tmp_path):
        """Test that mcp add preserves existing opencode.json content."""
        # Create existing opencode.json with custom settings
        config_path = tmp_path / "opencode.json"
        existing_config = {
            "$schema": "https://opencode.ai/config.json",
            "theme": "dark",
            "mcp": {
                "other-server": {"type": "local", "command": ["some-cmd"]},
            },
        }
        config_path.write_text(json.dumps(existing_config, indent=2), encoding="utf-8")

        result = runner.invoke(
            main, ["mcp", "add", "context7", "--target", str(tmp_path)]
        )
        assert result.exit_code == 0

        config = json.loads(config_path.read_text(encoding="utf-8"))

        # Verify existing content preserved
        assert config["theme"] == "dark"
        assert "other-server" in config["mcp"]

        # Verify context7 added
        assert "context7" in config["mcp"]

    def test_mcp_add_already_exists_same_config(self, runner, tmp_path):
        """Test that mcp add detects existing identical config."""
        # First add
        runner.invoke(main, ["mcp", "add", "context7", "--target", str(tmp_path)])

        # Second add (should report already exists)
        result = runner.invoke(
            main, ["mcp", "add", "context7", "--target", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "already configured" in result.output

    def test_mcp_add_updates_existing_config(self, runner, tmp_path):
        """Test that mcp add updates config when adding API key."""
        # First add without API key
        runner.invoke(main, ["mcp", "add", "context7", "--target", str(tmp_path)])

        # Second add with API key (should update)
        result = runner.invoke(
            main,
            [
                "mcp",
                "add",
                "context7",
                "--api-key",
                "new-key",
                "--target",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0

        config_path = tmp_path / "opencode.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        assert "headers" in config["mcp"]["context7"]
        assert config["mcp"]["context7"]["headers"]["CONTEXT7_API_KEY"] == "new-key"

    def test_mcp_list_empty(self, runner, tmp_path):
        """Test that mcp list handles missing config files."""
        result = runner.invoke(main, ["mcp", "list", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert "No MCP servers configured" in result.output

    def test_mcp_list_shows_configured_servers(self, runner, tmp_path):
        """Test that mcp list shows configured servers."""
        # Add context7
        runner.invoke(main, ["mcp", "add", "context7", "--target", str(tmp_path)])

        result = runner.invoke(main, ["mcp", "list", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert "context7" in result.output
        assert "remote" in result.output

    def test_mcp_list_shows_api_key_indicator(self, runner, tmp_path):
        """Test that mcp list shows indicator when API key is configured."""
        # Add context7 with API key
        runner.invoke(
            main,
            [
                "mcp",
                "add",
                "context7",
                "--api-key",
                "test-key",
                "--target",
                str(tmp_path),
            ],
        )

        result = runner.invoke(main, ["mcp", "list", "--target", str(tmp_path)])
        assert result.exit_code == 0
        # The key indicator emoji should be present
        assert "🔑" in result.output

    def test_mcp_add_invalid_server(self, runner, tmp_path):
        """Test that mcp add rejects unknown server names."""
        result = runner.invoke(
            main, ["mcp", "add", "unknown-server", "--target", str(tmp_path)]
        )
        # Click should reject the invalid choice
        assert result.exit_code != 0

    def test_mcp_current_directory(self, runner, tmp_path):
        """Test that mcp add works in current directory by default."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["mcp", "add", "context7"])
            assert result.exit_code == 0

            cwd = Path(os.getcwd())
            assert (cwd / "opencode.json").is_file()
