"""Tests for the skills module."""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from context_harness.cli import main
from context_harness.skills import (
    SkillResult,
    SkillInfo,
    LocalSkillInfo,
    parse_skill_info,
    list_local_skills,
    _validate_skill,
    _parse_skill_frontmatter,
    _truncate_description,
    _fetch_directory_recursive,
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


class TestTruncateDescription:
    """Tests for description truncation."""

    def test_truncate_short_text(self):
        """Test that short text is not truncated."""
        result = _truncate_description("Short text", 50)
        assert result == "Short text"

    def test_truncate_exact_length(self):
        """Test text at exact max length is not truncated."""
        text = "A" * 50
        result = _truncate_description(text, 50)
        assert result == text

    def test_truncate_long_text_at_word_boundary(self):
        """Test truncation at word boundary."""
        text = "This is a longer text that needs to be truncated at a word boundary"
        result = _truncate_description(text, 30)
        assert result.endswith("...")
        assert len(result) <= 30
        assert "truncat" not in result  # Shouldn't cut mid-word

    def test_truncate_preserves_word_boundary(self):
        """Test that truncation respects word boundaries."""
        text = "Word1 Word2 Word3 Word4 Word5"
        result = _truncate_description(text, 20)
        assert result.endswith("...")
        assert " " not in result[-4:]  # No space right before ellipsis

    def test_truncate_no_spaces(self):
        """Test truncation when no suitable word boundary exists."""
        text = "Verylongwordwithoutanyspaces"
        result = _truncate_description(text, 15)
        assert result.endswith("...")
        assert len(result) <= 15


class TestFetchDirectoryRecursive:
    """Tests for recursive directory fetching from GitHub."""

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_single_file(self, mock_run, tmp_path):
        """Test fetching when API returns a single file (not in array)."""
        # GitHub API returns a dict (not list) when path points to a file
        single_file_response = {
            "name": "SKILL.md",
            "path": "skill/test/SKILL.md",
            "type": "file",
            "url": "https://api.github.com/repos/test/test/contents/skill/test/SKILL.md",
        }

        file_content = b"# Test Skill\n\nThis is test content."

        def mock_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            # First call uses text=True for JSON response
            if kwargs.get("text"):
                result.stdout = json.dumps(single_file_response)
            else:
                # File content call returns bytes
                result.stdout = file_content
            return result

        mock_run.side_effect = mock_subprocess_run

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is True
        assert (dest / "SKILL.md").exists()
        assert (dest / "SKILL.md").read_bytes() == file_content

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_directory_with_files(self, mock_run, tmp_path):
        """Test fetching a directory containing multiple files."""
        directory_response = [
            {
                "name": "SKILL.md",
                "path": "skill/test/SKILL.md",
                "type": "file",
                "url": "https://api.github.com/repos/test/repo/contents/skill/test/SKILL.md",
            },
            {
                "name": "README.md",
                "path": "skill/test/README.md",
                "type": "file",
                "url": "https://api.github.com/repos/test/repo/contents/skill/test/README.md",
            },
        ]

        file_call_count = [0]

        def mock_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0

            if kwargs.get("text"):
                # Directory listing call
                result.stdout = json.dumps(directory_response)
            else:
                # File content calls
                file_call_count[0] += 1
                if file_call_count[0] == 1:
                    result.stdout = b"# SKILL content"
                else:
                    result.stdout = b"# README content"
            return result

        mock_run.side_effect = mock_subprocess_run

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is True
        assert (dest / "SKILL.md").exists()
        assert (dest / "README.md").exists()

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_nested_directory(self, mock_run, tmp_path):
        """Test fetching a directory containing subdirectories."""
        # Main directory contains a file and a subdirectory
        main_dir_response = [
            {
                "name": "SKILL.md",
                "path": "skill/test/SKILL.md",
                "type": "file",
                "url": "https://api.github.com/repos/test/repo/contents/skill/test/SKILL.md",
            },
            {
                "name": "scripts",
                "path": "skill/test/scripts",
                "type": "dir",
            },
        ]

        scripts_dir_response = [
            {
                "name": "helper.py",
                "path": "skill/test/scripts/helper.py",
                "type": "file",
                "url": "https://api.github.com/repos/test/repo/contents/skill/test/scripts/helper.py",
            },
        ]

        text_call_count = [0]

        def mock_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0

            if kwargs.get("text"):
                # Directory listing calls
                text_call_count[0] += 1
                api_path = args[2] if len(args) > 2 else ""

                if "scripts" in api_path:
                    result.stdout = json.dumps(scripts_dir_response)
                else:
                    result.stdout = json.dumps(main_dir_response)
            else:
                # File content calls - just return generic content
                result.stdout = b"# File content"
            return result

        mock_run.side_effect = mock_subprocess_run

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is True
        assert (dest / "SKILL.md").exists()
        assert (dest / "scripts").is_dir()
        assert (dest / "scripts" / "helper.py").exists()

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_api_error(self, mock_run, tmp_path):
        """Test handling of GitHub API errors."""
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh"], stderr="Not found"
        )

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is False

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_json_decode_error(self, mock_run, tmp_path):
        """Test handling of invalid JSON response."""
        result = MagicMock()
        result.returncode = 0
        result.stdout = "not valid json {"
        mock_run.return_value = result

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is False

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_creates_destination_directory(self, mock_run, tmp_path):
        """Test that destination directory is created if it doesn't exist."""
        single_file_response = {
            "name": "SKILL.md",
            "path": "skill/test/SKILL.md",
            "type": "file",
            "url": "https://api.github.com/repos/test/repo/contents/skill/test/SKILL.md",
        }

        def mock_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if kwargs.get("text"):
                result.stdout = json.dumps(single_file_response)
            else:
                result.stdout = b"content"
            return result

        mock_run.side_effect = mock_subprocess_run

        # Use a nested path that doesn't exist
        dest = tmp_path / "deep" / "nested" / "path"
        assert not dest.exists()

        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is True
        assert dest.exists()

    @patch("context_harness.skills.subprocess.run")
    def test_fetch_subdirectory_failure_propagates(self, mock_run, tmp_path):
        """Test that failure in subdirectory fetch propagates correctly."""
        import subprocess

        main_dir_response = [
            {
                "name": "scripts",
                "path": "skill/test/scripts",
                "type": "dir",
            },
        ]

        call_count = [0]

        def mock_subprocess_run(args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call succeeds with directory listing
                result = MagicMock()
                result.returncode = 0
                result.stdout = json.dumps(main_dir_response)
                return result
            else:
                # Second call (recursive) fails
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=["gh"], stderr="Permission denied"
                )

        mock_run.side_effect = mock_subprocess_run

        dest = tmp_path / "skill"
        success = _fetch_directory_recursive(
            "test/repo", "skill/test", dest, quiet=True
        )

        assert success is False


class TestSkillExtraction:
    """Tests for skill extraction functionality."""

    @patch("context_harness.skills.check_gh_auth")
    @patch("context_harness.skills.check_repo_access")
    @patch("context_harness.skills.subprocess.run")
    def test_extract_skill_success(
        self, mock_run, mock_access, mock_auth, sample_skill_dir, tmp_path
    ):
        """Test successful skill extraction creates a PR."""
        from context_harness.skills import extract_skill

        mock_auth.return_value = True
        mock_access.return_value = True

        # Track subprocess calls
        call_sequence = []

        def mock_subprocess_run(args, **kwargs):
            call_sequence.append(args[0] if args else "unknown")
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            # Handle gh pr create - returns the PR URL
            if args[:2] == ["gh", "pr"]:
                result.stdout = (
                    "https://github.com/cmtzco/context-harness-skills/pull/42"
                )

            return result

        mock_run.side_effect = mock_subprocess_run

        # source_path is the root containing .opencode/skill/test-skill
        source_path = sample_skill_dir.parent.parent.parent

        result, pr_url = extract_skill(
            "test-skill",
            source_path=str(source_path),
            quiet=True,
        )

        assert result == SkillResult.SUCCESS
        assert pr_url == "https://github.com/cmtzco/context-harness-skills/pull/42"

        # Verify key subprocess calls were made
        assert "gh" in call_sequence  # gh repo clone, gh pr create
        assert "git" in call_sequence  # git checkout, git add, git commit, git push

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


class TestListLocalSkills:
    """Tests for list_local_skills function."""

    def test_list_local_skills_with_valid_skills(self, sample_skill_dir):
        """Test listing local skills with valid skills present."""
        source_path = sample_skill_dir.parent.parent.parent
        skills = list_local_skills(source_path=str(source_path), quiet=True)

        assert len(skills) == 1
        assert skills[0].name == "test-skill"
        assert skills[0].description == "A test skill for unit testing"
        assert skills[0].version == "1.0.0"
        assert skills[0].is_valid is True

    def test_list_local_skills_empty_directory(self, tmp_path):
        """Test listing local skills when no skills exist."""
        # Create empty .opencode/skill directory
        skills_dir = tmp_path / ".opencode" / "skill"
        skills_dir.mkdir(parents=True)

        skills = list_local_skills(source_path=str(tmp_path), quiet=True)
        assert len(skills) == 0

    def test_list_local_skills_no_directory(self, tmp_path):
        """Test listing local skills when .opencode/skill doesn't exist."""
        skills = list_local_skills(source_path=str(tmp_path), quiet=True)
        assert len(skills) == 0

    def test_list_local_skills_invalid_skill(self, tmp_path):
        """Test listing local skills with invalid skill (missing SKILL.md)."""
        skill_dir = tmp_path / ".opencode" / "skill" / "invalid-skill"
        skill_dir.mkdir(parents=True)
        # No SKILL.md file

        skills = list_local_skills(source_path=str(tmp_path), quiet=True)

        assert len(skills) == 1
        assert skills[0].name == "invalid-skill"
        assert skills[0].is_valid is False
        assert "missing SKILL.md" in skills[0].description

    def test_list_local_skills_multiple_skills(self, tmp_path):
        """Test listing multiple local skills."""
        skills_dir = tmp_path / ".opencode" / "skill"

        # Create first skill
        skill1_dir = skills_dir / "skill-one"
        skill1_dir.mkdir(parents=True)
        (skill1_dir / "SKILL.md").write_text(
            """---
name: skill-one
description: First skill
version: 1.0.0
---
# Skill One
""",
            encoding="utf-8",
        )

        # Create second skill
        skill2_dir = skills_dir / "skill-two"
        skill2_dir.mkdir(parents=True)
        (skill2_dir / "SKILL.md").write_text(
            """---
name: skill-two
description: Second skill
version: 2.0.0
---
# Skill Two
""",
            encoding="utf-8",
        )

        skills = list_local_skills(source_path=str(tmp_path), quiet=True)

        assert len(skills) == 2
        skill_names = [s.name for s in skills]
        assert "skill-one" in skill_names
        assert "skill-two" in skill_names

    def test_list_local_skills_ignores_files(self, tmp_path):
        """Test that list_local_skills ignores non-directory entries."""
        skills_dir = tmp_path / ".opencode" / "skill"
        skills_dir.mkdir(parents=True)

        # Create a file (not a directory) in the skills folder
        (skills_dir / "README.md").write_text("# Skills\n", encoding="utf-8")

        # Create a valid skill directory
        skill_dir = skills_dir / "valid-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: valid-skill
description: Valid skill
---
# Valid
""",
            encoding="utf-8",
        )

        skills = list_local_skills(source_path=str(tmp_path), quiet=True)

        # Should only return the skill directory, not the README.md file
        assert len(skills) == 1
        assert skills[0].name == "valid-skill"

    def test_list_local_skills_sorted_alphabetically(self, tmp_path):
        """Test that skills are sorted alphabetically."""
        skills_dir = tmp_path / ".opencode" / "skill"

        # Create skills in non-alphabetical order
        for name in ["zebra-skill", "alpha-skill", "middle-skill"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                f"""---
name: {name}
description: {name} description
---
# {name}
""",
                encoding="utf-8",
            )

        skills = list_local_skills(source_path=str(tmp_path), quiet=True)

        assert len(skills) == 3
        assert skills[0].name == "alpha-skill"
        assert skills[1].name == "middle-skill"
        assert skills[2].name == "zebra-skill"


class TestListLocalSkillsCLI:
    """Tests for skill list-local CLI command."""

    def test_skill_list_local_help(self, runner):
        """Test that skill list-local --help works."""
        result = runner.invoke(main, ["skill", "list-local", "--help"])
        assert result.exit_code == 0
        assert "List skills installed" in result.output
        assert "--source" in result.output

    def test_skill_list_local_with_skills(self, runner, sample_skill_dir):
        """Test skill list-local with valid skills."""
        source_path = sample_skill_dir.parent.parent.parent
        result = runner.invoke(
            main, ["skill", "list-local", "--source", str(source_path)]
        )
        assert result.exit_code == 0
        assert "Local Skills" in result.output
        assert "test-skill" in result.output

    def test_skill_list_local_no_directory(self, runner, tmp_path):
        """Test skill list-local when no skills directory exists."""
        result = runner.invoke(main, ["skill", "list-local", "--source", str(tmp_path)])
        assert result.exit_code == 0
        assert "No skills directory found" in result.output
