"""Tests for SkillService.

Tests use mock GitHub client for isolation from actual API calls.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional
from unittest.mock import patch

import pytest

from context_harness.primitives import (
    ErrorCode,
    Failure,
    RegistryRepo,
    RepoVisibility,
    SkillSource,
    Success,
    VersionComparison,
    VersionStatus,
)
from context_harness.services.skill_service import (
    GitHubClient,
    SkillService,
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
        create_repo_url: Optional[str] = "https://github.com/test-user/test-repo",
    ):
        self._authenticated = authenticated
        self._has_repo_access = has_repo_access
        self._registry_content = registry_content
        self._username = username
        self._files: dict[str, str] = {}
        self._fetch_directory_succeeds = True
        self._create_repo_url = create_repo_url
        self._create_repo_calls: List[dict] = []

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

    def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str = "",
    ) -> Optional[str]:
        self._create_repo_calls.append(
            {"name": name, "private": private, "description": description}
        )
        return self._create_repo_url

    def enable_workflow_pr_creation(self, repo: str) -> bool:
        self._enable_workflow_pr_calls: list[str] = getattr(
            self, "_enable_workflow_pr_calls", []
        )
        self._enable_workflow_pr_calls.append(repo)
        return True


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


# ---------------------------------------------------------------------------
# Version comparison tests
# ---------------------------------------------------------------------------


class TestSkillServiceCompareVersions:
    """Tests for SkillService._compare_versions()."""

    def test_upgrade_available(self) -> None:
        """Remote is newer than local → UPGRADE_AVAILABLE."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version=None,
            current_ch_version="3.0.0",
        )
        assert result.status == VersionStatus.UPGRADE_AVAILABLE
        assert result.skill_name == "my-skill"
        assert result.local_version == "1.0.0"
        assert result.remote_version == "1.1.0"

    def test_up_to_date(self) -> None:
        """Remote equals local → UP_TO_DATE."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="2.0.0",
            remote_version="2.0.0",
            min_ch_version=None,
            current_ch_version="3.0.0",
        )
        assert result.status == VersionStatus.UP_TO_DATE

    def test_local_newer_than_remote(self) -> None:
        """Local is newer than remote → UP_TO_DATE (no downgrade)."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="2.0.0",
            remote_version="1.9.0",
            min_ch_version=None,
            current_ch_version="3.0.0",
        )
        assert result.status == VersionStatus.UP_TO_DATE

    def test_incompatible_ch_version(self) -> None:
        """Current CH is below min required → INCOMPATIBLE."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version="4.0.0",
            current_ch_version="3.0.0",
        )
        assert result.status == VersionStatus.INCOMPATIBLE
        assert result.context_harness_min == "4.0.0"

    def test_compatible_ch_version(self) -> None:
        """Current CH meets min required → not INCOMPATIBLE."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version="3.0.0",
            current_ch_version="3.0.0",
        )
        assert result.status != VersionStatus.INCOMPATIBLE

    def test_invalid_version_string(self) -> None:
        """Unparseable version strings → UNKNOWN."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="not-a-version",
            remote_version="also-bad",
            min_ch_version=None,
            current_ch_version="3.0.0",
        )
        assert result.status == VersionStatus.UNKNOWN

    def test_no_min_ch_version(self) -> None:
        """When min_ch_version is None, skip compatibility check."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version=None,
            current_ch_version="1.0.0",  # Would be incompatible if enforced
        )
        # Should still see UPGRADE_AVAILABLE, not INCOMPATIBLE
        assert result.status == VersionStatus.UPGRADE_AVAILABLE

    def test_result_has_correct_fields(self) -> None:
        """VersionComparison has all expected fields populated."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="test-skill",
            local_version="0.1.0",
            remote_version="0.2.0",
            min_ch_version="3.0.0",
            current_ch_version="4.0.0",
        )
        assert result.skill_name == "test-skill"
        assert result.local_version == "0.1.0"
        assert result.remote_version == "0.2.0"
        assert result.context_harness_min == "3.0.0"
        assert result.current_context_harness == "4.0.0"


class TestSkillServiceCheckSkillUpdates:
    """Tests for SkillService.check_skill_updates()."""

    def test_check_updates_not_installed(self, tmp_path: Path) -> None:
        """Skill not installed locally → UPGRADE_AVAILABLE (available to install)."""
        registry = create_test_registry(
            [
                {
                    "name": "new-skill",
                    "description": "A new skill",
                    "version": "1.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/new-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.check_skill_updates("new-skill", tmp_path)

        assert isinstance(result, Success)
        assert result.value.status == VersionStatus.UPGRADE_AVAILABLE
        assert result.value.local_version is None

    def test_check_updates_skill_not_in_registry(self, tmp_path: Path) -> None:
        """Skill not in remote registry → Failure(NOT_FOUND)."""
        registry = create_test_registry([])
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.check_skill_updates("ghost-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND

    def test_check_updates_up_to_date(self, tmp_path: Path) -> None:
        """Locally installed skill matches remote version → UP_TO_DATE."""
        # Create local skill
        skill_dir = tmp_path / ".opencode" / "skill" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: My skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "my-skill",
                    "description": "My skill",
                    "version": "1.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/my-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.check_skill_updates("my-skill", tmp_path)

        assert isinstance(result, Success)
        assert result.value.status == VersionStatus.UP_TO_DATE


class TestSkillServiceListOutdated:
    """Tests for SkillService.list_outdated_skills()."""

    def test_no_outdated_skills(self, tmp_path: Path) -> None:
        """All skills up to date → empty list."""
        skill_dir = tmp_path / ".opencode" / "skill" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: my-skill
description: My skill
version: 2.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "my-skill",
                    "description": "My skill",
                    "version": "2.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/my-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_outdated_skills(tmp_path)

        assert isinstance(result, Success)
        assert result.value == []

    def test_outdated_skill_included(self, tmp_path: Path) -> None:
        """Skill with newer remote version → included in results."""
        skill_dir = tmp_path / ".opencode" / "skill" / "old-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: old-skill
description: Old skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "old-skill",
                    "description": "Old skill",
                    "version": "2.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/old-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_outdated_skills(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 1
        assert result.value[0].skill_name == "old-skill"
        assert result.value[0].status == VersionStatus.UPGRADE_AVAILABLE

    def test_local_only_skills_excluded(self, tmp_path: Path) -> None:
        """Skills only installed locally (not in registry) are excluded."""
        skill_dir = tmp_path / ".opencode" / "skill" / "local-only"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: local-only
description: Local only skill
version: 1.0.0
---
""")
        registry = create_test_registry([])  # Empty registry
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_outdated_skills(tmp_path)

        assert isinstance(result, Success)
        assert result.value == []

    def test_incompatible_skill_included(self, tmp_path: Path) -> None:
        """Skills with CH version incompatibility → included as INCOMPATIBLE."""
        skill_dir = tmp_path / ".opencode" / "skill" / "needs-upgrade"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: needs-upgrade
description: Needs upgrade skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "needs-upgrade",
                    "description": "Needs upgrade skill",
                    "version": "2.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/needs-upgrade",
                    "min_context_harness_version": "99.0.0",  # Very high requirement
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.list_outdated_skills(tmp_path)

        assert isinstance(result, Success)
        assert len(result.value) == 1
        assert result.value[0].status == VersionStatus.INCOMPATIBLE


class TestSkillServiceUpgrade:
    """Tests for SkillService.upgrade_skill()."""

    def test_upgrade_already_up_to_date(self, tmp_path: Path) -> None:
        """Upgrading a skill that's already up to date → SKILL_NO_UPGRADE_AVAILABLE."""
        skill_dir = tmp_path / ".opencode" / "skill" / "current-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: current-skill
description: Current skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "current-skill",
                    "description": "Current skill",
                    "version": "1.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/current-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill("current-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NO_UPGRADE_AVAILABLE

    def test_upgrade_incompatible_without_force(self, tmp_path: Path) -> None:
        """Upgrade blocked when incompatible and force_compatibility=False."""
        skill_dir = tmp_path / ".opencode" / "skill" / "blocked-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: blocked-skill
description: Blocked skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "blocked-skill",
                    "description": "Blocked skill",
                    "version": "2.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/blocked-skill",
                    "min_context_harness_version": "99.0.0",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill(
            "blocked-skill", tmp_path, force_compatibility=False
        )

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_INCOMPATIBLE_VERSION

    def test_upgrade_incompatible_with_force(self, tmp_path: Path) -> None:
        """Upgrade proceeds when incompatible but force_compatibility=True."""
        skill_dir = tmp_path / ".opencode" / "skill" / "forced-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: forced-skill
description: Forced skill
version: 1.0.0
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "forced-skill",
                    "description": "Forced skill",
                    "version": "2.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/forced-skill",
                    "min_context_harness_version": "99.0.0",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill(
            "forced-skill", tmp_path, force_compatibility=True
        )

        assert isinstance(result, Success)

    def test_upgrade_not_in_registry(self, tmp_path: Path) -> None:
        """Upgrading a skill not in the remote registry → Failure."""
        registry = create_test_registry([])
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill("ghost-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND

    def test_upgrade_not_installed_locally(self, tmp_path: Path) -> None:
        """Upgrading a skill that is in the registry but not installed locally → SKILL_NOT_FOUND."""
        registry = create_test_registry(
            [
                {
                    "name": "remote-only-skill",
                    "description": "Remote skill",
                    "version": "1.0.0",
                    "author": "author",
                    "tags": [],
                    "path": "skill/remote-only-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill("remote-only-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_NOT_FOUND
        assert "not installed" in result.error.lower()

    def test_upgrade_unknown_version_returns_failure(self, tmp_path: Path) -> None:
        """Upgrading a skill with an unparseable version → SKILL_UPGRADE_FAILED."""
        skill_dir = tmp_path / ".opencode" / "skill" / "bad-version-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: bad-version-skill
description: Skill with bad version
version: not-a-valid-semver!!
---
""")
        registry = create_test_registry(
            [
                {
                    "name": "bad-version-skill",
                    "description": "Skill with bad version",
                    "version": "also-not-valid!!",
                    "author": "author",
                    "tags": [],
                    "path": "skill/bad-version-skill",
                }
            ]
        )
        client = MockGitHubClient(registry_content=registry)
        service = SkillService(github_client=client)

        result = service.upgrade_skill("bad-version-skill", tmp_path)

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.SKILL_UPGRADE_FAILED


class TestSkillServiceCompareVersionsEdgeCases:
    """Edge-case tests for SkillService._compare_versions()."""

    def test_unknown_ch_version_string(self) -> None:
        """'0.0.0+unknown' (dev install) is valid PEP 440 and parses as 0.0.0.

        packaging.version.Version treats the '+unknown' part as a local version
        identifier, so '0.0.0+unknown' normalises to 0.0.0. When a skill's
        min_context_harness_version is newer (e.g. 1.0.0), the result is
        INCOMPATIBLE — which is the safest outcome for a dev install.
        """
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version="1.0.0",
            current_ch_version="0.0.0+unknown",
        )
        # 0.0.0+unknown < 1.0.0  →  INCOMPATIBLE (safe default for dev installs)
        assert result.status == VersionStatus.INCOMPATIBLE

    def test_truly_invalid_ch_version_string(self) -> None:
        """A completely invalid CH version string propagates to UNKNOWN status."""
        service = SkillService(github_client=MockGitHubClient())
        result = service._compare_versions(
            skill_name="my-skill",
            local_version="1.0.0",
            remote_version="1.1.0",
            min_ch_version="1.0.0",
            current_ch_version="not-a-version!!",
        )
        # Invalid CH version → inner InvalidVersion re-raises → outer handler → UNKNOWN
        assert result.status == VersionStatus.UNKNOWN


# ---------------------------------------------------------------------------
# init_registry_repo tests
# ---------------------------------------------------------------------------


class TestSkillServiceInitRegistryRepo:
    """Tests for SkillService.init_registry_repo().

    These tests exercise the pre-subprocess validation paths (auth, repo
    existence, create_repo) via the mock client.  The subprocess calls for
    clone/add/commit/push are mocked via ``unittest.mock.patch``.
    """

    # -- Happy path ---------------------------------------------------------

    def test_init_repo_success(self) -> None:
        """Happy path: auth OK → repo doesn't exist → create → scaffold → push → Success."""
        client = MockGitHubClient(
            authenticated=True,
            has_repo_access=False,  # repo does NOT exist
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = service.init_registry_repo("my-skills")

        assert isinstance(result, Success)
        repo = result.value
        assert isinstance(repo, RegistryRepo)
        assert repo.name == "my-skills"
        assert repo.url == "https://github.com/test-user/my-skills"
        assert repo.visibility == RepoVisibility.PRIVATE

    def test_init_repo_public_visibility(self) -> None:
        """Public visibility flag is reflected in returned RegistryRepo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/public-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = service.init_registry_repo("public-skills", private=False)

        assert isinstance(result, Success)
        assert result.value.visibility == RepoVisibility.PUBLIC

    def test_init_repo_custom_description(self) -> None:
        """Custom description is passed through to create_repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = service.init_registry_repo(
                "my-skills", description="Team AI skills"
            )

        assert isinstance(result, Success)
        # Verify description was passed to create_repo
        assert len(client._create_repo_calls) == 1
        assert client._create_repo_calls[0]["description"] == "Team AI skills"

    def test_init_repo_default_description_used(self) -> None:
        """When no description is given, a default is provided."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            service.init_registry_repo("my-skills")

        assert len(client._create_repo_calls) == 1
        assert client._create_repo_calls[0]["description"] != ""

    def test_init_repo_org_name_passed_through(self) -> None:
        """Owner/repo name format is passed through to create_repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/my-org/team-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = service.init_registry_repo("my-org/team-skills")

        assert isinstance(result, Success)
        assert result.value.name == "my-org/team-skills"
        assert client._create_repo_calls[0]["name"] == "my-org/team-skills"

    # -- Scaffold content verification --------------------------------------

    def test_scaffold_writes_all_expected_files(self, tmp_path: Path) -> None:
        """Scaffold writes complete CI/CD file tree."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        expected_files = [
            "skills.json",
            "release-please-config.json",
            ".release-please-manifest.json",
            ".gitignore",
            "README.md",
            "CONTRIBUTING.md",
            "QUICKSTART.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/new-skill.md",
            ".github/workflows/release.yml",
            ".github/workflows/sync-registry.yml",
            ".github/workflows/validate-skills.yml",
            "scripts/sync-registry.py",
            "scripts/validate_skills.py",
            "skill/example-skill/SKILL.md",
            "skill/example-skill/version.txt",
            "skill/skill-release/SKILL.md",
            "skill/skill-release/version.txt",
            "skill/skill-release/references/troubleshooting.md",
        ]
        for filepath in expected_files:
            assert (tmp_path / filepath).exists(), f"Missing: {filepath}"

    def test_scaffold_skills_json_content(self, tmp_path: Path) -> None:
        """skills.json contains empty registry with schema_version 1.0."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = json.loads((tmp_path / "skills.json").read_text())
        assert content["schema_version"] == "1.0"
        assert content["skills"] == []

    def test_scaffold_readme_contains_repo_name(self, tmp_path: Path) -> None:
        """README.md references the repository name."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "my-org/team-skills")

        readme = (tmp_path / "README.md").read_text()
        assert "my-org/team-skills" in readme

    def test_scaffold_readme_contains_lifecycle_diagram(self, tmp_path: Path) -> None:
        """README.md includes the ASCII lifecycle flow."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        readme = (tmp_path / "README.md").read_text()
        assert "release-please" in readme
        assert "version.txt" in readme
        assert "sync-registry" in readme

    def test_scaffold_release_please_config(self, tmp_path: Path) -> None:
        """release-please-config.json has correct monorepo structure."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        config = json.loads((tmp_path / "release-please-config.json").read_text())
        assert config["separate-pull-requests"] is True
        assert config["include-component-in-tag"] is True
        assert config["tag-separator"] == "@"
        assert "skill/example-skill" in config["packages"]
        pkg = config["packages"]["skill/example-skill"]
        assert pkg["release-type"] == "simple"
        assert pkg["component"] == "example-skill"
        # skill-release must also be registered
        assert "skill/skill-release" in config["packages"]
        sr_pkg = config["packages"]["skill/skill-release"]
        assert sr_pkg["release-type"] == "simple"
        assert sr_pkg["component"] == "skill-release"

    def test_scaffold_release_please_manifest(self, tmp_path: Path) -> None:
        """.release-please-manifest.json has initial version for all skills."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        manifest = json.loads((tmp_path / ".release-please-manifest.json").read_text())
        assert manifest["skill/example-skill"] == "0.1.0"
        assert manifest["skill/skill-release"] == "0.1.0"

    def test_scaffold_example_skill_md_no_version(self, tmp_path: Path) -> None:
        """Example SKILL.md has frontmatter without version field."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "skill" / "example-skill" / "SKILL.md").read_text()
        assert "name: example-skill" in content
        assert "description:" in content
        # Version must NOT be in frontmatter
        lines = content.split("\n")
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter and line.strip().startswith("version:"):
                pytest.fail("version field found in SKILL.md frontmatter")

    def test_scaffold_example_skill_version_txt(self, tmp_path: Path) -> None:
        """Example skill has version.txt bootstrapped at 0.1.0."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        version = (
            (tmp_path / "skill" / "example-skill" / "version.txt").read_text().strip()
        )
        assert version == "0.1.0"

    def test_scaffold_skill_release_md_no_version(self, tmp_path: Path) -> None:
        """skill-release SKILL.md has frontmatter without version field."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "skill" / "skill-release" / "SKILL.md").read_text()
        assert "name: skill-release" in content
        assert "description:" in content
        # Version must NOT be in frontmatter
        lines = content.split("\n")
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter and line.strip().startswith("version:"):
                pytest.fail("version field found in skill-release SKILL.md frontmatter")

    def test_scaffold_skill_release_version_txt(self, tmp_path: Path) -> None:
        """skill-release has version.txt bootstrapped at 0.1.0."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        version = (
            (tmp_path / "skill" / "skill-release" / "version.txt").read_text().strip()
        )
        assert version == "0.1.0"

    def test_scaffold_skill_release_troubleshooting(self, tmp_path: Path) -> None:
        """skill-release includes references/troubleshooting.md."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        troubleshooting = (
            tmp_path / "skill" / "skill-release" / "references" / "troubleshooting.md"
        ).read_text()
        assert "Decision Tree" in troubleshooting
        assert "Diagnostic Commands" in troubleshooting
        assert "release-please" in troubleshooting

    def test_scaffold_skill_release_content_covers_workflows(
        self, tmp_path: Path
    ) -> None:
        """skill-release SKILL.md covers create, update, and release workflows."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "skill" / "skill-release" / "SKILL.md").read_text()
        assert "Golden Rules" in content
        assert "Create a New Skill" in content
        assert "Update an Existing Skill" in content
        assert "Release Lifecycle" in content
        assert "Common Mistakes" in content

    def test_scaffold_release_workflow_uses_release_please(
        self, tmp_path: Path
    ) -> None:
        """release.yml uses googleapis/release-please-action@v4."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".github" / "workflows" / "release.yml").read_text()
        assert "googleapis/release-please-action@v4" in content
        assert "release-please-config.json" in content

    def test_scaffold_sync_registry_workflow(self, tmp_path: Path) -> None:
        """sync-registry.yml triggers on version.txt and SKILL.md changes."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".github" / "workflows" / "sync-registry.yml").read_text()
        assert "skill/*/version.txt" in content
        assert "skill/*/SKILL.md" in content
        assert "sync-registry.py" in content
        assert "[skip ci]" in content

    def test_scaffold_validate_skills_workflow(self, tmp_path: Path) -> None:
        """validate-skills.yml runs on PRs touching skill directories."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (
            tmp_path / ".github" / "workflows" / "validate-skills.yml"
        ).read_text()
        assert "pull_request" in content
        assert "skill/**" in content
        assert "validate_skills.py" in content
        assert "marocchino/sticky-pull-request-comment@v2" in content
        assert "contents: read" in content

    def test_scaffold_sync_registry_script(self, tmp_path: Path) -> None:
        """sync-registry.py parses frontmatter and version.txt."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "scripts" / "sync-registry.py").read_text()
        assert "frontmatter" in content
        assert "version.txt" in content
        assert "content_hash" in content
        assert "skills.json" in content

    def test_scaffold_validate_skills_script(self, tmp_path: Path) -> None:
        """validate_skills.py checks frontmatter and rejects version field."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "scripts" / "validate_skills.py").read_text()
        assert "pydantic" in content.lower() or "BaseModel" in content
        assert "version" in content
        assert "validation-report.md" in content

    def test_scaffold_contributing_mentions_no_version(self, tmp_path: Path) -> None:
        """CONTRIBUTING.md warns against adding version to frontmatter."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "CONTRIBUTING.md").read_text()
        assert "version.txt" in content
        assert "release-please" in content
        assert "Never edit" in content or "never" in content.lower()

    def test_scaffold_contributing_contains_repo_name(self, tmp_path: Path) -> None:
        """CONTRIBUTING.md references the repository name."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "my-org/team-skills")

        content = (tmp_path / "CONTRIBUTING.md").read_text()
        assert "my-org/team-skills" in content

    def test_scaffold_quickstart_contains_repo_name(self, tmp_path: Path) -> None:
        """QUICKSTART.md references the repository name."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "my-org/team-skills")

        content = (tmp_path / "QUICKSTART.md").read_text()
        assert "my-org/team-skills" in content

    def test_scaffold_gitignore_present(self, tmp_path: Path) -> None:
        """.gitignore excludes Python and OS artifacts."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".gitignore").read_text()
        assert "__pycache__" in content
        assert ".DS_Store" in content

    def test_scaffold_pr_template_present(self, tmp_path: Path) -> None:
        """PR template includes conventional commit guidance."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()
        assert "feat:" in content or "fix:" in content
        assert "version" in content.lower()

    def test_scaffold_issue_template_present(self, tmp_path: Path) -> None:
        """Issue template for new skill requests exists."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".github" / "ISSUE_TEMPLATE" / "new-skill.md").read_text()
        assert "Skill Name" in content or "name" in content.lower()

    # -- Failure paths -------------------------------------------------------

    def test_init_repo_auth_failure(self) -> None:
        """Auth not available → Failure(AUTH_REQUIRED)."""
        client = MockGitHubClient(authenticated=False)
        service = SkillService(github_client=client)

        result = service.init_registry_repo("my-skills")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.AUTH_REQUIRED

    def test_init_repo_already_exists(self) -> None:
        """Repo already exists → Failure(REPO_ALREADY_EXISTS)."""
        client = MockGitHubClient(
            has_repo_access=True,  # repo exists
        )
        service = SkillService(github_client=client)

        result = service.init_registry_repo("my-skills")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.REPO_ALREADY_EXISTS

    def test_init_repo_create_fails(self) -> None:
        """create_repo returns None → Failure(REPO_CREATE_FAILED)."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url=None,  # simulate creation failure
        )
        service = SkillService(github_client=client)

        result = service.init_registry_repo("bad-name")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.REPO_CREATE_FAILED

    def test_init_repo_push_failure(self) -> None:
        """Subprocess error during clone/commit/push → Failure(REPO_CREATE_FAILED)."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "git push", stderr="push failed"
            ),
        ):
            result = service.init_registry_repo("my-skills")

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.REPO_CREATE_FAILED
        assert (
            "push failed" in result.error.lower()
            or "scaffold push failed" in result.error.lower()
        )

    def test_init_repo_push_failure_preserves_url(self) -> None:
        """Push failure details include the repo URL for debugging."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "git push", stderr="remote error"
            ),
        ):
            result = service.init_registry_repo("my-skills")

        assert isinstance(result, Failure)
        assert result.details is not None
        assert result.details["url"] == "https://github.com/test-user/my-skills"

    # -- Subprocess call verification ----------------------------------------

    def test_init_repo_calls_clone_add_commit_push(self) -> None:
        """Subprocess calls are made in correct order: clone, add, commit, push."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            service.init_registry_repo("my-skills")

        # Should have 4 subprocess calls: clone, add, commit, push
        assert mock_run.call_count == 4

        calls = [c.args[0] for c in mock_run.call_args_list]
        # First call: gh repo clone
        assert calls[0][0] == "gh"
        assert "clone" in calls[0]
        # Second call: git add
        assert calls[1][0] == "git"
        assert "add" in calls[1]
        # Third call: git commit
        assert calls[2][0] == "git"
        assert "commit" in calls[2]
        # Fourth call: git push
        assert calls[3][0] == "git"
        assert "push" in calls[3]

    def test_init_repo_private_flag_passed_to_create(self) -> None:
        """Private=True is passed through to create_repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run"):
            service.init_registry_repo("my-skills", private=True)

        assert client._create_repo_calls[0]["private"] is True

    def test_init_repo_public_flag_passed_to_create(self) -> None:
        """Private=False is passed through to create_repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run"):
            service.init_registry_repo("my-skills", private=False)

        assert client._create_repo_calls[0]["private"] is False

    # -- Workflow permissions -------------------------------------------------

    def test_init_repo_enables_workflow_pr_creation_bare_name(self) -> None:
        """Bare repo name → enable_workflow_pr_creation called with user/repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/test-user/my-skills",
            username="test-user",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            service.init_registry_repo("my-skills")

        assert hasattr(client, "_enable_workflow_pr_calls")
        assert client._enable_workflow_pr_calls == ["test-user/my-skills"]

    def test_init_repo_enables_workflow_pr_creation_org_name(self) -> None:
        """Org/repo name → enable_workflow_pr_creation called with org/repo."""
        client = MockGitHubClient(
            has_repo_access=False,
            create_repo_url="https://github.com/my-org/team-skills",
        )
        service = SkillService(github_client=client)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            service.init_registry_repo("my-org/team-skills")

        assert hasattr(client, "_enable_workflow_pr_calls")
        assert client._enable_workflow_pr_calls == ["my-org/team-skills"]

    # -- Scaffold content: workflow permissions docs -------------------------

    def test_scaffold_release_yml_contains_permissions_comment(
        self, tmp_path: Path
    ) -> None:
        """release.yml contains comment about enabling workflow PR creation."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / ".github" / "workflows" / "release.yml").read_text()
        assert "Allow GitHub Actions to create" in content
        assert "Settings > Actions > General" in content
        assert "gh api repos/OWNER/REPO/actions/permissions/workflow" in content

    def test_scaffold_quickstart_contains_setup_section(self, tmp_path: Path) -> None:
        """QUICKSTART.md documents the required repository setup step."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        content = (tmp_path / "QUICKSTART.md").read_text()
        assert "Repository Setup" in content
        assert "Allow GitHub Actions to create and approve pull requests" in content
        assert "can_approve_pull_request_reviews" in content

    def test_scaffold_readme_contains_setup_note(self, tmp_path: Path) -> None:
        """README.md mentions the workflow permissions requirement."""
        service = SkillService(github_client=MockGitHubClient())
        service._write_registry_scaffold(tmp_path, "test-user/my-skills")

        readme = (tmp_path / "README.md").read_text()
        assert "Settings" in readme
        assert "Actions" in readme
