"""Tests for SkillService.

Tests use mock GitHub client for isolation from actual API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import pytest

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Skill,
    SkillMetadata,
    SkillSource,
    Success,
)
from context_harness.services.skill_service import (
    GitHubClient,
    SkillService,
    SKILLS_DIR,
    SKILLS_REGISTRY_PATH,
)


class MockGitHubClient:
    """Mock GitHub client for testing."""

    def __init__(
        self,
        authenticated: bool = True,
        has_repo_access: bool = True,
        registry_content: Optional[str] = None,
        username: str = "test-user",
    ):
        self._authenticated = authenticated
        self._has_repo_access = has_repo_access
        self._registry_content = registry_content
        self._username = username
        self._files: dict[str, str] = {}
        self._fetch_directory_succeeds = True

    def check_auth(self) -> bool:
        return self._authenticated

    def check_repo_access(self, repo: str) -> bool:
        return self._has_repo_access

    def fetch_file(self, repo: str, path: str) -> Optional[str]:
        if path == SKILLS_REGISTRY_PATH:
            return self._registry_content
        return self._files.get(path)

    def fetch_directory(self, repo: str, path: str, dest: Path) -> bool:
        if not self._fetch_directory_succeeds:
            return False
        # Create a minimal skill structure
        dest.mkdir(parents=True, exist_ok=True)
        skill_md = dest / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A test skill
version: 1.0.0
tags:
  - testing
---

# Test Skill

This is a test skill.
""")
        return True

    def get_username(self) -> str:
        return self._username


def create_test_registry(skills: List[dict]) -> str:
    """Create a test registry JSON string."""
    return json.dumps(
        {
            "schema_version": "1.0",
            "skills": skills,
        }
    )


class TestSkillServiceListRemote:
    """Tests for SkillService.list_remote()."""

    def test_list_remote_returns_skills(self) -> None:
        """Test listing remote skills returns skills from registry."""
        registry = create_test_registry(
            [
                {
                    "name": "skill-a",
                    "description": "Skill A description",
                    "version": "1.0.0",
                    "author": "test-author",
                    "tags": ["testing", "automation"],
                    "path": "skill/skill-a",
                },
                {
                    "name": "skill-b",
                    "description": "Skill B description",
                    "version": "2.0.0",
                    "author": "another-author",
                    "tags": ["development"],
                    "path": "skill/skill-b",
                },
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_remote()

        assert isinstance(result, Success)
        assert len(result.value) == 2

        skill_a = next(s for s in result.value if s.name == "skill-a")
        assert skill_a.description == "Skill A description"
        assert skill_a.version == "1.0.0"
        assert skill_a.source == SkillSource.REMOTE
        assert "testing" in skill_a.tags

    def test_list_remote_not_authenticated(self) -> None:
        """Test list_remote fails when not authenticated."""
        client = MockGitHubClient(authenticated=False)
        service = SkillService(github_client=client)

        result = service.list_remote()

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED

    def test_list_remote_no_repo_access(self) -> None:
        """Test list_remote fails when no repo access."""
        client = MockGitHubClient(has_repo_access=False)
        service = SkillService(github_client=client)

        result = service.list_remote()

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.PERMISSION_DENIED

    def test_list_remote_registry_not_found(self) -> None:
        """Test list_remote fails when registry not found."""
        client = MockGitHubClient(registry_content=None)
        service = SkillService(github_client=client)

        result = service.list_remote()

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_FOUND

    def test_list_remote_invalid_registry(self) -> None:
        """Test list_remote fails with invalid registry JSON."""
        client = MockGitHubClient(registry_content="not valid json {{{")
        service = SkillService(github_client=client)

        result = service.list_remote()

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.VALIDATION_ERROR

    def test_list_remote_filter_by_tags(self) -> None:
        """Test filtering skills by tags."""
        registry = create_test_registry(
            [
                {"name": "skill-a", "tags": ["testing", "python"]},
                {"name": "skill-b", "tags": ["development", "typescript"]},
                {"name": "skill-c", "tags": ["testing", "javascript"]},
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_remote(tags=["testing"])

        assert isinstance(result, Success)
        assert len(result.value) == 2
        names = [s.name for s in result.value]
        assert "skill-a" in names
        assert "skill-c" in names
        assert "skill-b" not in names

    def test_list_remote_tag_filter_case_insensitive(self) -> None:
        """Test tag filtering is case insensitive."""
        registry = create_test_registry(
            [
                {"name": "skill-a", "tags": ["Testing"]},
                {"name": "skill-b", "tags": ["TESTING"]},
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_remote(tags=["testing"])

        assert isinstance(result, Success)
        assert len(result.value) == 2


class TestSkillServiceListLocal:
    """Tests for SkillService.list_local()."""

    def test_list_local_with_valid_skills(self, tmp_path: Path) -> None:
        """Test listing local skills with valid SKILL.md."""
        skill_dir = tmp_path / ".opencode" / "skill" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: My local skill
version: 1.2.3
tags:
  - local
  - testing
---

# My Skill
""")
        service = SkillService(github_client=MockGitHubClient())

        result = service.list_local(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 1

        skill = result.value[0]
        assert skill.name == "my-skill"
        assert skill.description == "My local skill"
        assert skill.version == "1.2.3"
        assert skill.source == SkillSource.LOCAL
        assert skill.is_valid is True

    def test_list_local_no_skills_directory(self, tmp_path: Path) -> None:
        """Test list_local returns empty when no skills directory."""
        service = SkillService(github_client=MockGitHubClient())

        result = service.list_local(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 0

    def test_list_local_skill_missing_skill_md(self, tmp_path: Path) -> None:
        """Test skill without SKILL.md is marked invalid."""
        skill_dir = tmp_path / ".opencode" / "skill" / "incomplete-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "README.md").write_text("# Just a readme")

        service = SkillService(github_client=MockGitHubClient())

        result = service.list_local(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 1

        skill = result.value[0]
        assert skill.name == "incomplete-skill"
        assert skill.is_valid is False
        assert "(missing SKILL.md)" in skill.description

    def test_list_local_multiple_skills(self, tmp_path: Path) -> None:
        """Test listing multiple local skills."""
        for name in ["skill-a", "skill-b", "skill-c"]:
            skill_dir = tmp_path / ".opencode" / "skill" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"""---
name: {name}
description: Description for {name}
version: 1.0.0
---
""")

        service = SkillService(github_client=MockGitHubClient())

        result = service.list_local(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 3
        names = [s.name for s in result.value]
        assert "skill-a" in names
        assert "skill-b" in names
        assert "skill-c" in names


class TestSkillServiceGetInfo:
    """Tests for SkillService.get_info()."""

    def test_get_info_existing_skill(self) -> None:
        """Test getting info for existing skill."""
        registry = create_test_registry(
            [
                {
                    "name": "target-skill",
                    "description": "The skill we want",
                    "version": "2.5.0",
                    "author": "skill-author",
                    "tags": ["important"],
                    "path": "skill/target-skill",
                },
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.get_info("target-skill")

        assert isinstance(result, Success)
        assert result.value.name == "target-skill"
        assert result.value.version == "2.5.0"

    def test_get_info_not_found(self) -> None:
        """Test getting info for non-existent skill."""
        registry = create_test_registry([])
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.get_info("nonexistent-skill")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND


class TestSkillServiceInstall:
    """Tests for SkillService.install()."""

    def test_install_skill_success(self, tmp_path: Path) -> None:
        """Test successful skill installation."""
        registry = create_test_registry(
            [
                {
                    "name": "installable-skill",
                    "description": "Can be installed",
                    "version": "1.0.0",
                    "path": "skill/installable-skill",
                },
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.install("installable-skill", tmp_path)

        assert isinstance(result, Success)
        assert result.value.name == "installable-skill"
        assert result.value.source == SkillSource.LOCAL

        # Verify files were created
        skill_dir = tmp_path / ".opencode" / "skill" / "installable-skill"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

    def test_install_skill_already_exists(self, tmp_path: Path) -> None:
        """Test install fails when skill already exists."""
        registry = create_test_registry(
            [
                {"name": "existing-skill", "path": "skill/existing-skill"},
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        # Pre-create the skill directory
        skill_dir = tmp_path / ".opencode" / "skill" / "existing-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("existing content")

        result = service.install("existing-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.ALREADY_EXISTS

    def test_install_skill_force_overwrite(self, tmp_path: Path) -> None:
        """Test install with force overwrites existing skill."""
        registry = create_test_registry(
            [
                {"name": "existing-skill", "path": "skill/existing-skill"},
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        # Pre-create the skill directory
        skill_dir = tmp_path / ".opencode" / "skill" / "existing-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "old-file.txt").write_text("old content")

        result = service.install("existing-skill", tmp_path, force=True)

        assert isinstance(result, Success)
        # Old file should be gone
        assert not (skill_dir / "old-file.txt").exists()
        # New SKILL.md should exist
        assert (skill_dir / "SKILL.md").exists()

    def test_install_skill_not_found(self, tmp_path: Path) -> None:
        """Test install fails for non-existent skill."""
        registry = create_test_registry([])
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.install("nonexistent", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND

    def test_install_skill_fetch_fails(self, tmp_path: Path) -> None:
        """Test install fails when fetch fails."""
        registry = create_test_registry(
            [
                {"name": "bad-skill", "path": "skill/bad-skill"},
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        client._fetch_directory_succeeds = False
        service = SkillService(github_client=client)

        result = service.install("bad-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INSTALL_FAILED


class TestSkillServiceValidate:
    """Tests for SkillService.validate()."""

    def test_validate_valid_skill(self, tmp_path: Path) -> None:
        """Test validating a valid skill."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: A valid skill
version: 1.0.0
tags:
  - testing
---

# My Skill

Content here.
""")
        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Success)
        assert result.value.name == "my-skill"
        assert result.value.description == "A valid skill"
        assert result.value.version == "1.0.0"
        assert "testing" in result.value.tags

    def test_validate_missing_skill_md(self, tmp_path: Path) -> None:
        """Test validation fails when SKILL.md missing."""
        skill_dir = tmp_path / "no-skill-md"
        skill_dir.mkdir()

        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID
        assert "SKILL.md not found" in result.error

    def test_validate_missing_frontmatter(self, tmp_path: Path) -> None:
        """Test validation fails when frontmatter missing."""
        skill_dir = tmp_path / "no-frontmatter"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just markdown\n\nNo frontmatter here.")

        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID
        assert "frontmatter" in result.error.lower()

    def test_validate_incomplete_frontmatter(self, tmp_path: Path) -> None:
        """Test validation fails with incomplete frontmatter."""
        skill_dir = tmp_path / "incomplete"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: incomplete
version: 1.0.0

# Missing closing ---
""")
        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID

    def test_validate_missing_name(self, tmp_path: Path) -> None:
        """Test validation fails when name missing."""
        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: Has description but no name
version: 1.0.0
---
""")
        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID
        assert "name" in result.error.lower()

    def test_validate_missing_description(self, tmp_path: Path) -> None:
        """Test validation fails when description missing."""
        skill_dir = tmp_path / "no-desc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: no-desc
version: 1.0.0
---
""")
        service = SkillService(github_client=MockGitHubClient())

        result = service.validate(skill_dir)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID
        assert "description" in result.error.lower()


class TestSkillServiceExtract:
    """Tests for SkillService.extract()."""

    def test_extract_invalid_skill_name(self, tmp_path: Path) -> None:
        """Test extract fails with invalid skill name."""
        service = SkillService(github_client=MockGitHubClient())

        result = service.extract("invalid skill name!", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.VALIDATION_ERROR

    def test_extract_not_authenticated(self, tmp_path: Path) -> None:
        """Test extract fails when not authenticated."""
        client = MockGitHubClient(authenticated=False)
        service = SkillService(github_client=client)

        result = service.extract("my-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED

    def test_extract_skill_not_found(self, tmp_path: Path) -> None:
        """Test extract fails when skill not found locally."""
        service = SkillService(github_client=MockGitHubClient())

        result = service.extract("nonexistent-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND

    def test_extract_invalid_skill(self, tmp_path: Path) -> None:
        """Test extract fails when skill is invalid."""
        skill_dir = tmp_path / ".opencode" / "skill" / "invalid-skill"
        skill_dir.mkdir(parents=True)
        # Create skill without required frontmatter
        (skill_dir / "SKILL.md").write_text("# No frontmatter")

        service = SkillService(github_client=MockGitHubClient())

        result = service.extract("invalid-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INVALID
