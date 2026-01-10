"""Skill service for ContextHarness.

Handles skill listing, installation, extraction, and validation.
Business logic extracted from skills.py module.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Protocol

import yaml

from context_harness.primitives import (
    DEFAULT_SKILLS_REPO,
    ErrorCode,
    Failure,
    Result,
    Skill,
    SkillMetadata,
    SkillSource,
    Success,
)


SKILLS_REGISTRY_PATH = "skills.json"
SKILLS_DIR = "skill"


class GitHubClient(Protocol):
    """Protocol for GitHub API operations.

    Allows for dependency injection and testing.
    """

    def check_auth(self) -> bool:
        """Check if authenticated with GitHub."""
        ...

    def check_repo_access(self, repo: str) -> bool:
        """Check if user has access to a repository."""
        ...

    def fetch_file(self, repo: str, path: str) -> Optional[str]:
        """Fetch a file's content from a repository."""
        ...

    def fetch_directory(self, repo: str, path: str, dest: Path) -> bool:
        """Fetch a directory recursively from a repository."""
        ...


class DefaultGitHubClient:
    """Default GitHub client using gh CLI."""

    def check_auth(self) -> bool:
        """Check if GitHub CLI is authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def check_repo_access(self, repo: str) -> bool:
        """Check if user has access to the repository."""
        result = subprocess.run(
            ["gh", "api", f"/repos/{repo}", "--silent"],
            capture_output=True,
        )
        return result.returncode == 0

    def fetch_file(self, repo: str, path: str) -> Optional[str]:
        """Fetch a file's content from a repository."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"/repos/{repo}/contents/{path}",
                    "-H",
                    "Accept: application/vnd.github.raw+json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None

    def fetch_directory(self, repo: str, path: str, dest: Path) -> bool:
        """Fetch a directory recursively from a repository."""
        try:
            result = subprocess.run(
                ["gh", "api", f"/repos/{repo}/contents/{path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            contents = json.loads(result.stdout)

            if isinstance(contents, dict):
                contents = [contents]

            dest.mkdir(parents=True, exist_ok=True)

            for item in contents:
                item_name = item["name"]
                item_path = dest / item_name

                if item["type"] == "file":
                    file_result = subprocess.run(
                        [
                            "gh",
                            "api",
                            item["url"],
                            "-H",
                            "Accept: application/vnd.github.raw+json",
                        ],
                        capture_output=True,
                        check=True,
                    )
                    item_path.write_bytes(file_result.stdout)

                elif item["type"] == "dir":
                    if not self.fetch_directory(repo, item["path"], item_path):
                        return False

            return True

        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return False

    def get_username(self) -> str:
        """Get the current GitHub username."""
        try:
            result = subprocess.run(
                ["gh", "api", "/user", "--jq", ".login"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "github-user-unknown"


class SkillService:
    """Service for managing skills.

    Handles:
    - Listing remote skills from registry
    - Listing local skills
    - Installing skills
    - Extracting skills to PRs
    - Validating skill structure

    Example:
        service = SkillService()

        # List remote skills
        result = service.list_remote()
        if isinstance(result, Success):
            for skill in result.value:
                print(skill.name)

        # Install a skill
        result = service.install("my-skill", Path("/project"))
    """

    def __init__(
        self,
        github_client: Optional[GitHubClient] = None,
        skills_repo: str = DEFAULT_SKILLS_REPO,
    ):
        """Initialize the skill service.

        Args:
            github_client: GitHub client for API operations
            skills_repo: Skills repository (owner/repo format)
        """
        self.github = github_client or DefaultGitHubClient()
        self.skills_repo = skills_repo

    def list_remote(
        self,
        tags: Optional[List[str]] = None,
    ) -> Result[List[Skill]]:
        """List available skills from the remote registry.

        Args:
            tags: Optional list of tags to filter by

        Returns:
            Result containing list of Skill primitives
        """
        if not self.github.check_auth():
            return Failure(
                error="GitHub CLI is not authenticated. Run 'gh auth login'.",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if not self.github.check_repo_access(self.skills_repo):
            return Failure(
                error=f"Cannot access repository '{self.skills_repo}'",
                code=ErrorCode.PERMISSION_DENIED,
                details={"repo": self.skills_repo},
            )

        # Fetch registry
        registry_content = self.github.fetch_file(
            self.skills_repo, SKILLS_REGISTRY_PATH
        )
        if registry_content is None:
            return Failure(
                error="Skills registry not found",
                code=ErrorCode.NOT_FOUND,
            )

        try:
            registry = json.loads(registry_content)
        except json.JSONDecodeError as e:
            return Failure(
                error=f"Invalid skills registry: {e}",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Parse skills
        skills: List[Skill] = []
        for skill_data in registry.get("skills", []):
            skill = Skill(
                name=skill_data.get("name", ""),
                description=skill_data.get("description", ""),
                version=skill_data.get("version", "0.0.0"),
                author=skill_data.get("author", "unknown"),
                tags=skill_data.get("tags", []),
                location="",  # Not installed yet
                path=skill_data.get("path", ""),  # Registry path
                source=SkillSource.REMOTE,
                is_valid=True,
                min_context_harness_version=skill_data.get(
                    "min_context_harness_version"
                ),
            )
            skills.append(skill)

        # Filter by tags
        if tags:
            tags_lower = [t.lower() for t in tags]
            skills = [s for s in skills if any(t.lower() in tags_lower for t in s.tags)]

        return Success(value=skills)

    def list_local(self, project_path: Path) -> Result[List[Skill]]:
        """List skills installed in the local .opencode/skill/ directory.

        Args:
            project_path: Project directory containing .opencode/skill/

        Returns:
            Result containing list of Skill primitives
        """
        skills_dir = project_path / ".opencode" / "skill"

        if not skills_dir.exists():
            return Success(value=[])  # Empty list, not an error

        skills: List[Skill] = []

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"

            if not skill_md.exists():
                skills.append(
                    Skill(
                        name=skill_name,
                        description="(missing SKILL.md)",
                        version="0.0.0",
                        author="unknown",
                        tags=[],
                        location=str(skill_dir),
                        source=SkillSource.LOCAL,
                        is_valid=False,
                    )
                )
                continue

            # Parse frontmatter
            try:
                metadata = self._parse_skill_frontmatter(skill_dir)
                skills.append(
                    Skill(
                        name=skill_name,
                        description=metadata.description,
                        version=metadata.version,
                        author=metadata.author or "unknown",
                        tags=metadata.tags,
                        location=str(skill_md),
                        source=SkillSource.LOCAL,
                        is_valid=True,
                    )
                )
            except Exception:
                skills.append(
                    Skill(
                        name=skill_name,
                        description="(error reading SKILL.md)",
                        version="0.0.0",
                        author="unknown",
                        tags=[],
                        location=str(skill_dir),
                        source=SkillSource.LOCAL,
                        is_valid=False,
                    )
                )

        return Success(value=skills)

    def get_info(self, skill_name: str) -> Result[Skill]:
        """Get detailed information about a specific remote skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Result containing Skill primitive
        """
        result = self.list_remote()
        if isinstance(result, Failure):
            return result

        for skill in result.value:
            if skill.name == skill_name:
                return Success(value=skill)

        return Failure(
            error=f"Skill '{skill_name}' not found",
            code=ErrorCode.SKILL_NOT_FOUND,
            details={"skill_name": skill_name},
        )

    def install(
        self,
        skill_name: str,
        project_path: Path,
        force: bool = False,
    ) -> Result[Skill]:
        """Install a skill from the remote registry.

        Args:
            skill_name: Name of the skill to install
            project_path: Target project directory
            force: If True, overwrite existing skill

        Returns:
            Result containing installed Skill primitive
        """
        # Get skill info
        info_result = self.get_info(skill_name)
        if isinstance(info_result, Failure):
            return info_result

        skill = info_result.value
        skill_dest = project_path / ".opencode" / "skill" / skill_name

        # Check if already exists
        if skill_dest.exists() and not force:
            return Failure(
                error=f"Skill '{skill_name}' already installed at {skill_dest}",
                code=ErrorCode.ALREADY_EXISTS,
                details={"path": str(skill_dest)},
            )

        # Remove existing if force
        if skill_dest.exists() and force:
            shutil.rmtree(skill_dest)

        # Fetch skill files
        if not self.github.fetch_directory(self.skills_repo, skill.path, skill_dest):
            return Failure(
                error=f"Failed to install skill '{skill_name}'",
                code=ErrorCode.SKILL_INSTALL_FAILED,
            )

        # Return updated skill with local path
        skill_md_path = skill_dest / "SKILL.md"
        installed_skill = Skill(
            name=skill.name,
            description=skill.description,
            version=skill.version,
            author=skill.author,
            tags=skill.tags,
            location=str(skill_md_path),
            path=skill.path,  # Keep registry path for reference
            source=SkillSource.LOCAL,
            is_valid=True,
            min_context_harness_version=skill.min_context_harness_version,
        )

        return Success(
            value=installed_skill,
            message=f"Skill '{skill_name}' installed successfully",
        )

    def validate(self, skill_path: Path) -> Result[SkillMetadata]:
        """Validate a skill directory structure.

        Args:
            skill_path: Path to the skill directory

        Returns:
            Result containing SkillMetadata if valid
        """
        skill_md = skill_path / "SKILL.md"

        if not skill_md.exists():
            return Failure(
                error=f"SKILL.md not found in {skill_path}",
                code=ErrorCode.SKILL_INVALID,
                details={"path": str(skill_path)},
            )

        content = skill_md.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return Failure(
                error="SKILL.md missing YAML frontmatter",
                code=ErrorCode.SKILL_INVALID,
            )

        frontmatter_end = content.find("---", 3)
        if frontmatter_end == -1:
            return Failure(
                error="SKILL.md has incomplete frontmatter",
                code=ErrorCode.SKILL_INVALID,
            )

        try:
            metadata = self._parse_skill_frontmatter(skill_path)
        except Exception as e:
            return Failure(
                error=f"Error parsing SKILL.md frontmatter: {e}",
                code=ErrorCode.SKILL_INVALID,
            )

        if not metadata.name:
            return Failure(
                error="SKILL.md frontmatter missing 'name' field",
                code=ErrorCode.SKILL_INVALID,
            )

        if not metadata.description:
            return Failure(
                error="SKILL.md frontmatter missing 'description' field",
                code=ErrorCode.SKILL_INVALID,
            )

        return Success(value=metadata)

    def extract(
        self,
        skill_name: str,
        source_path: Path,
    ) -> Result[str]:
        """Extract a local skill and create a PR to the central repository.

        Args:
            skill_name: Name of the skill to extract
            source_path: Source directory containing .opencode/skill/

        Returns:
            Result containing PR URL
        """
        import re

        # Validate skill name
        if not re.match(r"^[a-zA-Z0-9_-]+$", skill_name):
            return Failure(
                error=f"Invalid skill name '{skill_name}'. Only alphanumeric, hyphens, underscores allowed.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        if not self.github.check_auth():
            return Failure(
                error="GitHub CLI is not authenticated",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if not self.github.check_repo_access(self.skills_repo):
            return Failure(
                error=f"Cannot access repository '{self.skills_repo}'",
                code=ErrorCode.PERMISSION_DENIED,
            )

        skill_source = source_path / ".opencode" / "skill" / skill_name
        if not skill_source.exists():
            return Failure(
                error=f"Skill '{skill_name}' not found at {skill_source}",
                code=ErrorCode.SKILL_NOT_FOUND,
            )

        # Validate skill
        validate_result = self.validate(skill_source)
        if isinstance(validate_result, Failure):
            return validate_result

        metadata = validate_result.value

        # Create branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"skill/{skill_name}-{timestamp}"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmppath = Path(tmpdir)

                # Clone the skills repo (shallow)
                subprocess.run(
                    [
                        "gh",
                        "repo",
                        "clone",
                        self.skills_repo,
                        tmpdir,
                        "--",
                        "--depth=1",
                    ],
                    capture_output=True,
                    check=True,
                )

                # Create and checkout branch
                subprocess.run(
                    ["git", "-C", tmpdir, "checkout", "-b", branch_name],
                    capture_output=True,
                    check=True,
                )

                # Create skill directory in repo
                skill_dest = tmppath / SKILLS_DIR / skill_name
                skill_dest.parent.mkdir(parents=True, exist_ok=True)

                # Copy skill files
                shutil.copytree(skill_source, skill_dest)

                # Update registry
                registry_path = tmppath / SKILLS_REGISTRY_PATH
                if registry_path.exists():
                    registry = json.loads(registry_path.read_text(encoding="utf-8"))
                else:
                    registry = {"schema_version": "1.0", "skills": []}

                # Check if skill already in registry
                existing_idx = None
                for i, s in enumerate(registry.get("skills", [])):
                    if s.get("name") == skill_name:
                        existing_idx = i
                        break

                skill_entry = {
                    "name": skill_name,
                    "description": self._truncate_description(
                        metadata.description, 200
                    ),
                    "version": metadata.version,
                    "author": self.github.get_username(),
                    "tags": metadata.tags,
                    "path": f"{SKILLS_DIR}/{skill_name}",
                }

                if existing_idx is not None:
                    registry["skills"][existing_idx] = skill_entry
                else:
                    registry["skills"].append(skill_entry)

                registry_path.write_text(json.dumps(registry, indent=2) + "\n")

                # Commit changes
                subprocess.run(
                    ["git", "-C", tmpdir, "add", "."],
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    [
                        "git",
                        "-C",
                        tmpdir,
                        "commit",
                        "-m",
                        f"feat(skill): add {skill_name}",
                    ],
                    capture_output=True,
                    check=True,
                )

                # Push branch
                subprocess.run(
                    ["git", "-C", tmpdir, "push", "-u", "origin", branch_name],
                    capture_output=True,
                    check=True,
                )

                # Create PR
                pr_body = f"""## New Skill: {skill_name}

{metadata.description}

### Files Added
- `{SKILLS_DIR}/{skill_name}/SKILL.md`
"""
                for item in skill_dest.rglob("*"):
                    if item.is_file() and item.name != "SKILL.md":
                        rel_path = item.relative_to(skill_dest)
                        pr_body += f"- `{SKILLS_DIR}/{skill_name}/{rel_path}`\n"

                pr_body += "\n---\n_Extracted via ContextHarness skill extractor_\n"

                pr_result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--repo",
                        self.skills_repo,
                        "--title",
                        f"Add skill: {skill_name}",
                        "--body",
                        pr_body,
                        "--head",
                        branch_name,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                pr_url = pr_result.stdout.strip()
                return Success(
                    value=pr_url,
                    message=f"Pull request created successfully",
                )

        except subprocess.CalledProcessError as e:
            error_msg = (
                getattr(e, "stderr", None)
                or getattr(e, "output", None)
                or "Unknown error"
            )
            if isinstance(error_msg, bytes):
                error_msg = error_msg.decode("utf-8", errors="replace")
            return Failure(
                error=f"Error during extraction: {error_msg}",
                code=ErrorCode.UNKNOWN,
            )

    def _parse_skill_frontmatter(self, skill_path: Path) -> SkillMetadata:
        """Parse skill frontmatter from SKILL.md.

        Args:
            skill_path: Path to the skill directory

        Returns:
            SkillMetadata dataclass
        """
        skill_md = skill_path / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        frontmatter_end = content.find("---", 3)
        frontmatter_str = content[3:frontmatter_end].strip()

        try:
            result = yaml.safe_load(frontmatter_str)
            if result is None:
                result = {}
        except yaml.YAMLError:
            result = {}
            for line in frontmatter_str.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    result[key.strip()] = value.strip()

        return SkillMetadata(
            name=str(result.get("name", "")),
            description=str(result.get("description", "")),
            version=str(result.get("version", "0.1.0")),
            author=result.get("author"),
            tags=result.get("tags", []) if isinstance(result.get("tags"), list) else [],
        )

    def _truncate_description(self, text: str, max_length: int) -> str:
        """Truncate description at word boundary with ellipsis."""
        if len(text) <= max_length:
            return text

        truncated = text[: max_length - 3]
        last_space = truncated.rfind(" ")

        if last_space > max_length // 2:
            truncated = truncated[:last_space]

        return truncated + "..."
