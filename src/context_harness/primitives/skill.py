"""Skill primitives for ContextHarness.

A Skill represents a reusable agent capability that extends
what the agent can do. Skills follow the OpenCode skill format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class SkillSource(Enum):
    """Where a skill originates from."""

    LOCAL = "local"  # Installed in .opencode/skill/
    REMOTE = "remote"  # From the central skills repository
    BUILTIN = "builtin"  # Bundled with ContextHarness


class VersionStatus(Enum):
    """Status of a skill's version compared to available versions."""

    UP_TO_DATE = "up_to_date"  # Local version matches or exceeds remote
    UPGRADE_AVAILABLE = "upgrade_available"  # Newer remote version available
    INCOMPATIBLE = "incompatible"  # Skill requires newer ContextHarness version
    UNKNOWN = "unknown"  # Unable to determine version status


class RepoVisibility(Enum):
    """Visibility of a GitHub repository."""

    PRIVATE = "private"
    PUBLIC = "public"


@dataclass
class SkillMetadata:
    """Frontmatter metadata from SKILL.md.

    This corresponds to the YAML frontmatter at the top of SKILL.md files.

    Attributes:
        name: Skill identifier (must match directory name)
        description: Brief description of what the skill does
        version: Semantic version string
        author: Author name or identifier
        tags: List of categorization tags
    """

    name: str
    description: str
    version: str = "0.1.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class Skill:
    """A skill that extends agent capabilities.

    Skills are loaded from SKILL.md files in .opencode/skill/ directories.
    They provide specialized knowledge, workflows, or tool integrations.

    Attributes:
        name: Skill identifier (directory name)
        description: Brief description
        version: Semantic version
        author: Author name
        tags: Categorization tags
        location: Absolute path to SKILL.md file
        source: Where the skill comes from (local, remote, builtin)
        is_valid: Whether the skill passes validation
        min_context_harness_version: Minimum required CH version
        path: Registry path for remote skills (e.g., "skill/skill-creator")
    """

    name: str
    description: str
    location: str  # Absolute path to SKILL.md
    source: SkillSource = SkillSource.LOCAL
    version: str = "0.1.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    is_valid: bool = True
    min_context_harness_version: Optional[str] = None
    path: Optional[str] = None  # Registry path for remote skills

    @classmethod
    def from_metadata(
        cls,
        metadata: SkillMetadata,
        location: str,
        source: SkillSource = SkillSource.LOCAL,
    ) -> "Skill":
        """Create a Skill from SkillMetadata.

        Args:
            metadata: Parsed frontmatter metadata
            location: Path to the SKILL.md file
            source: Where the skill originates

        Returns:
            Skill instance
        """
        return cls(
            name=metadata.name,
            description=metadata.description,
            version=metadata.version,
            author=metadata.author,
            tags=metadata.tags,
            location=location,
            source=source,
        )

    def to_info(self) -> dict:
        """Convert to info dict for display/serialization.

        Returns:
            Dict suitable for JSON serialization
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "location": self.location,
            "source": self.source.value,
            "is_valid": self.is_valid,
        }


@dataclass
class SkillRegistryEntry:
    """Entry in the skills registry (skills.json).

    Represents a skill available for installation from the
    central skills repository.

    Attributes:
        name: Skill identifier
        description: Brief description
        version: Published version
        author: Publisher name
        tags: Categorization tags
        path: Path in the repository (e.g., "skill/my-skill")
        min_context_harness_version: Minimum CH version required
    """

    name: str
    description: str
    version: str
    author: str
    path: str
    tags: List[str] = field(default_factory=list)
    min_context_harness_version: Optional[str] = None

    def to_skill(self) -> Skill:
        """Convert registry entry to Skill instance.

        Returns:
            Skill with source set to REMOTE
        """
        return Skill(
            name=self.name,
            description=self.description,
            version=self.version,
            author=self.author,
            tags=self.tags,
            path=self.path,
            location="",  # Not installed yet
            source=SkillSource.REMOTE,
            min_context_harness_version=self.min_context_harness_version,
        )


@dataclass
class VersionComparison:
    """Comparison of local and remote skill versions.

    Used to detect available upgrades and compatibility issues.

    Attributes:
        skill_name: Name of the skill being compared
        local_version: Currently installed version (None if not installed)
        remote_version: Latest available version from registry
        status: Comparison status (UP_TO_DATE, UPGRADE_AVAILABLE, etc.)
        context_harness_min: Minimum ContextHarness version required by skill
        current_context_harness: Current ContextHarness version
    """

    skill_name: str
    local_version: Optional[str]
    remote_version: str
    status: VersionStatus
    context_harness_min: Optional[str] = None
    current_context_harness: Optional[str] = None

    def needs_upgrade(self) -> bool:
        """Check if an upgrade is available.

        Returns:
            True if UPGRADE_AVAILABLE status
        """
        return self.status == VersionStatus.UPGRADE_AVAILABLE

    def is_compatible(self) -> bool:
        """Check if skill is compatible with current ContextHarness version.

        Returns:
            False if INCOMPATIBLE status, True otherwise
        """
        return self.status != VersionStatus.INCOMPATIBLE

    def to_dict(self) -> dict:
        """Convert to dictionary for display/serialization.

        Returns:
            Dict suitable for JSON serialization
        """
        return {
            "skill_name": self.skill_name,
            "local_version": self.local_version,
            "remote_version": self.remote_version,
            "status": self.status.value,
            "context_harness_min": self.context_harness_min,
            "current_context_harness": self.current_context_harness,
        }


@dataclass
class RegistryRepo:
    """Information about a skills registry repository.

    Represents a GitHub repository that serves as a private or organizational
    skills registry, created via `ch skill init-repo`.

    Attributes:
        name: Full repository name (owner/repo or just repo for personal)
        url: HTTPS URL to the repository
        visibility: Whether the repo is private or public
    """

    name: str
    url: str
    visibility: RepoVisibility
