"""Tests for SkillService.

Tests use mock GitHub client for isolation from actual API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from context_harness.primitives import (
    ErrorCode,
    Failure,
    SkillSource,
    Success,
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


# ---------------------------------------------------------------------------
# Version comparison tests
# ---------------------------------------------------------------------------

from context_harness.primitives import VersionComparison, VersionStatus  # noqa: E402


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
