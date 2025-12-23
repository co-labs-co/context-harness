"""Tests for the skills module."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from context_harness.cli import main
from context_harness.skills import (
    SkillResult,
    SkillInfo,
    parse_skill_info,
    _validate_skill,
    _parse_skill_frontmatter,
)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_skill_dir(tmp_path):
    """Create a sample skill directory for testing."""
    skill_dir = tmp_path / ".opencode" / "skill" / "test-skill"
    skill_dir.mkdir(parents=True)

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test-skill
description: A test skill for unit testing
version: 1.0.0
---

# Test Skill

This is a test skill.
""",
        encoding="utf-8",
    )

    # Add optional directories
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")

    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "helper.py").write_text(
        "# Helper script\n", encoding="utf-8"
    )

    return skill_dir


@pytest.fixture
def sample_registry():
    """Sample skills registry data."""
    return {
        "schema_version": "1.0",
        "skills": [
            {
                "name": "react-forms",
                "description": "React form handling with validation",
                "version": "1.0.0",
                "author": "testuser",
                "tags": ["react", "forms", "frontend"],
                "path": "skill/react-forms",
                "min_context_harness_version": "0.3.0",
            },
            {
                "name": "django-auth",
                "description": "Django authentication patterns",
                "version": "2.0.0",
                "author": "testuser",
                "tags": ["django", "auth", "backend"],
                "path": "skill/django-auth",
            },
        ],
    }


class TestSkillInfo:
    """Tests for SkillInfo dataclass and parsing."""

    def test_parse_skill_info_complete(self, sample_registry):
        """Test parsing complete skill info."""
        skill_data = sample_registry["skills"][0]
        info = parse_skill_info(skill_data)

        assert info.name == "react-forms"
        assert info.description == "React form handling with validation"
        assert info.version == "1.0.0"
        assert info.author == "testuser"
        assert info.tags == ["react", "forms", "frontend"]
        assert info.path == "skill/react-forms"
        assert info.min_context_harness_version == "0.3.0"

    def test_parse_skill_info_minimal(self):
        """Test parsing minimal skill info."""
        skill_data = {
            "name": "minimal-skill",
            "description": "Minimal",
        }
        info = parse_skill_info(skill_data)

        assert info.name == "minimal-skill"
        assert info.description == "Minimal"
        assert info.version == "0.0.0"
        assert info.author == "unknown"
        assert info.tags == []
        assert info.path == ""
        assert info.min_context_harness_version is None


class TestSkillValidation:
    """Tests for skill validation functions."""

    def test_validate_skill_valid(self, sample_skill_dir):
        """Test validation passes for valid skill."""
        assert _validate_skill(sample_skill_dir, quiet=True) is True

    def test_validate_skill_missing_skill_md(self, tmp_path):
        """Test validation fails when SKILL.md is missing."""
        skill_dir = tmp_path / "no-skill"
        skill_dir.mkdir()

        assert _validate_skill(skill_dir, quiet=True) is False

    def test_validate_skill_missing_frontmatter(self, tmp_path):
        """Test validation fails when frontmatter is missing."""
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")

        assert _validate_skill(skill_dir, quiet=True) is False

    def test_validate_skill_missing_name(self, tmp_path):
        """Test validation fails when name field is missing."""
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
description: Missing name
---
# Skill
""",
            encoding="utf-8",
        )

        assert _validate_skill(skill_dir, quiet=True) is False

    def test_validate_skill_missing_description(self, tmp_path):
        """Test validation fails when description field is missing."""
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: missing-desc
---
# Skill
""",
            encoding="utf-8",
        )

        assert _validate_skill(skill_dir, quiet=True) is False


class TestFrontmatterParsing:
    """Tests for frontmatter parsing."""

    def test_parse_skill_frontmatter(self, sample_skill_dir):
        """Test parsing frontmatter from SKILL.md."""
        frontmatter = _parse_skill_frontmatter(sample_skill_dir)

        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "A test skill for unit testing"
        assert frontmatter["version"] == "1.0.0"

    def test_parse_skill_frontmatter_multiline_description(self, tmp_path):
        """Test parsing frontmatter with multiline description."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: multiline
description: First line
version: 1.0.0
---
# Content
""",
            encoding="utf-8",
        )

        frontmatter = _parse_skill_frontmatter(skill_dir)
        assert frontmatter["name"] == "multiline"
        assert "First line" in frontmatter["description"]


class TestSkillCLI:
    """Tests for skill CLI commands."""

    def test_skill_help(self, runner):
        """Test that skill --help works."""
        result = runner.invoke(main, ["skill", "--help"])
        assert result.exit_code == 0
        assert "Manage ContextHarness skills" in result.output

    def test_skill_list_help(self, runner):
        """Test that skill list --help works."""
        result = runner.invoke(main, ["skill", "list", "--help"])
        assert result.exit_code == 0
        assert "List available skills" in result.output
        assert "--tags" in result.output

    def test_skill_info_help(self, runner):
        """Test that skill info --help works."""
        result = runner.invoke(main, ["skill", "info", "--help"])
        assert result.exit_code == 0
        assert "Show detailed information" in result.output

    def test_skill_install_help(self, runner):
        """Test that skill install --help works."""
        result = runner.invoke(main, ["skill", "install", "--help"])
        assert result.exit_code == 0
        assert "Install a skill" in result.output
        assert "--target" in result.output
        assert "--force" in result.output

    def test_skill_extract_help(self, runner):
        """Test that skill extract --help works."""
        result = runner.invoke(main, ["skill", "extract", "--help"])
        assert result.exit_code == 0
        assert "Extract a local skill" in result.output
        assert "--source" in result.output

    @patch("context_harness.skills.check_gh_auth")
    @patch("context_harness.skills.check_repo_access")
    def test_skill_list_auth_failure(self, mock_repo_access, mock_auth, runner):
        """Test skill list handles auth failure."""
        mock_auth.return_value = False

        result = runner.invoke(main, ["skill", "list"])
        # Should complete but show no skills
        assert result.exit_code == 0

    @patch("context_harness.skills.check_gh_auth")
    @patch("context_harness.skills.check_repo_access")
    @patch("context_harness.skills.subprocess.run")
    def test_skill_list_with_registry(
        self, mock_run, mock_repo_access, mock_auth, runner, sample_registry
    ):
        """Test skill list with successful registry fetch."""
        mock_auth.return_value = True
        mock_repo_access.return_value = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_registry)
        mock_run.return_value = mock_result

        result = runner.invoke(main, ["skill", "list"])
        assert result.exit_code == 0

    def test_skill_install_not_found(self, runner, tmp_path):
        """Test skill install handles not found."""
        with patch("context_harness.skills.get_skill_info") as mock_info:
            mock_info.return_value = None

            result = runner.invoke(
                main, ["skill", "install", "nonexistent", "--target", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_skill_extract_not_found(self, runner, tmp_path):
        """Test skill extract handles not found skill."""
        with (
            patch("context_harness.skills.check_gh_auth") as mock_auth,
            patch("context_harness.skills.check_repo_access") as mock_access,
        ):
            mock_auth.return_value = True
            mock_access.return_value = True

            result = runner.invoke(
                main, ["skill", "extract", "nonexistent", "--source", str(tmp_path)]
            )
            assert result.exit_code == 1
            assert "not found" in result.output


class TestSkillInstallation:
    """Tests for skill installation functionality."""

    @patch("context_harness.skills.get_skill_info")
    @patch("context_harness.skills._fetch_directory_recursive")
    def test_install_skill_success(self, mock_fetch, mock_info, tmp_path):
        """Test successful skill installation."""
        from context_harness.skills import install_skill

        mock_info.return_value = SkillInfo(
            name="test-skill",
            description="Test",
            version="1.0.0",
            author="test",
            tags=[],
            path="skill/test-skill",
        )
        mock_fetch.return_value = True

        result = install_skill("test-skill", target=str(tmp_path), quiet=True)
        assert result == SkillResult.SUCCESS

    @patch("context_harness.skills.get_skill_info")
    def test_install_skill_already_exists(self, mock_info, tmp_path):
        """Test install skill when already exists."""
        from context_harness.skills import install_skill

        mock_info.return_value = SkillInfo(
            name="test-skill",
            description="Test",
            version="1.0.0",
            author="test",
            tags=[],
            path="skill/test-skill",
        )

        # Create existing skill
        skill_dir = tmp_path / ".opencode" / "skill" / "test-skill"
        skill_dir.mkdir(parents=True)

        result = install_skill("test-skill", target=str(tmp_path), quiet=True)
        assert result == SkillResult.ALREADY_EXISTS

    @patch("context_harness.skills.get_skill_info")
    @patch("context_harness.skills._fetch_directory_recursive")
    def test_install_skill_force_overwrites(self, mock_fetch, mock_info, tmp_path):
        """Test install skill with force overwrites existing."""
        from context_harness.skills import install_skill

        mock_info.return_value = SkillInfo(
            name="test-skill",
            description="Test",
            version="1.0.0",
            author="test",
            tags=[],
            path="skill/test-skill",
        )
        mock_fetch.return_value = True

        # Create existing skill
        skill_dir = tmp_path / ".opencode" / "skill" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "old-file.txt").write_text("old", encoding="utf-8")

        result = install_skill(
            "test-skill", target=str(tmp_path), force=True, quiet=True
        )
        assert result == SkillResult.SUCCESS
        # Old file should be gone after force reinstall
        assert not (skill_dir / "old-file.txt").exists()


class TestSkillExtraction:
    """Tests for skill extraction functionality."""

    @patch("context_harness.skills.check_gh_auth")
    def test_extract_skill_auth_failure(self, mock_auth, sample_skill_dir):
        """Test extract skill handles auth failure."""
        from context_harness.skills import extract_skill

        mock_auth.return_value = False

        result, pr_url = extract_skill(
            "test-skill",
            source_path=str(sample_skill_dir.parent.parent.parent),
            quiet=True,
        )
        assert result == SkillResult.AUTH_ERROR
        assert pr_url is None

    @patch("context_harness.skills.check_gh_auth")
    @patch("context_harness.skills.check_repo_access")
    def test_extract_skill_not_found(self, mock_access, mock_auth, tmp_path):
        """Test extract skill handles missing skill."""
        from context_harness.skills import extract_skill

        mock_auth.return_value = True
        mock_access.return_value = True

        result, pr_url = extract_skill(
            "nonexistent",
            source_path=str(tmp_path),
            quiet=True,
        )
        assert result == SkillResult.NOT_FOUND
        assert pr_url is None

    @patch("context_harness.skills.check_gh_auth")
    @patch("context_harness.skills.check_repo_access")
    def test_extract_skill_invalid_skill(self, mock_access, mock_auth, tmp_path):
        """Test extract skill handles invalid skill structure."""
        from context_harness.skills import extract_skill

        mock_auth.return_value = True
        mock_access.return_value = True

        # Create invalid skill (missing required fields)
        skill_dir = tmp_path / ".opencode" / "skill" / "invalid-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")

        result, pr_url = extract_skill(
            "invalid-skill",
            source_path=str(tmp_path),
            quiet=True,
        )
        assert result == SkillResult.ERROR
        assert pr_url is None
