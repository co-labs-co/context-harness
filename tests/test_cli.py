"""Tests for the CLI module."""

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

    def test_init_creates_directories(self, runner, tmp_path):
        """Test that init creates the expected directories."""
        result = runner.invoke(main, ["init", "--target", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".context-harness").is_dir()
        assert (tmp_path / ".opencode").is_dir()
        assert (tmp_path / ".opencode" / "agent").is_dir()

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
        assert (tmp_path / ".opencode" / "agent" / "docs-subagent.md").is_file()
        assert (tmp_path / ".opencode" / "agent" / "research-subagent.md").is_file()

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
        import os
        from pathlib import Path

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
