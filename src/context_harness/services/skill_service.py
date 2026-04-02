"""Skill service for ContextHarness.

Handles skill listing, installation, extraction, and validation.
Business logic extracted from skills.py module.

Supports both OpenCode (.opencode/skill/) and Claude Code (.claude/skills/) tools.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Protocol

import yaml
from packaging.version import InvalidVersion, Version

from context_harness import __version__ as CH_VERSION
from context_harness.primitives import (
    DEFAULT_SKILLS_REPO,
    ErrorCode,
    Failure,
    RegistryRepo,
    RepoVisibility,
    Result,
    Skill,
    SkillMetadata,
    SkillSource,
    Success,
    ToolDetector,
    ToolTarget,
    ToolType,
    VersionComparison,
    VersionStatus,
)

if TYPE_CHECKING:
    from context_harness.services.registry_client import RegistryClient


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

    def get_username(self) -> str:
        """Get the current authenticated GitHub username."""
        ...

    def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str = "",
    ) -> Optional[str]:
        """Create a new GitHub repository.

        Args:
            name: Repository name (e.g., "my-skills" or "my-org/my-skills")
            private: Whether the repository should be private
            description: Repository description

        Returns:
            HTTPS URL of the created repository, or None on failure
        """
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

    def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str = "",
    ) -> Optional[str]:
        """Create a new GitHub repository using gh CLI.

        Args:
            name: Repository name (e.g., "my-skills" or "my-org/my-skills")
            private: Whether the repository should be private
            description: Repository description

        Returns:
            HTTPS URL of the created repository, or None on failure
        """
        cmd = ["gh", "repo", "create", name]
        cmd.append("--private" if private else "--public")
        if description:
            cmd.extend(["--description", description])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            # gh repo create returns the URL on stdout
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None


class _GitHubClientAdapter:
    """Adapter to wrap GitHubClient in RegistryClient interface.

    This provides backward compatibility for code that still uses
    the GitHubClient interface directly.
    """

    def __init__(self, client: "GitHubClient", repo: str):
        self._client = client
        self._repo = repo

    def check_auth(self) -> bool:
        return self._client.check_auth()

    def check_access(self) -> bool:
        return self._client.check_repo_access(self._repo)

    def fetch_manifest(self) -> Optional[str]:
        return self._client.fetch_file(self._repo, SKILLS_REGISTRY_PATH)

    def fetch_file(self, path: str) -> Optional[bytes]:
        content = self._client.fetch_file(self._repo, path)
        if content:
            return content.encode("utf-8") if isinstance(content, str) else content
        return None

    def fetch_directory(self, path: str, dest: Path) -> bool:
        return self._client.fetch_directory(self._repo, path, dest)


class SkillService:
    """Service for managing skills.

    Handles:
    - Listing remote skills from registry
    - Listing local skills
    - Installing skills
    - Extracting skills to PRs
    - Validating skill structure

    Supports both GitHub and HTTP registries.

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
        github_client: Optional["GitHubClient"] = None,
        registry_client: Optional["RegistryClient"] = None,
        skills_repo: str = DEFAULT_SKILLS_REPO,
    ):
        """Initialize the skill service.

        Args:
            github_client: GitHub client for API operations (deprecated, use registry_client)
            registry_client: Registry client for registry operations
            skills_repo: Skills repository (owner/repo format for GitHub)
        """
        # Support both old and new interfaces
        if registry_client is not None:
            self._registry = registry_client
            self._is_github = False
        elif github_client is not None:
            # Wrap old GitHubClient in adapter
            self._registry = _GitHubClientAdapter(github_client, skills_repo)
            self._is_github = True
        else:
            # Default to GitHub client
            from context_harness.services.registry_client import (
                GitHubRegistryClient,
            )

            self._registry = GitHubRegistryClient(skills_repo)
            self._is_github = True

        # Keep for backward compatibility with extract/init-repo
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
        if not self._registry.check_auth():
            return Failure(
                error="Registry authentication failed. For GitHub, run 'gh auth login'. For HTTP, check your token.",
                code=ErrorCode.AUTH_REQUIRED,
            )

        if not self._registry.check_access():
            return Failure(
                error=f"Cannot access registry '{self.skills_repo}'",
                code=ErrorCode.PERMISSION_DENIED,
                details={"repo": self.skills_repo},
            )

        # Fetch registry
        registry_content = self._registry.fetch_manifest()
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

    def list_local(
        self,
        project_path: Path,
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[List[Skill]]:
        """List skills installed in the local project.

        Scans both .opencode/skill/ and .claude/skills/ directories based on
        tool_target parameter or auto-detection.

        Args:
            project_path: Project directory to scan for skills
            tool_target: Which tool(s) to scan:
                - "opencode": Only .opencode/skill/
                - "claude-code": Only .claude/skills/
                - "both": Scan both directories
                - None: Auto-detect installed tools

        Returns:
            Result containing list of Skill primitives from all scanned directories
        """
        detector = ToolDetector(project_path)
        skills_dirs = detector.get_skills_dirs(tool_target)

        if not skills_dirs:
            return Success(value=[])  # No tools installed

        all_skills: List[Skill] = []
        seen_names: set[str] = set()  # Track duplicates across directories

        for skills_dir in skills_dirs:
            if not skills_dir.exists():
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue

                skill_name = skill_dir.name

                # Skip duplicates (same skill in both directories)
                if skill_name in seen_names:
                    continue
                seen_names.add(skill_name)

                skill_md = skill_dir / "SKILL.md"

                if not skill_md.exists():
                    all_skills.append(
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
                    all_skills.append(
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
                    all_skills.append(
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

        return Success(value=all_skills)

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
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[Skill]:
        """Install a skill from the remote registry.

        Installs to the appropriate skill directory based on tool_target.

        Args:
            skill_name: Name of the skill to install
            project_path: Target project directory
            force: If True, overwrite existing skill
            tool_target: Which tool(s) to install for:
                - "opencode": Install to .opencode/skill/
                - "claude-code": Install to .claude/skills/
                - "both": Install to both directories
                - None: Auto-detect installed tools

        Returns:
            Result containing installed Skill primitive
        """
        # Get skill info
        info_result = self.get_info(skill_name)
        if isinstance(info_result, Failure):
            return info_result

        skill = info_result.value

        # Determine installation directories
        detector = ToolDetector(project_path)

        if tool_target == "both":
            # Install to both directories
            install_dirs = [
                detector._opencode_paths.skills_dir,
                detector._claude_code_paths.skills_dir,
            ]
        elif tool_target == "opencode":
            install_dirs = [detector._opencode_paths.skills_dir]
        elif tool_target == "claude-code":
            install_dirs = [detector._claude_code_paths.skills_dir]
        else:
            # Auto-detect: get dirs from installed tools, or default to OpenCode
            install_dirs = detector.get_skills_dirs(tool_target)
            if not install_dirs:
                # No tools installed, default to OpenCode for backward compatibility
                install_dirs = [detector._opencode_paths.skills_dir]

        # Install to each directory
        installed_path: Optional[Path] = None
        for skills_dir in install_dirs:
            skill_dest = skills_dir / skill_name

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

            # Ensure parent directory exists
            skills_dir.mkdir(parents=True, exist_ok=True)

            # Fetch skill files
            if skill.path and not self._registry.fetch_directory(
                skill.path, skill_dest
            ):
                return Failure(
                    error=f"Failed to install skill '{skill_name}'",
                    code=ErrorCode.SKILL_INSTALL_FAILED,
                )

            # Track the first successful install path for return value
            if installed_path is None:
                installed_path = skill_dest

        # Return updated skill with local path
        skill_md_path = (installed_path / "SKILL.md") if installed_path else None
        installed_skill = Skill(
            name=skill.name,
            description=skill.description,
            version=skill.version,
            author=skill.author,
            tags=skill.tags,
            location=str(skill_md_path) if skill_md_path else "",
            path=skill.path,  # Keep registry path for reference
            source=SkillSource.LOCAL,
            is_valid=True,
            min_context_harness_version=skill.min_context_harness_version,
        )

        return Success(
            value=installed_skill,
            message=f"Skill '{skill_name}' installed successfully",
        )

    def check_skill_updates(
        self,
        skill_name: str,
        project_path: Path,
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[VersionComparison]:
        """Check if updates are available for a specific skill.

        Args:
            skill_name: Name of the skill to check
            project_path: Project directory containing local skills
            tool_target: Which tool directory to search

        Returns:
            Result containing VersionComparison
        """
        # Get current context-harness version
        from context_harness import __version__

        # Get local skill info
        local_result = self.list_local(project_path, tool_target)
        if isinstance(local_result, Failure):
            return local_result

        local_skill = None
        for skill in local_result.value:
            if skill.name == skill_name:
                local_skill = skill
                break

        # Get remote skill info
        remote_result = self.get_info(skill_name)
        if isinstance(remote_result, Failure):
            return remote_result

        remote_skill = remote_result.value

        # If not installed locally, it's an available install (not an upgrade)
        if local_skill is None:
            return Success(
                value=VersionComparison(
                    skill_name=skill_name,
                    local_version=None,
                    remote_version=remote_skill.version,
                    status=VersionStatus.UPGRADE_AVAILABLE,
                    context_harness_min=remote_skill.min_context_harness_version,
                    current_context_harness=__version__,
                )
            )

        # Compare versions
        comparison = self._compare_versions(
            skill_name=skill_name,
            local_version=local_skill.version,
            remote_version=remote_skill.version,
            min_ch_version=remote_skill.min_context_harness_version,
            current_ch_version=__version__,
        )

        return Success(value=comparison)

    def list_outdated_skills(
        self,
        project_path: Path,
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[List[VersionComparison]]:
        """List all locally installed skills with available updates.

        Args:
            project_path: Project directory containing local skills
            tool_target: Which tool directory to search

        Returns:
            Result containing list of VersionComparison for outdated skills
        """
        # Get all local skills
        local_result = self.list_local(project_path, tool_target)
        if isinstance(local_result, Failure):
            return local_result

        # Get all remote skills
        remote_result = self.list_remote()
        if isinstance(remote_result, Failure):
            return remote_result

        # Build remote skills index
        remote_skills = {s.name: s for s in remote_result.value}

        # Get current context-harness version
        from context_harness import __version__

        outdated: List[VersionComparison] = []

        for local_skill in local_result.value:
            remote_skill = remote_skills.get(local_skill.name)
            if remote_skill is None:
                continue  # Skip local-only skills

            comparison = self._compare_versions(
                skill_name=local_skill.name,
                local_version=local_skill.version,
                remote_version=remote_skill.version,
                min_ch_version=remote_skill.min_context_harness_version,
                current_ch_version=__version__,
            )

            # Only include upgradable or incompatible
            if comparison.status in (
                VersionStatus.UPGRADE_AVAILABLE,
                VersionStatus.INCOMPATIBLE,
            ):
                outdated.append(comparison)

        return Success(value=outdated)

    def upgrade_skill(
        self,
        skill_name: str,
        project_path: Path,
        force_compatibility: bool = False,
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[Skill]:
        """Upgrade a skill to the latest version.

        Args:
            skill_name: Name of the skill to upgrade
            project_path: Project directory containing local skills
            force_compatibility: If True, bypass compatibility checks
            tool_target: Which tool directory to upgrade

        Returns:
            Result containing upgraded Skill
        """
        # Check for updates
        update_result = self.check_skill_updates(skill_name, project_path, tool_target)
        if isinstance(update_result, Failure):
            return update_result

        comparison = update_result.value

        # Skill exists in registry but is not installed locally
        if comparison.local_version is None:
            return Failure(
                error=f"Skill '{skill_name}' is not installed locally. Use 'ch skill install {skill_name}' to install it.",
                code=ErrorCode.SKILL_NOT_FOUND,
            )

        # Version comparison failed — cannot determine safe upgrade path
        if comparison.status == VersionStatus.UNKNOWN:
            return Failure(
                error=f"Skill '{skill_name}' has an unrecognizable version (local={comparison.local_version}, remote={comparison.remote_version}). Cannot determine upgrade path.",
                code=ErrorCode.SKILL_UPGRADE_FAILED,
            )

        # Check if upgrade is needed
        if comparison.status == VersionStatus.UP_TO_DATE:
            return Failure(
                error=f"Skill '{skill_name}' is already up to date (v{comparison.local_version})",
                code=ErrorCode.SKILL_NO_UPGRADE_AVAILABLE,
            )

        # Check compatibility
        if comparison.status == VersionStatus.INCOMPATIBLE and not force_compatibility:
            return Failure(
                error=f"Skill '{skill_name}' requires ContextHarness >= {comparison.context_harness_min}, but you have {comparison.current_context_harness}. Upgrade ContextHarness first or use --force to bypass.",
                code=ErrorCode.SKILL_INCOMPATIBLE_VERSION,
                details={
                    "skill_name": skill_name,
                    "required_version": comparison.context_harness_min,
                    "current_version": comparison.current_context_harness,
                },
            )

        # Perform upgrade (reinstall with force=True)
        install_result = self.install(
            skill_name=skill_name,
            project_path=project_path,
            force=True,
            tool_target=tool_target,
        )

        if isinstance(install_result, Success):
            return Success(
                value=install_result.value,
                message=f"Skill '{skill_name}' upgraded from {comparison.local_version} to {comparison.remote_version}",
            )

        # Map install failure to upgrade failure
        if isinstance(install_result, Failure):
            return Failure(
                error=f"Failed to upgrade skill '{skill_name}': {install_result.error}",
                code=ErrorCode.SKILL_UPGRADE_FAILED,
                details=install_result.details,
            )

        return install_result

    def init_registry_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: Optional[str] = None,
    ) -> Result[RegistryRepo]:
        """Initialize a new skills registry repository on GitHub.

        Creates a new GitHub repository scaffolded with the standard skills
        registry structure (skills.json, skill/example-skill/ with SKILL.md
        and version.txt, README.md, and CI/CD workflows). The repository is
        ready to use as a custom skills-repo immediately.

        Workflow: Create repo → Clone to tmpdir → Write scaffold → Commit → Push

        Args:
            name: Repository name (e.g., "my-skills" or "my-org/my-skills").
                  If no org prefix, creates under authenticated user.
            private: Whether the repository should be private (default: True)
            description: Repository description (auto-generated if not provided)

        Returns:
            Result containing RegistryRepo on success, or Failure with details
        """
        # 0. Validate repo name format
        # Allow "repo-name" or "org/repo-name" with alphanumeric, hyphens, underscores, dots
        if not re.match(r"^[a-zA-Z0-9._-]+(/[a-zA-Z0-9._-]+)?$", name):
            return Failure(
                error=f"Invalid repository name '{name}'. Use alphanumeric characters, hyphens, underscores, or dots. Format: 'repo-name' or 'org/repo-name'.",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # 1. Validate gh auth
        if not self.github.check_auth():
            return Failure(
                error="GitHub CLI is not authenticated. Run 'gh auth login'.",
                code=ErrorCode.AUTH_REQUIRED,
            )

        # 2. Check if repo already exists (by trying to access it)
        if self.github.check_repo_access(name):
            return Failure(
                error=f"Repository '{name}' already exists.",
                code=ErrorCode.REPO_ALREADY_EXISTS,
                details={"repo": name},
            )

        # 3. Create the repository
        if description is None:
            description = "ContextHarness skills registry"

        repo_url = self.github.create_repo(
            name,
            private=private,
            description=description,
        )
        if repo_url is None:
            return Failure(
                error=f"Failed to create repository '{name}'. Check your GitHub permissions and that the name is valid.",
                code=ErrorCode.REPO_CREATE_FAILED,
                details={"repo": name},
            )

        # 4. Clone → Scaffold → Commit → Push (all in a temp directory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone the newly created (empty) repo
                subprocess.run(
                    ["gh", "repo", "clone", name, tmpdir],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                tmppath = Path(tmpdir)

                # Write scaffold files
                self._write_registry_scaffold(tmppath, name)

                # Stage, commit, and push
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
                        "feat: initialize skills registry",
                    ],
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", tmpdir, "push"],
                    capture_output=True,
                    check=True,
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
                error=f"Repository created but scaffold push failed: {error_msg}",
                code=ErrorCode.REPO_CREATE_FAILED,
                details={"repo": name, "url": repo_url},
            )

        visibility = RepoVisibility.PRIVATE if private else RepoVisibility.PUBLIC

        return Success(
            value=RegistryRepo(
                name=name,
                url=repo_url,
                visibility=visibility,
            ),
            message=f"Skills registry '{name}' created successfully",
        )

    def upgrade_registry_repo(
        self,
        repo_path: Path,
        *,
        check_only: bool = False,
        dry_run: bool = False,
        force: bool = False,
    ) -> Result[dict]:
        """Upgrade an existing skills registry to the latest scaffold version.

        Detects the current registry version and applies necessary scaffold
        updates while preserving user skills and customizations.

        Legacy registries (without .registry-version) are detected as version
        "0.0.0" and will receive all scaffold updates.

        Args:
            repo_path: Path to the local registry repository
            check_only: Only check for available updates, don't apply them
            dry_run: Show what would be updated without making changes
            force: Overwrite all scaffold files without prompting

        Returns:
            Result containing upgrade details dict on success, or Failure
        """
        if not repo_path.exists():
            return Failure(
                error=f"Registry path does not exist: {repo_path}",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Detect current version (0.0.0 for legacy registries)
        current_version = self._detect_registry_version(repo_path)
        latest_version = CH_VERSION

        # Parse versions for comparison
        try:
            current = Version(current_version)
            latest = Version(latest_version.split("+")[0])  # Remove local version
        except InvalidVersion:
            return Failure(
                error=f"Invalid version format: current={current_version}, latest={latest_version}",
                code=ErrorCode.VALIDATION_ERROR,
            )

        # Check-only mode - just report if upgrade available
        if check_only:
            if force or current < latest:
                return Success(
                    value={
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "upgraded": False,
                        "upgrade_available": True,
                    },
                    message=f"Upgrade available: {current_version} → {latest_version}",
                )
            else:
                return Success(
                    value={
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "upgraded": False,
                        "upgrade_available": False,
                    },
                    message="Registry is already at the latest version",
                )

        # Get list of files to update
        # Note: Critical infrastructure is ALWAYS included, even if version is current
        files_to_update = self._get_scaffold_files_to_update(
            repo_path, current_version, force=force
        )

        # If nothing to update and not forcing, we're done
        if not files_to_update and not force:
            return Success(
                value={
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "upgraded": False,
                    "message": "Already at latest version",
                },
                message="Registry is already at the latest version",
            )

        if dry_run:
            return Success(
                value={
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "upgraded": False,
                    "dry_run": True,
                    "files_to_update": files_to_update,
                },
                message=f"Dry run: would update {len(files_to_update)} file(s)",
            )

        # Apply scaffold updates (preserve user skills)
        updated_files = self._apply_scaffold_updates(
            repo_path, files_to_update, force=force
        )

        # Update version markers
        self._write_scaffold_registry_version(repo_path)
        self._update_json_version_markers(repo_path)

        # Regenerate skills.json with full metadata from skill/ directories
        # This ensures the web frontend has name, description, version, tags
        # instead of stale id-only entries from the old schema
        if self._regenerate_skills_json(repo_path):
            if "skills.json" not in updated_files:
                updated_files.append("skills.json")

        return Success(
            value={
                "current_version": current_version,
                "latest_version": latest_version,
                "upgraded": True,
                "files_updated": updated_files,
            },
            message=f"Registry upgraded: {current_version} → {latest_version}",
        )

    def _detect_registry_version(self, repo_path: Path) -> str:
        """Detect the registry scaffold version.

        Returns "0.0.0" for legacy registries without .registry-version file.
        """
        version_file = repo_path / ".registry-version"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        return "0.0.0"  # Legacy registry

    def _get_scaffold_files_to_update(
        self, repo_path: Path, current_version: str, *, force: bool = False
    ) -> list[str]:
        """Get list of scaffold files that need updating.

        Excludes user skill directories (skill/*) except scaffolded ones.

        Args:
            repo_path: Path to the registry repository
            current_version: Current scaffold version of the registry
            force: If True, include all scaffold files (overwrite mode)

        Returns:
            List of relative file paths to update

        NOTE: When adding new scaffold files to init-repo, add them here too!
        See SCAFFOLD_UPGRADE.md for the complete list and maintenance process.
        """
        # Critical infrastructure - ALWAYS updated (contains path references, must stay in sync)
        # These files reference other files by path and must be updated when scaffold structure changes
        # Also includes files with AI agent instructions that are updated regularly
        critical_infrastructure = [
            "Dockerfile",  # Contains COPY paths that must match actual file locations
            "docker-compose.yml",  # Contains volume mounts and service config
            "registry/nginx.conf",  # Nginx config for serving files
            "registry/web/index.html",  # AI agent instructions are updated regularly
            "registry/web/skill.html",  # Skill detail page format may change
            "llms.txt",  # AI agent installation protocol (emerging standard)
        ]

        # Infrastructure files - added if missing, or with --force
        infrastructure_files = [
            # GitHub workflows
            ".github/workflows/release.yml",
            ".github/workflows/sync-registry.yml",
            ".github/workflows/validate-skills.yml",
            ".github/workflows/auto-rebase.yml",
            # GitHub templates
            ".github/ISSUE_TEMPLATE/new-skill.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            # Scripts
            "scripts/sync-registry.py",
            "scripts/validate-skills.py",
            # Release configuration
            ".releaseplease.json",
            ".release-please-manifest.json",
            # Git configuration
            ".gitignore",
            # Marketplace manifest
            "marketplace.json",
        ]

        # Documentation files - often customized by users
        # Only add these in force mode or if missing
        documentation_files = [
            "README.md",
            "CONTRIBUTING.md",
            "QUICKSTART.md",
        ]

        files_to_update = []

        # ALWAYS include critical infrastructure (regardless of force)
        # These files contain path references that must stay in sync with scaffold structure
        files_to_update.extend(critical_infrastructure)

        if force:
            # Force mode: include all scaffold files for overwrite
            files_to_update.extend(infrastructure_files)
            files_to_update.extend(documentation_files)
        else:
            # Normal mode: only include infrastructure files that don't exist
            for file_path in infrastructure_files:
                full_path = repo_path / file_path
                if not full_path.exists():
                    files_to_update.append(file_path)
            # Documentation files only if missing (users often customize)
            for file_path in documentation_files:
                full_path = repo_path / file_path
                if not full_path.exists():
                    files_to_update.append(file_path)

        # Always add version marker files
        files_to_update.append(".registry-version")

        return files_to_update

    def _apply_scaffold_updates(
        self, repo_path: Path, files_to_update: list[str], *, force: bool
    ) -> list[str]:
        """Apply scaffold file updates while preserving user skills.

        Args:
            repo_path: Path to the registry repository
            files_to_update: List of relative file paths to update
            force: If True, overwrite existing files without checking

        Returns:
            List of files that were actually updated
        """
        # Critical infrastructure - ALWAYS overwritten (contains path references or updated instructions)
        critical_infrastructure = {
            "Dockerfile",
            "docker-compose.yml",
            "registry/nginx.conf",
            "registry/web/index.html",  # AI agent instructions are updated regularly
            "registry/web/skill.html",  # Skill detail page format may change
            "llms.txt",  # AI agent installation protocol (emerging standard)
        }

        updated_files = []

        # Create directory structure if needed
        (repo_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (repo_path / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True, exist_ok=True)
        (repo_path / "scripts").mkdir(parents=True, exist_ok=True)
        (repo_path / "registry" / "web").mkdir(parents=True, exist_ok=True)

        # Extract repo name from git remote or use placeholder
        repo_name = self._get_repo_name_from_git(repo_path)

        # Apply each scaffold file
        for file_path in files_to_update:
            full_path = repo_path / file_path

            # Skip if file exists and not forcing AND not critical infrastructure
            # Critical infrastructure is ALWAYS updated to keep path references in sync
            is_critical = file_path in critical_infrastructure
            if full_path.exists() and not force and not is_critical:
                continue

            # Write the scaffold file
            self._write_single_scaffold_file(repo_path, file_path, repo_name)
            updated_files.append(file_path)

        return updated_files

    def _get_repo_name_from_git(self, repo_path: Path) -> str:
        """Try to get repo name from git remote."""
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()
            # Extract owner/repo from URL
            if "github.com" in url:
                # Handle both https and ssh URLs
                parts = (
                    url.replace(".git", "").replace("git@github.com:", "").split("/")
                )
                if len(parts) >= 2:
                    return f"{parts[-2]}/{parts[-1]}"
        except (subprocess.CalledProcessError, IndexError):
            pass
        return "owner/skills-registry"  # Fallback

    def _write_single_scaffold_file(
        self, repo_path: Path, file_path: str, repo_name: str
    ) -> None:
        """Write a single scaffold file based on its path.

        NOTE: When adding new scaffold files, add them to both:
        1. This writers dictionary
        2. _get_scaffold_files_to_update() list
        See SCAFFOLD_UPGRADE.md for the maintenance process.
        """
        # Map file paths to their writer methods
        writers = {
            # GitHub workflows
            ".github/workflows/release.yml": self._write_scaffold_release_workflow,
            ".github/workflows/sync-registry.yml": self._write_scaffold_sync_registry_workflow,
            ".github/workflows/validate-skills.yml": self._write_scaffold_validate_skills_workflow,
            ".github/workflows/auto-rebase.yml": self._write_scaffold_auto_rebase_workflow,
            # GitHub templates
            ".github/ISSUE_TEMPLATE/new-skill.md": self._write_scaffold_issue_template,
            ".github/PULL_REQUEST_TEMPLATE.md": self._write_scaffold_pr_template,
            # Scripts
            "scripts/sync-registry.py": self._write_scaffold_sync_registry_script,
            "scripts/validate-skills.py": self._write_scaffold_validate_skills_script,
            # HTTP registry (Docker/nginx)
            "Dockerfile": self._write_scaffold_dockerfile,
            "docker-compose.yml": lambda p: self._write_scaffold_docker_compose(
                p, repo_name
            ),
            "registry/nginx.conf": self._write_scaffold_nginx_conf,
            "registry/web/index.html": lambda p: self._write_scaffold_index_html(
                p, repo_name
            ),
            "registry/web/skill.html": lambda p: self._write_scaffold_skill_html(
                p, repo_name
            ),
            # AI agent instructions
            "llms.txt": self._write_scaffold_llms_txt,
            # Release configuration
            ".releaseplease.json": self._write_scaffold_release_please_config,
            ".release-please-manifest.json": self._write_scaffold_release_please_manifest,
            # Git configuration
            ".gitignore": self._write_scaffold_gitignore,
            # Marketplace manifest (requires repo_name)
            "marketplace.json": lambda p: self._write_scaffold_marketplace_json(
                p, repo_name
            ),
            # Documentation (requires repo_name)
            "README.md": lambda p: self._write_scaffold_readme(p, repo_name),
            "CONTRIBUTING.md": lambda p: self._write_scaffold_contributing(
                p, repo_name
            ),
            "QUICKSTART.md": lambda p: self._write_scaffold_quickstart(p, repo_name),
        }

        writer = writers.get(file_path)
        if writer:
            writer(repo_path)
        elif file_path == ".registry-version":
            self._write_scaffold_registry_version(repo_path)

    def _update_json_version_markers(self, repo_path: Path) -> None:
        """Update registry_version in marketplace.json.

        Note: skills.json is handled by _regenerate_skills_json() which
        rewrites the file from scratch during upgrade-repo, so we skip it
        here to avoid redundant I/O.
        """
        # Update marketplace.json
        marketplace_path = repo_path / "marketplace.json"
        if marketplace_path.exists():
            try:
                data = json.loads(marketplace_path.read_text(encoding="utf-8"))
                data["registry_version"] = CH_VERSION
                data["schema_version"] = "1.1"
                marketplace_path.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8"
                )
            except (json.JSONDecodeError, KeyError):
                pass

    def _regenerate_skills_json(self, repo_path: Path) -> bool:
        """Regenerate skills.json by scanning skill/ directories for metadata.

        Parses SKILL.md frontmatter and version.txt for each skill directory,
        producing the full skills.json that the web frontend requires
        (name, version, description, tags, author, content_hash).

        Unlike scripts/sync-registry.py, this does NOT generate per-skill
        .listing.json files — only the top-level skills.json.

        If no skill/ directory exists, falls back to updating version markers
        in any existing skills.json without altering the skills list.

        Args:
            repo_path: Path to the registry repository

        Returns:
            True if skills.json was written, False otherwise.
        """
        skills_dir = repo_path / "skill"
        if not skills_dir.exists():
            # No skill/ dir — still update version markers in existing skills.json
            skills_json_path = repo_path / "skills.json"
            if skills_json_path.exists():
                try:
                    data = json.loads(skills_json_path.read_text(encoding="utf-8"))
                    data["registry_version"] = CH_VERSION
                    data["schema_version"] = "1.1"
                    skills_json_path.write_text(
                        json.dumps(data, indent=2) + "\n", encoding="utf-8"
                    )
                    return True
                except (json.JSONDecodeError, OSError):
                    pass
            return False

        skills_json_path = repo_path / "skills.json"

        # Collect skill metadata from each skill directory
        skills = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Parse frontmatter using existing method
            try:
                metadata = self._parse_skill_frontmatter(skill_dir)
            except Exception:
                # If parsing fails, use directory name as fallback
                metadata = SkillMetadata(
                    name=skill_dir.name,
                    description="",
                )

            # Read version from version.txt (fall back to frontmatter or 0.1.0)
            version = metadata.version or "0.1.0"
            version_txt = skill_dir / "version.txt"
            if version_txt.exists():
                version = version_txt.read_text(encoding="utf-8").strip() or version

            # Compute content hash for change detection
            content_hash = hashlib.sha256(skill_md.read_bytes()).hexdigest()[:16]

            skill_entry: dict = {
                "name": metadata.name or skill_dir.name,
                "description": metadata.description or "",
                "version": version,
                "author": metadata.author or "",
                "tags": metadata.tags or [],
                "path": f"skill/{skill_dir.name}",
                "content_hash": content_hash,
            }

            # Include min_context_harness_version if present in frontmatter
            # to maintain parity with sync-registry.py CI output
            try:
                raw_fm = skill_md.read_text(encoding="utf-8")
                fm_end = raw_fm.find("---", 3)
                if fm_end > 0:
                    fm_data = yaml.safe_load(raw_fm[3:fm_end].strip()) or {}
                    min_ch = fm_data.get("min_context_harness_version")
                    if min_ch:
                        skill_entry["min_context_harness_version"] = str(min_ch)
            except Exception:
                pass  # Don't fail on optional field

            skills.append(skill_entry)

        # Write the full skills.json
        registry = {
            "schema_version": "1.1",
            "registry_version": CH_VERSION,
            "skills": skills,
        }
        try:
            skills_json_path.write_text(
                json.dumps(registry, indent=2) + "\n", encoding="utf-8"
            )
            return True
        except OSError:
            return False  # Don't fail the upgrade if skills.json can't be written

    def _write_registry_scaffold(self, repo_path: Path, repo_name: str) -> None:
        """Write the full skills registry scaffold with CI/CD automation.

        Creates the complete file tree for a skills registry with:
        - release-please for automated per-skill semantic versioning
        - GitHub Actions for validation, release, and registry sync
        - Example skill with proper structure
        - Contributing and quickstart documentation

        Lifecycle:
            1. Author edits skill/my-skill/SKILL.md (NO version in frontmatter)
            2. Author commits with conventional commits (feat:, fix:, etc.)
            3. release-please creates release PR bumping version.txt + CHANGELOG.md
            4. Merge release PR → scoped tag (my-skill@v1.0.0) + GitHub Release
            5. sync-registry.yml rebuilds skills.json from all skills

        Args:
            repo_path: Path to the cloned repository
            repo_name: Repository name for use in templates
        """
        # Create directory structure
        (repo_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (repo_path / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True, exist_ok=True)
        (repo_path / "scripts").mkdir(parents=True, exist_ok=True)
        (repo_path / "skill" / "example-skill").mkdir(parents=True, exist_ok=True)
        (repo_path / "skill" / "skill-release" / "references").mkdir(
            parents=True, exist_ok=True
        )

        # --- Root files ---
        self._write_scaffold_skills_json(repo_path)
        self._write_scaffold_release_please_config(repo_path)
        self._write_scaffold_release_please_manifest(repo_path)
        self._write_scaffold_gitignore(repo_path)
        self._write_scaffold_readme(repo_path, repo_name)
        self._write_scaffold_contributing(repo_path, repo_name)
        self._write_scaffold_quickstart(repo_path, repo_name)

        # --- GitHub templates ---
        self._write_scaffold_pr_template(repo_path)
        self._write_scaffold_issue_template(repo_path)

        # --- GitHub Actions workflows ---
        self._write_scaffold_release_workflow(repo_path)
        self._write_scaffold_sync_registry_workflow(repo_path)
        self._write_scaffold_validate_skills_workflow(repo_path)
        self._write_scaffold_auto_rebase_workflow(repo_path)

        # --- Scripts ---
        self._write_scaffold_sync_registry_script(repo_path)
        self._write_scaffold_validate_skills_script(repo_path)

        # --- Example skill ---
        self._write_scaffold_example_skill(repo_path)

        # --- Skill-release skill (bundled operational guide) ---
        self._write_scaffold_skill_release(repo_path)

        # --- HTTP Registry hosting (Docker/nginx) ---
        self._write_scaffold_http_registry(repo_path, repo_name)

        # --- Marketplace manifest for plugin discovery ---
        self._write_scaffold_marketplace_json(repo_path, repo_name)

        # --- Registry version marker (for upgrade detection) ---
        self._write_scaffold_registry_version(repo_path)

    # -- Scaffold file writers -----------------------------------------------

    def _write_scaffold_skills_json(self, repo_path: Path) -> None:
        """Write skills.json — registry manifest with scaffolded skills.

        When upgrading an existing repo, preserves existing skills array
        to avoid clearing actual skill registrations. The sync-registry.py
        script will rebuild this from skill directories during CI.
        """
        skills_json_path = repo_path / "skills.json"

        # If file exists and has skills key, preserve the content
        if skills_json_path.exists():
            try:
                existing = json.loads(skills_json_path.read_text())
                # Preserve if it's a dict with a skills key (even if empty)
                if isinstance(existing, dict) and "skills" in existing:
                    # Update schema version but preserve skills
                    existing["schema_version"] = "1.1"
                    existing["registry_version"] = CH_VERSION
                    skills_json_path.write_text(
                        json.dumps(existing, indent=2) + "\n", encoding="utf-8"
                    )
                    return
            except json.JSONDecodeError:
                pass

        # Default template for new registries
        registry = {
            "schema_version": "1.1",
            "registry_version": CH_VERSION,
            "skills": [
                {
                    "name": "example-skill",
                    "description": "An example skill to demonstrate the registry structure",
                    "version": "0.1.0",
                    "author": "your-name",
                    "tags": ["example", "getting-started"],
                },
                {
                    "name": "skill-release",
                    "description": "Guide for creating, versioning, and releasing skills in a ContextHarness skills registry repository.",
                    "version": "0.1.0",
                    "author": None,
                    "tags": [],
                },
            ],
        }
        skills_json_path.write_text(
            json.dumps(registry, indent=2) + "\n", encoding="utf-8"
        )

    def _write_scaffold_release_please_config(self, repo_path: Path) -> None:
        """Write release-please-config.json for monorepo per-skill releases."""
        config = {
            "$schema": "https://raw.githubusercontent.com/googleapis/"
            "release-please/main/schemas/config.json",
            "separate-pull-requests": True,
            "include-component-in-tag": True,
            "tag-separator": "@",
            "packages": {
                "skill/example-skill": {
                    "release-type": "simple",
                    "component": "example-skill",
                },
                "skill/skill-release": {
                    "release-type": "simple",
                    "component": "skill-release",
                },
            },
        }
        (repo_path / "release-please-config.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def _write_scaffold_release_please_manifest(self, repo_path: Path) -> None:
        """Write .release-please-manifest.json with initial versions.

        Preserves existing version entries when upgrading an existing repo
        to avoid resetting actual release versions to template defaults.
        """
        manifest_path = repo_path / ".release-please-manifest.json"

        # Default template versions
        default_manifest = {
            "skill/example-skill": "0.1.0",
            "skill/skill-release": "0.1.0",
        }

        # If file exists, preserve existing versions
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text())
                # Only merge if existing is a dict with string keys/values
                if isinstance(existing, dict) and all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in existing.items()
                ):
                    # Merge: existing versions take precedence over defaults
                    manifest = {**default_manifest, **existing}
                else:
                    manifest = default_manifest
            except json.JSONDecodeError:
                manifest = default_manifest
        else:
            manifest = default_manifest

        (manifest_path).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def _write_scaffold_gitignore(self, repo_path: Path) -> None:
        """Write .gitignore for the registry repo."""
        content = """\
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
"""
        (repo_path / ".gitignore").write_text(content, encoding="utf-8")

    def _write_scaffold_registry_version(self, repo_path: Path) -> None:
        """Write .registry-version file for upgrade detection.

        This file tracks the ContextHarness CLI version that created or
        last upgraded the registry scaffold. Used by upgrade-repo to
        determine what updates are needed.
        """
        (repo_path / ".registry-version").write_text(CH_VERSION, encoding="utf-8")

    def _write_scaffold_readme(self, repo_path: Path, repo_name: str) -> None:
        """Write README.md with lifecycle documentation."""
        content = f"""\
# {repo_name}

Skills registry for [ContextHarness](https://github.com/co-labs-co/context-harness).

## ⚠️ Setup Required

After creating this repo, configure GitHub Actions permissions:

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select **Read and write permissions**
3. Check **Allow GitHub Actions to create and approve pull requests**

Without these settings, release-please cannot create release PRs.

## How It Works

This registry uses **fully automated semantic versioning**. Authors never touch
version numbers — just write content and use conventional commits:

```mermaid
flowchart TD
    A["Author edits skill/my-skill/SKILL.md"] --> B["Commits: feat: add new examples"]
    B --> C["PR merged to main"]
    C --> D["release-please detects path-scoped change"]
    D --> E["Creates release PR"]
    E --> |"Bumps version.txt & CHANGELOG.md"| F["Release PR merged"]
    F --> G["Tag: my-skill@v0.2.0 + GitHub Release"]
    G --> H["sync-registry rebuilds skills.json"]
    H --> I["CLI: context-harness skill outdated"]

    style A fill:#f9f,stroke:#333
    style G fill:#9f9,stroke:#333
    style I fill:#9cf,stroke:#333
```

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for adding your first skill.

## Configure as Your Registry

```bash
# Set for current project
context-harness config set skills-repo {repo_name}

# Set for all projects (user-level)
context-harness config set skills-repo {repo_name} --global
```

## HTTP Hosting (Optional)

Host this registry via HTTP for AI agents or air-gapped environments:

```bash
# Build and run with Docker
docker-compose up -d

# Registry available at http://localhost:8080
```

### AI Agent Discovery

The registry includes `llms.txt` - an emerging standard for LLM-specific instructions. AI coding assistants read this file to understand how to install skills:

```
http://localhost:8080/llms.txt
```

### Install from HTTP Registry

```bash
# Point CLI at HTTP registry
context-harness skill use-registry http://localhost:8080

# Or install directly
context-harness skill install <skill-name> --registry http://localhost:8080
```

## Commit Convention

| Commit prefix | Version bump | Example |
|---------------|-------------|---------|
| `fix:` | Patch (0.0.x) | `fix: correct typo in examples` |
| `feat:` | Minor (0.x.0) | `feat: add error handling patterns` |
| `feat!:` | Major (x.0.0) | `feat!: restructure skill format` |
| `docs:` | No release | `docs: update readme` |
| `chore:` | No release | `chore: clean up formatting` |

## Structure

```
{repo_name}/
├── .github/
│   └── workflows/
│       ├── release.yml           # release-please automation
│       ├── sync-registry.yml     # Rebuilds skills.json post-release
│       ├── validate-skills.yml   # PR validation checks
│       └── auto-rebase.yml       # Auto-rebase PRs when shared files change
├── scripts/
│   ├── sync-registry.py          # Parses skills → skills.json
│   └── validate_skills.py        # Pydantic-based validation
├── registry/                     # HTTP hosting (optional)
│   ├── nginx.conf                # CORS-enabled nginx config
│   └── web/
│       ├── index.html            # Skill browser UI
│       └── skill.html            # Individual skill pages
├── skill/
│   └── example-skill/
│       ├── SKILL.md              # Skill content (no version field)
│       └── version.txt           # Managed by release-please
├── Dockerfile                    # nginx container for HTTP hosting
├── docker-compose.yml            # Easy local deployment
├── llms.txt                      # AI agent installation instructions
├── skills.json                   # Auto-maintained registry manifest
├── marketplace.json              # Plugin marketplace compatibility
├── release-please-config.json    # Per-skill release configuration
├── .release-please-manifest.json # Current versions (CI-managed)
├── CONTRIBUTING.md
├── QUICKSTART.md
└── README.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or update skills.
"""
        (repo_path / "README.md").write_text(content, encoding="utf-8")

    def _write_scaffold_contributing(self, repo_path: Path, repo_name: str) -> None:
        """Write CONTRIBUTING.md with skill authoring guidelines."""
        content = f"""\
# Contributing to {repo_name}

## Adding a New Skill

1. **Create the skill directory**:
   ```bash
   mkdir -p skill/my-skill
   ```

2. **Create SKILL.md** with frontmatter (no version field!):
   ```markdown
   ---
   name: my-skill
   description: Brief description of what this skill does
   author: your-name
   tags:
     - category
   ---

   # My Skill

   Your skill content here...
   ```

3. **Create version.txt** (bootstrapped at 0.1.0):
   ```bash
   echo "0.1.0" > skill/my-skill/version.txt
   ```

4. **Register with release-please** — add to `release-please-config.json`:
   ```json
   {{
     "packages": {{
       "skill/my-skill": {{
         "release-type": "simple",
         "component": "my-skill"
       }}
     }}
   }}
   ```

   And to `.release-please-manifest.json`:
   ```json
   {{
     "skill/my-skill": "0.1.0"
   }}
   ```

5. **Commit and push**:
   ```bash
   git add skill/my-skill/ release-please-config.json .release-please-manifest.json
   git commit -m "feat: add my-skill"
   git push origin main
   ```

## Updating a Skill

1. Edit the skill's `SKILL.md` file
2. Commit with a conventional commit message:
   - `fix: correct typo in examples` → patch bump
   - `feat: add new section on error handling` → minor bump
   - `feat!: restructure skill format` → major bump
3. Push and merge your PR
4. release-please will automatically create a release PR

## Important Notes

- **Never edit `version.txt` manually** — release-please manages it
- **Never edit `skills.json` manually** — CI rebuilds it after releases
- **Never add `version` to SKILL.md frontmatter** — it lives in `version.txt`
- The `name` field in SKILL.md **must match** the directory name
"""
        (repo_path / "CONTRIBUTING.md").write_text(content, encoding="utf-8")

    def _write_scaffold_quickstart(self, repo_path: Path, repo_name: str) -> None:
        """Write QUICKSTART.md with step-by-step first skill guide."""
        content = f"""\
# Quick Start: Add Your First Skill

This guide walks you through adding a skill to **{repo_name}**.

## Prerequisites

- Git installed
- GitHub CLI (`gh`) installed and authenticated
- Repository cloned locally

## ⚠️ Required GitHub Settings

Before using this registry, configure GitHub Actions permissions:

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select **Read and write permissions**
3. Check **Allow GitHub Actions to create and approve pull requests**

Without these settings, release-please cannot create release PRs.

## Steps

### 1. Create the Skill

```bash
# Create skill directory
mkdir -p skill/my-first-skill

# Create SKILL.md
cat > skill/my-first-skill/SKILL.md << 'SKILLEOF'
---
name: my-first-skill
description: My first custom skill
author: your-name
tags:
  - getting-started
---

# My First Skill

Instructions and content for your skill go here.
SKILLEOF

# Bootstrap version (required for release-please)
echo "0.1.0" > skill/my-first-skill/version.txt
```

### 2. Register with Release-Please

Add the skill to `release-please-config.json` under `"packages"`:

```json
"skill/my-first-skill": {{
  "release-type": "simple",
  "component": "my-first-skill"
}}
```

Add to `.release-please-manifest.json`:

```json
"skill/my-first-skill": "0.1.0"
```

### 3. Commit and Push

```bash
git add .
git commit -m "feat: add my-first-skill"
git push origin main
```

### 4. What Happens Next

1. **release-please** creates a release PR bumping `version.txt`
2. Merge the release PR → tag `my-first-skill@v0.1.0` is created
3. **sync-registry** rebuilds `skills.json` automatically
4. Users can now install: `context-harness skill install my-first-skill`

## Install Your Skill

```bash
# Configure this registry (one time)
context-harness config set skills-repo {repo_name}

# Install
context-harness skill install my-first-skill
```
"""
        (repo_path / "QUICKSTART.md").write_text(content, encoding="utf-8")

    def _write_scaffold_pr_template(self, repo_path: Path) -> None:
        """Write .github/PULL_REQUEST_TEMPLATE.md."""
        content = """\
## Summary

<!-- Brief description of changes -->

## Type of Change

- [ ] New skill (`feat: add skill-name`)
- [ ] Skill update (`feat:` or `fix:` depending on change)
- [ ] Documentation (`docs:`)
- [ ] CI/Infrastructure (`ci:` or `chore:`)

## Checklist

- [ ] SKILL.md has valid frontmatter (`name`, `description`, `author`, `tags`)
- [ ] `name` in frontmatter matches directory name
- [ ] No `version` field in SKILL.md frontmatter
- [ ] `version.txt` exists (for new skills, bootstrapped at `0.1.0`)
- [ ] release-please config updated (for new skills)
- [ ] Commit message follows conventional commits format
"""
        (repo_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_issue_template(self, repo_path: Path) -> None:
        """Write .github/ISSUE_TEMPLATE/new-skill.md."""
        content = """\
---
name: New Skill Request
about: Propose a new skill for the registry
title: "[skill] "
labels: new-skill
---

## Skill Name

<!-- Must be lowercase, hyphenated: my-skill-name -->

## Description

<!-- What does this skill help agents do? -->

## Use Cases

<!-- When should an agent use this skill? -->

## Tags

<!-- Categories (e.g., python, testing, deployment) -->

## Content Outline

<!-- High-level outline of what the skill would contain -->
"""
        (repo_path / ".github" / "ISSUE_TEMPLATE" / "new-skill.md").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_release_workflow(self, repo_path: Path) -> None:
        """Write .github/workflows/release.yml for release-please."""
        content = """\
name: Release

on:
  push:
    branches:
      - main

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          manifest-file: .release-please-manifest.json
          config-file: release-please-config.json
"""
        (repo_path / ".github" / "workflows" / "release.yml").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_sync_registry_workflow(self, repo_path: Path) -> None:
        """Write .github/workflows/sync-registry.yml for post-release sync."""
        content = """\
name: Sync Registry

on:
  push:
    branches:
      - main
    paths:
      - "skill/*/version.txt"
      - "skill/*/SKILL.md"

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install python-frontmatter

      - name: Rebuild skills.json
        run: python scripts/sync-registry.py

      - name: Commit updated skills.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add skills.json marketplace.json skill/*/.listing.json
          git diff --cached --quiet || git commit -m "chore: sync registry manifests [skip ci]"
          git push
"""
        (repo_path / ".github" / "workflows" / "sync-registry.yml").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_validate_skills_workflow(self, repo_path: Path) -> None:
        """Write .github/workflows/validate-skills.yml for PR checks."""
        content = """\
name: Validate Skills

on:
  pull_request:
    paths:
      - "skill/**"
      - "release-please-config.json"
      - ".release-please-manifest.json"

permissions:
  contents: read
  pull-requests: write

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install python-frontmatter pydantic>=2.0 semver

      - name: Validate skills
        id: validate
        run: python scripts/validate_skills.py
        continue-on-error: true

      - name: Read validation report
        if: always()
        id: report
        run: |
          if [ -f validation-report.md ]; then
            {
              echo 'REPORT<<REPORTEOF'
              cat validation-report.md
              echo 'REPORTEOF'
            } >> "$GITHUB_OUTPUT"
          fi

      - name: Post PR comment
        if: always() && steps.report.outputs.REPORT
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          header: skill-validation
          message: ${{ steps.report.outputs.REPORT }}

      - name: Fail if validation errors
        if: steps.validate.outcome == 'failure'
        run: exit 1
"""
        (repo_path / ".github" / "workflows" / "validate-skills.yml").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_auto_rebase_workflow(self, repo_path: Path) -> None:
        """Write .github/workflows/auto-rebase.yml for automatic PR rebasing.

        Automatically rebases PRs when main changes to resolve conflicts
        with shared files (skills.json, release-please-config.json, etc.)
        that occur when multiple skills are extracted in parallel.

        For JSON files with conflicts, accepts main's version then rebuilds
        using sync-registry.py to include all skills.
        """
        content = """\
name: Auto Rebase

on:
  push:
    branches:
      - main
    paths:
      - "skills.json"
      - "release-please-config.json"
      - ".release-please-manifest.json"

permissions:
  contents: write
  pull-requests: write

jobs:
  rebase:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install python-frontmatter

      - name: Rebase open PRs with conflict resolution
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Configure git identity for rebase commits
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

          # Get open PRs and process each one
          gh pr list --base main --state open --json number,headRefName \\
            --jq '.[] | "\\(.number) \\(.headRefName)"' \\
            | while read -r pr_number pr_branch; do
              if [ -z "$pr_number" ] || [ -z "$pr_branch" ]; then
                continue
              fi

              echo "Attempting to rebase PR #$pr_number ($pr_branch)"

              # Fetch the PR branch
              git fetch origin "$pr_branch" || continue

              # Checkout the PR branch
              git checkout "$pr_branch" || continue

              # Try to rebase onto main
              if git rebase origin/main; then
                echo "Rebase successful, pushing..."
                git push origin "$pr_branch" --force-with-lease
                echo "✅ PR #$pr_number rebased successfully"
              else
                echo "⚠️ Rebase has conflicts, attempting auto-resolution..."

                # Get list of conflicted files
                CONFLICTS=$(git diff --name-only --diff-filter=U)

                if echo "$CONFLICTS" | grep -q ".json"; then
                  echo "Found JSON conflicts: $CONFLICTS"

                  # Resolve each conflicting JSON file by merging
                  python3 << 'PYRESOLVE'
import json
import subprocess
import os

# Get conflicted files
result = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=U'],
                       capture_output=True, text=True)
conflicts = [f for f in result.stdout.strip().split('\n') if f and f.endswith('.json')]

for filepath in conflicts:
    if not os.path.exists(filepath):
        continue

    # During rebase conflict:
    # - :2:filepath = stage 2 = "ours" = upstream (main)
    # - :3:filepath = stage 3 = "theirs" = commit being replayed (PR)

    # Get main's version (stage 2)
    main_result = subprocess.run(
        ['git', 'show', ':2:' + filepath],
        capture_output=True, text=True
    )
    try:
        main_data = json.loads(main_result.stdout) if main_result.returncode == 0 else {}
    except:
        main_data = {}

    # Get PR's version (stage 3 - the commit being replayed during rebase)
    ours_result = subprocess.run(
        ['git', 'show', ':3:' + filepath],
        capture_output=True, text=True
    )
    try:
        ours_data = json.loads(ours_result.stdout) if ours_result.returncode == 0 else {}
    except:
        ours_data = {}

    # Deep merge: overlay PR's changes onto main's base
    def deep_merge(base, overlay):
        if isinstance(base, dict) and isinstance(overlay, dict):
            result = dict(base)
            for k, v in overlay.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = deep_merge(result[k], v)
                else:
                    result[k] = v
            return result
        return overlay

    merged = deep_merge(main_data, ours_data)

    # Write merged file
    with open(filepath, 'w') as f:
        json.dump(merged, f, indent=2, sort_keys=True)
        f.write('\n')

    print(f"Merged {filepath}")

# Also rebuild skills.json from all skills on disk
subprocess.run(['python', 'scripts/sync-registry.py'], capture_output=True)
print("Rebuilt skills.json")
PYRESOLVE

                  # Stage all resolved files
                  git add skills.json release-please-config.json .release-please-manifest.json 2>/dev/null || true

                  # Continue rebase
                  if git rebase --continue; then
                    echo "Auto-resolution successful, pushing..."
                    git push origin "$pr_branch" --force-with-lease
                    echo "✅ PR #$pr_number rebased with conflict resolution"
                  else
                    echo "❌ Could not complete rebase even after conflict resolution"
                    git rebase --abort
                  fi
                else
                  echo "❌ Non-JSON conflicts detected, cannot auto-resolve"
                  git rebase --abort
                fi
              fi

              # Go back to main for next iteration
              git checkout main
            done
"""
        (repo_path / ".github" / "workflows" / "auto-rebase.yml").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_sync_registry_script(self, repo_path: Path) -> None:
        """Write scripts/sync-registry.py to rebuild skills.json."""
        content = '''\
#!/usr/bin/env python3
"""Rebuild skills.json from skill directories.

Parses SKILL.md frontmatter and version.txt for each skill,
then writes the consolidated skills.json registry manifest.
Also generates .listing.json for each skill for frontend file discovery.

Usage:
    python scripts/sync-registry.py
"""

import hashlib
import json
from pathlib import Path

import frontmatter


def build_listing(skill_dir: Path) -> dict:
    """Build .listing.json for a skill directory."""
    listing = {
        "files": [],
        "directories": [],
        "directory_files": {},
    }

    skip_names = {".listing.json", ".gitkeep", ".DS_Store", "__pycache__"}

    for item in skill_dir.iterdir():
        if item.name in skip_names:
            continue

        if item.is_file():
            listing["files"].append(item.name)
        elif item.is_dir():
            listing["directories"].append(item.name)
            dir_files = []
            for subitem in item.iterdir():
                if subitem.name not in skip_names and subitem.is_file():
                    dir_files.append(subitem.name)
            if dir_files:
                listing["directory_files"][item.name] = sorted(dir_files)

    listing["files"] = sorted(listing["files"])
    listing["directories"] = sorted(listing["directories"])

    return listing


def get_registry_version() -> str:
    """Read registry version from .registry-version file."""
    version_file = Path(".registry-version")
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def build_registry() -> dict:
    """Scan skill/ directories and build registry manifest."""
    skills_dir = Path("skill")
    skills = []

    if not skills_dir.exists():
        return {
            "schema_version": "1.1",
            "registry_version": get_registry_version(),
            "skills": [],
        }

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        version_txt = skill_dir / "version.txt"

        if not skill_md.exists():
            continue

        # Parse frontmatter
        post = frontmatter.load(str(skill_md))
        metadata = post.metadata

        # Read version from version.txt (fall back to 0.1.0)
        version = "0.1.0"
        if version_txt.exists():
            version = version_txt.read_text().strip()

        # Compute content hash for change detection
        content_hash = hashlib.sha256(skill_md.read_bytes()).hexdigest()[:16]

        skills.append(
            {
                "name": metadata.get("name", skill_dir.name),
                "description": metadata.get("description", ""),
                "version": version,
                "author": metadata.get("author", ""),
                "tags": metadata.get("tags", []),
                "path": f"skill/{skill_dir.name}",
                "min_context_harness_version": metadata.get(
                    "min_context_harness_version"
                ),
                "content_hash": content_hash,
            }
        )

        # Generate .listing.json for frontend file discovery
        listing = build_listing(skill_dir)
        (skill_dir / ".listing.json").write_text(
            json.dumps(listing, indent=2) + "\\n", encoding="utf-8"
        )

    return {
        "schema_version": "1.1",
        "registry_version": get_registry_version(),
        "skills": skills,
    }


def update_marketplace_json(skills: list) -> None:
    """Update marketplace.json with current skills list.

    The marketplace.json provides a standardized format for plugin
    marketplace discovery, It's regenerated alongside skills.json
    whenever skills are updated.
    """
    import os

    # Determine registry URL from environment or default
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    registry_url = ""
    if repo:
        parts = repo.split("/")
        if len(parts) == 2:
            owner, name = parts
            registry_url = f"https://{owner}.github.io/{name}"

    # Load existing marketplace.json to preserve metadata
    marketplace_path = Path("marketplace.json")
    if marketplace_path.exists():
        try:
            existing = json.loads(marketplace_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    # Update skills list while preserving other fields
    marketplace = {
        "$schema": "https://context-harness.dev/schemas/marketplace.json",
        "schema_version": existing.get("schema_version", "1.0"),
        "registry_version": get_registry_version(),
        "name": existing.get("name", repo),
        "display_name": existing.get("display_name", f"{repo.split('/')[-1]} Skills Registry" if repo else "Skills Registry"),
        "description": existing.get("description", "ContextHarness skills registry with versioned skills"),
        "registry_type": "context-harness",
        "registry_url": existing.get("registry_url", registry_url),
        "skills_endpoint": "/skills.json",
        "skill_base_path": "/skill",
        "website": existing.get("website", f"https://github.com/{repo}" if repo else ""),
        "maintainer": existing.get("maintainer", {}),
        "compatibility": existing.get("compatibility", {
            "context_harness": ">=0.5.0",
            "claude_code": ">=1.0.0",
        }),
        "skills": skills,
    }

    marketplace_path.write_text(
        json.dumps(marketplace, indent=2) + "\\n", encoding="utf-8"
    )
    print(f"Updated marketplace.json with {len(skills)} skill(s)")


def main() -> None:
    """Rebuild and write skills.json and marketplace.json."""
    registry = build_registry()

    Path("skills.json").write_text(
        json.dumps(registry, indent=2) + "\\n", encoding="utf-8"
    )

    print(f"Updated skills.json with {len(registry['skills'])} skill(s)")
    for skill in registry["skills"]:
        print(f"  - {skill['name']} v{skill['version']}")

    # Also update marketplace.json
    update_marketplace_json(registry["skills"])


if __name__ == "__main__":
    main()
'''
        (repo_path / "scripts" / "sync-registry.py").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_validate_skills_script(self, repo_path: Path) -> None:
        """Write scripts/validate_skills.py for PR validation."""
        content = '''\
#!/usr/bin/env python3
"""Validate skill directories for CI checks.

Checks:
- SKILL.md exists and has valid frontmatter
- name field matches directory name
- No version field in frontmatter (managed by release-please)
- version.txt exists
- No duplicate skill names
- Tags are a list of strings

Writes validation-report.md for PR comment integration.

Usage:
    python scripts/validate_skills.py
"""

import sys
from pathlib import Path
from typing import List

import frontmatter
from pydantic import BaseModel, field_validator


class SkillFrontmatter(BaseModel):
    """Expected SKILL.md frontmatter schema."""

    name: str
    description: str
    author: str = ""
    tags: List[str] = []
    min_context_harness_version: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> List[str]:
        """Ensure tags is a list of strings."""
        if not isinstance(v, list):
            msg = "tags must be a list"
            raise ValueError(msg)
        for tag in v:
            if not isinstance(tag, str):
                msg = f"tag must be a string, got {type(tag).__name__}"
                raise ValueError(msg)
        return v


def validate_skill(skill_dir: Path) -> List[str]:
    """Validate a single skill directory. Returns list of errors."""
    errors: List[str] = []
    skill_name = skill_dir.name

    # Check SKILL.md exists
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{skill_name}: missing SKILL.md")
        return errors

    # Parse frontmatter
    try:
        post = frontmatter.load(str(skill_md))
        metadata = post.metadata
    except Exception as e:
        errors.append(f"{skill_name}: failed to parse frontmatter: {e}")
        return errors

    # Validate schema
    try:
        parsed = SkillFrontmatter(**metadata)
    except Exception as e:
        errors.append(f"{skill_name}: invalid frontmatter: {e}")
        return errors

    # Name must match directory
    if parsed.name != skill_name:
        errors.append(
            f"{skill_name}: name '{parsed.name}' does not match "
            f"directory '{skill_name}'"
        )

    # Version must NOT be in frontmatter
    if "version" in metadata:
        errors.append(
            f"{skill_name}: remove 'version' from frontmatter "
            f"(managed by release-please via version.txt)"
        )

    # version.txt must exist
    version_txt = skill_dir / "version.txt"
    if not version_txt.exists():
        errors.append(f"{skill_name}: missing version.txt (bootstrap with '0.1.0')")

    return errors


def main() -> None:
    """Validate all skills and write report."""
    skills_dir = Path("skill")
    all_errors: List[str] = []
    validated_count = 0
    skill_names: List[str] = []

    if not skills_dir.exists():
        print("No skill/ directory found")
        sys.exit(0)

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        validated_count += 1
        skill_names.append(skill_dir.name)
        errors = validate_skill(skill_dir)
        all_errors.extend(errors)

    # Check for duplicate names
    seen = set()
    for name in skill_names:
        if name in seen:
            all_errors.append(f"Duplicate skill directory: {name}")
        seen.add(name)

    # Write report
    report_lines = ["## Skill Validation Report\\n"]

    if all_errors:
        report_lines.append(f"**{len(all_errors)} error(s)** "
                          f"found in {validated_count} skill(s):\\n")
        for error in all_errors:
            report_lines.append(f"- ❌ {error}")
    else:
        report_lines.append(
            f"✅ **All {validated_count} skill(s) passed validation**"
        )

    report = "\\n".join(report_lines) + "\\n"

    Path("validation-report.md").write_text(report, encoding="utf-8")

    print(report)

    if all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
        (repo_path / "scripts" / "validate_skills.py").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_example_skill(self, repo_path: Path) -> None:
        """Write skill/example-skill/SKILL.md and version.txt."""
        skill_md = """\
---
name: example-skill
description: An example skill to demonstrate the registry structure
author: your-name
tags:
  - example
  - getting-started
---

# Example Skill

This is a template skill to show the expected structure. Replace this
content with your actual skill instructions.

## When to Use

Use this skill when you need an example of the skill format.

## Instructions

1. Copy this directory as a starting point for new skills
2. Update the frontmatter (name, description, author, tags)
3. Replace this content with your skill's instructions
4. Create a version.txt with `0.1.0`
5. Register in release-please-config.json
"""
        (repo_path / "skill" / "example-skill" / "SKILL.md").write_text(
            skill_md, encoding="utf-8"
        )

        # version.txt — bootstrapped at 0.1.0 (required by release-please)
        (repo_path / "skill" / "example-skill" / "version.txt").write_text(
            "0.1.0\n", encoding="utf-8"
        )

        # .listing.json for frontend file discovery
        self._write_scaffold_skill_listing(repo_path / "skill" / "example-skill")

    def _write_scaffold_skill_listing(self, skill_path: Path) -> None:
        """Write .listing.json for a skill directory.

        Args:
            skill_path: Path to the skill directory (e.g., skill/example-skill/)
        """
        listing: dict[str, Any] = {
            "files": [],
            "directories": [],
            "directory_files": {},
        }

        skip_names = {".listing.json", ".gitkeep", ".DS_Store", "__pycache__"}

        for item in skill_path.iterdir():
            if item.name in skip_names:
                continue

            if item.is_file():
                listing["files"].append(item.name)
            elif item.is_dir():
                listing["directories"].append(item.name)
                dir_files = []
                for subitem in item.iterdir():
                    if subitem.name not in skip_names and subitem.is_file():
                        dir_files.append(subitem.name)
                if dir_files:
                    listing["directory_files"][item.name] = sorted(dir_files)

        listing["files"] = sorted(listing["files"])
        listing["directories"] = sorted(listing["directories"])

        (skill_path / ".listing.json").write_text(
            json.dumps(listing, indent=2) + "\n", encoding="utf-8"
        )

    def _write_scaffold_skill_release(self, repo_path: Path) -> None:
        """Write skill/skill-release/ — bundled operational guide for releases.

        Provides workflows for creating, updating, and releasing skills
        within the registry, including release-please conventions,
        conventional commit guidance, and troubleshooting procedures.
        """
        skill_md = """\
---
name: skill-release
description: >-
  Guide for creating, versioning, and releasing skills in a ContextHarness
  skills registry repository. Use when adding new skills to a registry repo,
  releasing skill versions, updating existing skills with proper conventional
  commit messages, troubleshooting release-please automation, understanding
  the release lifecycle, or managing the skill lifecycle in an init-repo
  scaffolded repository.
---

# Skill Release

Operational guide for authoring, versioning, and releasing skills within a
ContextHarness skills registry repository (created via
`context-harness skill init-repo`).

## Golden Rules

These three rules prevent the most common issues:

1. **Never edit `version.txt` manually** — release-please manages it
2. **Never edit `skills.json` manually** — CI rebuilds it after every release
3. **Never add `version` to SKILL.md frontmatter** — the version lives only
   in `version.txt`

## How Versioning Works

This registry uses **release-please** with the `simple` release type.
Version bumps are fully automated based on conventional commit messages.
The system uses **path-based detection** to attribute commits to skills
based on which files they touch.

**Common misconception**: Commit scopes like `feat(my-skill): ...` are
cosmetic only. release-please determines which skill a commit belongs to
by checking which files under `skill/<name>/` were modified, NOT by
parsing the commit scope.

## Workflow 1: Create a New Skill

### Step 1 — Create the directory and files

```bash
mkdir -p skill/<skill-name>
```

### Step 2 — Create SKILL.md with frontmatter

```markdown
---
name: <skill-name>
description: Brief description of what this skill does
author: your-name
tags:
  - category
---

# Skill Title

Your skill content here...
```

**Requirements**:
- `name` must match the directory name exactly
- `description` is required and should explain both what the skill does
  AND when to use it
- Do NOT include a `version` field

### Step 3 — Bootstrap version.txt

```bash
echo "0.1.0" > skill/<skill-name>/version.txt
```

### Step 4 — Register with release-please

Add to `release-please-config.json` under `"packages"`:

```json
"skill/<skill-name>": {
  "release-type": "simple",
  "component": "<skill-name>"
}
```

Add to `.release-please-manifest.json`:

```json
"skill/<skill-name>": "0.1.0"
```

### Step 5 — Commit with feat: prefix

```bash
git add skill/<skill-name>/ release-please-config.json \\
  .release-please-manifest.json
git commit -m "feat: add <skill-name>"
git push origin main
```

The `feat:` prefix is critical — it is a releasable commit type that
triggers release-please to create the initial release PR.

## Workflow 2: Update an Existing Skill

1. Edit the skill's `SKILL.md` (or any file in `skill/<skill-name>/`)
2. Commit with the appropriate conventional commit prefix:
   - `fix: correct typo in examples` — patch bump (0.1.0 → 0.1.1)
   - `feat: add error handling section` — minor bump (0.1.0 → 0.2.0)
   - `feat!: restructure skill format` — major bump (0.1.0 → 1.0.0)
3. Push and merge to main
4. release-please automatically creates a release PR

## Workflow 3: Release Lifecycle

After a releasable commit merges to main:

```
1. release.yml triggers → release-please-action runs
2. Detects changed paths under skill/<name>/
3. Creates release PR: "chore(main): release <name> X.Y.Z"
   - Bumps skill/<name>/version.txt
   - Generates/updates skill/<name>/CHANGELOG.md
4. Maintainer merges the release PR
5. release-please creates:
   - Git tag: <name>@vX.Y.Z
   - GitHub Release with changelog
6. sync-registry.yml triggers on version.txt change
7. Rebuilds skills.json automatically
8. Users detect update: context-harness skill outdated
```

## Commit Convention Quick Reference

| Prefix | Version Bump | Use When |
|--------|-------------|----------|
| `fix:` | Patch (0.0.x) | Correcting errors, typos, broken examples |
| `feat:` | Minor (0.x.0) | Adding new content, sections, examples |
| `feat!:` | Major (x.0.0) | Restructuring, breaking format changes |
| `docs:` | No release | README, CONTRIBUTING changes (not skill content) |
| `chore:` | No release | Formatting, cleanup, CI config |

**For skill content changes, always use `feat:` or `fix:`**. Using
`docs:` or `chore:` for SKILL.md edits will NOT trigger a release.

### Version Override

Force a specific version with the `Release-As` trailer:

```bash
git commit --allow-empty -m "chore: release 2.0.0" -m "Release-As: 2.0.0"
```

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Using `docs:` for skill edits | No release PR created | Use `feat:` or `fix:` |
| Adding `version` to frontmatter | Validation failure | Remove it |
| Forgetting release-please registration | No release PR | Add to both JSON files |
| Editing `version.txt` manually | Version conflict | Revert; let CI manage |
| Editing `skills.json` manually | Overwritten on release | Let CI rebuild it |

## Troubleshooting

For detailed troubleshooting with diagnostic commands, see
[references/troubleshooting.md](references/troubleshooting.md).

Quick checks:
- **No release PR appearing?** Verify commit used `feat:` or `fix:`,
  check Actions tab for release.yml runs
- **skills.json not updated?** Only updates after a release PR merge;
  check sync-registry.yml runs
- **Validation failing?** Run `python scripts/validate_skills.py` locally
"""
        (repo_path / "skill" / "skill-release" / "SKILL.md").write_text(
            skill_md, encoding="utf-8"
        )

        troubleshooting_md = """\
# Troubleshooting Guide

Diagnostic procedures for common issues in the skills registry release
pipeline.

## Decision Tree

### Release PR not created after merge

```
1. Was the commit prefix releasable? (feat: or fix:)
   NO  → Recommit with feat: or fix: prefix
   YES → Continue

2. Did the commit touch files under skill/<name>/?
   NO  → release-please uses path-based detection, not commit scope
   YES → Continue

3. Is the skill registered in release-please-config.json?
   NO  → Add package entry and re-push
   YES → Continue

4. Did the release.yml workflow run?
   Check: gh run list --workflow=release.yml --limit=5
   NO  → Check workflow trigger (must be push to main)
   YES → Check the run logs for errors
```

### skills.json not updated after release

```
1. Was the release PR actually merged (not just the feature PR)?
   NO  → Merge the release PR first
   YES → Continue

2. Did sync-registry.yml trigger?
   Check: gh run list --workflow=sync-registry.yml --limit=5
   NO  → sync-registry triggers on skill/*/version.txt changes;
         the release PR must bump version.txt
   YES → Check logs for errors

3. Manual rebuild:
   python scripts/sync-registry.py
   git add skills.json
   git commit -m "chore: sync skills.json [skip ci]"
   git push
```

### Validation failing on PR

```
1. Check the validation report:
   python scripts/validate_skills.py

2. Common failures:
   - "missing SKILL.md"                 → Create the file
   - "name does not match directory"    → Align frontmatter name with dir
   - "remove 'version' from frontmatter" → Delete version field
   - "missing version.txt"             → echo "0.1.0" > skill/<name>/version.txt
   - "invalid frontmatter"             → Check YAML syntax in header
```

### Release created wrong version

```
1. Check which commits release-please included:
   gh pr view <release-pr-number> --json body

2. If version is wrong, use Release-As override:
   git commit --allow-empty -m "chore: release X.Y.Z" \\
     -m "Release-As: X.Y.Z"

3. If a release was already tagged incorrectly:
   - Delete the GitHub Release via UI or API
   - Delete the git tag: git push --delete origin <tag>
   - Update .release-please-manifest.json to correct version
   - Push a new releasable commit to trigger fresh release PR
```

## Diagnostic Commands

```bash
# Recent release workflow runs
gh run list --workflow=release.yml --limit=5

# Pending release PRs
gh pr list --label "autorelease: pending"

# Recent sync workflow runs
gh run list --workflow=sync-registry.yml --limit=5

# Commits touching a specific skill
git log --oneline -- skill/<skill-name>/

# Validate locally before pushing
python scripts/validate_skills.py
```

## Known release-please Quirks

1. **`releases_created` output is unreliable in v4** — Use per-path
   outputs: `steps.release.outputs['skill/name--release_created']`

2. **Do not use `@` in skill names** — Known bug (#2661) causes tag
   parsing failures

3. **First release for new skill** — The initial `feat: add <name>`
   commit triggers the first release PR, bumping from the bootstrapped
   0.1.0 to the appropriate next version.

4. **`python-frontmatter` pip name vs import** — Install with
   `pip install python-frontmatter`, but import as `import frontmatter`

5. **`[skip ci]` in sync-registry commits** — The sync-registry workflow
   uses `[skip ci]` to prevent infinite workflow loops when it commits
   the updated skills.json
"""
        (
            repo_path / "skill" / "skill-release" / "references" / "troubleshooting.md"
        ).write_text(troubleshooting_md, encoding="utf-8")

        # version.txt — bootstrapped at 0.1.0 (required by release-please)
        (repo_path / "skill" / "skill-release" / "version.txt").write_text(
            "0.1.0\n", encoding="utf-8"
        )

        # .listing.json for frontend file discovery
        self._write_scaffold_skill_listing(repo_path / "skill" / "skill-release")

    def _compare_versions(
        self,
        skill_name: str,
        local_version: str,
        remote_version: str,
        min_ch_version: Optional[str],
        current_ch_version: str,
    ) -> VersionComparison:
        """Compare skill versions and check compatibility.

        Args:
            skill_name: Name of the skill
            local_version: Currently installed version
            remote_version: Latest available version
            min_ch_version: Minimum required ContextHarness version
            current_ch_version: Current ContextHarness version

        Returns:
            VersionComparison with appropriate status
        """
        try:
            local = Version(local_version)
            remote = Version(remote_version)

            # Check ContextHarness compatibility first
            if min_ch_version:
                try:
                    current_ch = Version(current_ch_version)
                    min_required = Version(min_ch_version)

                    if current_ch < min_required:
                        return VersionComparison(
                            skill_name=skill_name,
                            local_version=local_version,
                            remote_version=remote_version,
                            status=VersionStatus.INCOMPATIBLE,
                            context_harness_min=min_ch_version,
                            current_context_harness=current_ch_version,
                        )
                except InvalidVersion:
                    # Propagate invalid version errors to the outer handler so
                    # that the overall status is reported as UNKNOWN.
                    raise

            # Compare skill versions
            if remote > local:
                status = VersionStatus.UPGRADE_AVAILABLE
            else:
                status = VersionStatus.UP_TO_DATE

            return VersionComparison(
                skill_name=skill_name,
                local_version=local_version,
                remote_version=remote_version,
                status=status,
                context_harness_min=min_ch_version,
                current_context_harness=current_ch_version,
            )

        except InvalidVersion:
            # If version parsing fails, status is unknown
            return VersionComparison(
                skill_name=skill_name,
                local_version=local_version,
                remote_version=remote_version,
                status=VersionStatus.UNKNOWN,
                context_harness_min=min_ch_version,
                current_context_harness=current_ch_version,
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
        tool_target: Optional[ToolTarget] = None,
    ) -> Result[str]:
        """Extract a local skill and create a PR to the central repository.

        Searches for the skill in both .opencode/skill/ and .claude/skills/
        directories based on tool_target or auto-detection.

        Args:
            skill_name: Name of the skill to extract
            source_path: Source directory containing skill directories
            tool_target: Optional target tool (Claude Code or OpenCode)

        Returns:
            Result containing PR URL if successful
        """
        # Determine skill directories to search
        detector = ToolDetector(source_path)
        if tool_target:
            skills_dirs = detector.get_skills_dirs(tool_target.tool_type)
        else:
            # Auto-detect: search both tool types
            skills_dirs = detector.get_skills_dirs("both")

        # Find the skill
        skill_source: Optional[Path] = None
        for skills_dir in skills_dirs:
            candidate = skills_dir / skill_name
            if candidate.exists():
                skill_source = candidate
                break

        if skill_source is None:
            # Build helpful error message with searched locations
            searched = (
                ", ".join(str(d) for d in skills_dirs)
                if skills_dirs
                else "no skill directories found"
            )
            return Failure(
                error=f"Skill '{skill_name}' not found. Searched: {searched}",
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

    # -- HTTP Registry Scaffold Methods --------------------------------------

    def _write_scaffold_marketplace_json(self, repo_path: Path, repo_name: str) -> None:
        """Write marketplace.json — standardized manifest for plugin discovery.

        This format provides compatibility with future Claude Code plugin
        marketplaces and other AI coding assistant ecosystems.

        The marketplace.json is regenerated by sync-registry.py alongside
        skills.json whenever skills are updated.
        """
        # Determine registry URL (GitHub Pages or custom domain)
        # For GitHub repos, the default is Pages at user.github.io/repo-name
        parts = repo_name.split("/")
        if len(parts) == 2:
            owner, name = parts
            registry_url = f"https://{owner}.github.io/{name}"
        else:
            registry_url = f"https://github.com/{repo_name}"

        marketplace = {
            "$schema": "https://context-harness.dev/schemas/marketplace.json",
            "schema_version": "1.1",
            "registry_version": CH_VERSION,
            "name": repo_name,
            "display_name": f"{repo_name.split('/')[-1]} Skills Registry",
            "description": "ContextHarness skills registry with versioned skills",
            "registry_type": "context-harness",
            "registry_url": registry_url,
            "skills_endpoint": "/skills.json",
            "skill_base_path": "/skill",
            "website": f"https://github.com/{repo_name}",
            "maintainer": {
                "name": "Registry Owner",
                "url": f"https://github.com/{parts[0] if len(parts) == 2 else repo_name}",
            },
            "compatibility": {
                "context_harness": ">=0.5.0",
                "claude_code": ">=1.0.0",
            },
            "skills": [],
        }
        (repo_path / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

    def _write_scaffold_http_registry(self, repo_path: Path, repo_name: str) -> None:
        """Write HTTP registry hosting files for Docker/nginx deployment.

        Creates a complete setup for hosting the skills registry via HTTP:
        - Dockerfile for containerized nginx serving
        - docker-compose.yml for easy deployment
        - nginx.conf with CORS headers for cross-origin access
        - Web frontend (index.html, skill.html) for browsing skills
        """
        # Create directories
        (repo_path / "registry" / "web").mkdir(parents=True, exist_ok=True)

        # --- Dockerfile ---
        self._write_scaffold_dockerfile(repo_path)

        # --- docker-compose.yml ---
        self._write_scaffold_docker_compose(repo_path, repo_name)

        # --- nginx.conf ---
        self._write_scaffold_nginx_conf(repo_path)

        # --- llms.txt (AI agent instructions) ---
        self._write_scaffold_llms_txt(repo_path)

        # --- Web frontend ---
        self._write_scaffold_index_html(repo_path, repo_name)
        self._write_scaffold_skill_html(repo_path, repo_name)

    def _write_scaffold_dockerfile(self, repo_path: Path) -> None:
        """Write Dockerfile for nginx-based registry hosting."""
        content = """\
# ContextHarness Skills Registry - HTTP Server
# Serves skills.json and skill files via nginx with CORS support

FROM nginx:alpine

# Copy nginx configuration
COPY registry/nginx.conf /etc/nginx/nginx.conf

# Copy registry files
COPY skills.json marketplace.json llms.txt /usr/share/nginx/html/
COPY skill /usr/share/nginx/html/skill

# Copy web frontend
COPY registry/web /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost/skills.json || exit 1
"""
        (repo_path / "Dockerfile").write_text(content, encoding="utf-8")

    def _write_scaffold_docker_compose(self, repo_path: Path, repo_name: str) -> None:
        """Write docker-compose.yml for easy deployment."""
        content = f"""\
# ContextHarness Skills Registry
# Quick start: docker-compose up -d
# Access at: http://localhost:8080

services:
  registry:
    build: .
    ports:
      - "8080:80"
    volumes:
      # Mount skill directories for development
      - ./skill:/usr/share/nginx/html/skill:ro
      - ./skills.json:/usr/share/nginx/html/skills.json:ro
      - ./marketplace.json:/usr/share/nginx/html/marketplace.json:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost/skills.json"]
      interval: 30s
      timeout: 3s
      retries: 3

  # Optional: GitHub Pages sync (for production)
  # pages-sync:
  #   image: alpine:latest
  #   command: sh -c "while true; do sleep 3600; done"
"""
        (repo_path / "docker-compose.yml").write_text(content, encoding="utf-8")

    def _write_scaffold_nginx_conf(self, repo_path: Path) -> None:
        """Write nginx.conf with CORS headers for cross-origin access."""
        content = """\
# ContextHarness Skills Registry nginx configuration
# Optimized for serving JSON and markdown with CORS support

worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip compression
    gzip on;
    gzip_types application/json text/markdown text/plain text/css application/javascript;
    gzip_min_length 256;

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # CORS headers for all requests
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Origin, Content-Type, Accept" always;

        # Cache static assets
        location ~* \\.(json|md|txt)$ {
            expires 5m;
            add_header Cache-Control "public, must-revalidate";
            add_header Access-Control-Allow-Origin * always;
        }

        # Serve skills.json
        location = /skills.json {
            add_header Content-Type application/json;
            add_header Access-Control-Allow-Origin * always;
        }

        # Serve marketplace.json
        location = /marketplace.json {
            add_header Content-Type application/json;
            add_header Access-Control-Allow-Origin * always;
        }

        # Serve llms.txt (AI agent instructions)
        location = /llms.txt {
            add_header Content-Type text/plain;
            add_header Access-Control-Allow-Origin * always;
        }

        # Serve skill files
        location /skill/ {
            alias /usr/share/nginx/html/skill/;
            add_header Access-Control-Allow-Origin * always;
        }

        # Markdown files with correct content-type (sibling location, not nested)
        location ~* ^/skill/.*\\.md$ {
            root /usr/share/nginx/html;
            default_type text/markdown;
            add_header Access-Control-Allow-Origin * always;
        }

        # Web frontend
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Health check endpoint
        location /health {
            return 200 'OK';
            add_header Content-Type text/plain;
        }
    }
}
"""
        (repo_path / "registry" / "nginx.conf").write_text(content, encoding="utf-8")

    def _write_scaffold_llms_txt(self, repo_path: Path) -> None:
        """Write llms.txt - AI agent instructions file.

        This is an emerging standard for providing LLM-specific instructions.
        AI agents are trained to look for this file at the root of websites.
        """
        content = """\
# ContextHarness Skills Registry

> AI Agent Instructions: This registry provides skills that extend AI coding assistants with specialized capabilities.

## Installation Protocol

**ALWAYS use the CLI to install skills:**
```
ch skill install <skill-name>
```

The CLI handles all installation details automatically.

## Rules

- ONLY use `ch skill install` - never manually download or copy files
- The CLI installs to both `.opencode/skill/` AND `.claude/skills/` automatically
- User does NOT have git access to this registry

## Available Skills

See `/skills.json` for the complete list of available skills with descriptions.
"""
        (repo_path / "llms.txt").write_text(content, encoding="utf-8")

    def _write_scaffold_index_html(self, repo_path: Path, repo_name: str) -> None:
        """Write index.html - static frontend for browsing skills.

        A clean shadcn-inspired UI using Tailwind CSS with the project theme.
        Includes sections for AI agent instructions and skill building.
        """
        content = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skills Registry</title>
    <!-- AI Agent Instructions: Read /llms.txt for installation protocol -->
    <meta name="llm-instructions" content="/llms.txt">
    <meta name="ai-agent-protocol" content="read-instructions-first">
    <meta name="description" content="Skills registry for AI coding assistants. Read /llms.txt for installation instructions.">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Noto+Sans+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --background: oklch(0.1450 0 0);
            --foreground: oklch(0.9850 0 0);
            --card: oklch(0.2050 0 0);
            --card-foreground: oklch(0.9850 0 0);
            --primary: oklch(0.9220 0 0);
            --primary-foreground: oklch(0.2050 0 0);
            --secondary: oklch(0.2690 0 0);
            --secondary-foreground: oklch(0.9850 0 0);
            --muted: oklch(0.2690 0 0);
            --muted-foreground: oklch(0.7080 0 0);
            --accent: oklch(0.3710 0 0);
            --accent-foreground: oklch(0.9850 0 0);
            --border: oklch(0.2750 0 0);
            --input: oklch(0.3250 0 0);
            --ring: oklch(0.5560 0 0);
            --radius: 0.625rem;
        }
        * { border-color: var(--border); }
        body { font-family: 'Noto Sans Mono', ui-sans-serif, system-ui, sans-serif; background: var(--background); color: var(--foreground); }
        .font-mono { font-family: 'Fira Code', ui-monospace, monospace; }
        .collapsible-content { max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; }
        .collapsible-content.open { max-height: 2000px; }
        .chevron { transition: transform 0.2s; }
        .chevron.open { transform: rotate(180deg); }
    </style>
</head>
<body class="min-h-screen">
    <div class="max-w-5xl mx-auto px-6 py-12">
        <!-- Header -->
        <header class="mb-8">
            <h1 class="text-3xl font-semibold tracking-tight mb-2">Skills Registry</h1>
            <p class="text-[var(--muted-foreground)]">Extend your AI assistant with specialized capabilities</p>
            <p class="text-xs text-[var(--muted-foreground)] mt-1">🤖 AI agents: read <a href="/llms.txt" class="underline">llms.txt</a> for installation instructions</p>
        </header>

        <!-- Build a Skill Section (hidden for now) -->
        <section id="build-skill" class="mb-8 p-4 bg-[var(--card)] border rounded-[var(--radius)]" hidden>
            <div id="build-toggle" class="flex items-center justify-between cursor-pointer">
                <div class="flex items-center gap-2">
                    <span class="text-lg">🔧</span>
                    <h2 class="text-sm font-medium">Build a Skill</h2>
                </div>
                <svg id="build-chevron" class="w-4 h-4 chevron text-[var(--muted-foreground)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
            </div>
            <div id="build-content" class="collapsible-content">
                <div class="mt-4 pt-4 border-t text-sm space-y-4">
                    <p class="text-[var(--muted-foreground)]">
                        Create and contribute skills to extend ContextHarness capabilities for your team.
                    </p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="p-3 bg-[var(--background)] rounded-[var(--radius)]">
                            <h3 class="text-xs font-medium mb-2">📁 Skill Structure</h3>
                            <pre class="text-xs text-[var(--muted-foreground)] overflow-x-auto">skill/my-skill/
├── SKILL.md       # Instructions
├── version.txt    # Semantic version
└── references/    # Optional docs</pre>
                        </div>
                        <div class="p-3 bg-[var(--background)] rounded-[var(--radius)]">
                            <h3 class="text-xs font-medium mb-2">📝 SKILL.md Format</h3>
                            <pre class="text-xs text-[var(--muted-foreground)] overflow-x-auto">---
name: my-skill
description: What it does
tags: [category]
---

# Instructions here...</pre>
                        </div>
                    </div>
                    <div class="space-y-2">
                        <p class="text-xs text-[var(--muted-foreground)]"><strong>Quick Start:</strong></p>
                        <ol class="list-decimal list-inside text-xs text-[var(--muted-foreground)] space-y-1">
                            <li>Create a directory in <code class="bg-[var(--muted)] px-1 rounded">skill/my-skill/</code></li>
                            <li>Add <code class="bg-[var(--muted)] px-1 rounded">SKILL.md</code> with YAML frontmatter</li>
                            <li>Add <code class="bg-[var(--muted)] px-1 rounded">version.txt</code> with <code class="bg-[var(--muted)] px-1 rounded">0.1.0</code></li>
                            <li>Commit with <code class="bg-[var(--muted)] px-1 rounded">feat: add my-skill</code></li>
                        </ol>
                    </div>
                    <div class="flex gap-2">
                        <a href="skill/skill-release/SKILL.md" class="px-3 py-1.5 text-xs bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity">View Example Skill</a>
                        <a href="https://github.com/co-labs-co/context-harness" class="px-3 py-1.5 text-xs bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded hover:opacity-90 transition-opacity">Full Documentation</a>
                    </div>
                </div>
            </div>
        </section>

        <!-- Search -->
        <div class="mb-8">
            <input
                type="text"
                id="search"
                placeholder="Search skills..."
                class="w-full px-4 py-2.5 bg-[var(--card)] border rounded-[var(--radius)] text-sm outline-none focus:ring-2 focus:ring-[var(--ring)] transition-shadow"
            >
        </div>

        <!-- Skills List -->
        <div id="skills-list" class="space-y-3">
            <div class="text-center py-12 text-[var(--muted-foreground)]">
                Loading...
            </div>
        </div>

        <!-- Footer -->
        <footer class="mt-16 pt-8 border-t text-center text-sm text-[var(--muted-foreground)]">
            <a href="https://github.com/co-labs-co/context-harness" class="hover:text-[var(--foreground)] transition-colors">ContextHarness</a>
        </footer>
    </div>

    <!-- Toast -->
    <div id="toast" class="fixed bottom-6 right-6 px-4 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-[var(--radius)] text-sm font-medium opacity-0 translate-y-2 transition-all duration-200 pointer-events-none">
        Copied to clipboard
    </div>

    <script>
        let skills = [];

        function toggleSection(id) {
            var content = document.getElementById(id);
            var chevron = document.getElementById(id.replace('-content', '-chevron'));
            content.classList.toggle('open');
            chevron.classList.toggle('open');
        }

        async function loadSkills() {
            try {
                const res = await fetch('./skills.json');
                const data = await res.json();
                skills = data.skills || [];
                render();
            } catch (e) {
                document.getElementById('skills-list').innerHTML = '<div class="text-center py-12 text-[var(--muted-foreground)]">Failed to load skills</div>';
            }
        }

        function render(list) {
            if (!list) list = skills;
            const container = document.getElementById('skills-list');
            container.innerHTML = '';

            if (!list.length) {
                container.innerHTML = '<div class="text-center py-12 text-[var(--muted-foreground)]">No skills found</div>';
                return;
            }

            list.forEach(function(s) {
                var a = document.createElement('a');
                a.href = 'skill.html?name=' + encodeURIComponent(s.name);
                a.className = 'block group p-4 bg-[var(--card)] border rounded-[var(--radius)] hover:border-[var(--ring)] transition-colors';

                var outerDiv = document.createElement('div');
                outerDiv.className = 'flex items-start justify-between gap-4';

                var innerDiv = document.createElement('div');
                innerDiv.className = 'flex-1 min-w-0';

                var titleRow = document.createElement('div');
                titleRow.className = 'flex items-center gap-2 mb-1';

                var h3 = document.createElement('h3');
                h3.className = 'font-medium';
                h3.textContent = s.name;
                titleRow.appendChild(h3);

                var version = document.createElement('span');
                version.className = 'font-mono text-xs px-1.5 py-0.5 bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded';
                version.textContent = 'v' + (s.version || '0.0.0');
                titleRow.appendChild(version);
                innerDiv.appendChild(titleRow);

                var desc = document.createElement('p');
                desc.className = 'text-sm text-[var(--muted-foreground)] line-clamp-2 mb-2';
                desc.textContent = s.description || 'No description';
                innerDiv.appendChild(desc);

                if (s.tags && s.tags.length) {
                    var tagsDiv = document.createElement('div');
                    tagsDiv.className = 'flex flex-wrap gap-1.5';
                    s.tags.slice(0, 3).forEach(function(t) {
                        var tag = document.createElement('span');
                        tag.className = 'text-xs px-2 py-0.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-full';
                        tag.textContent = t;
                        tagsDiv.appendChild(tag);
                    });
                    innerDiv.appendChild(tagsDiv);
                }
                outerDiv.appendChild(innerDiv);

                var btn = document.createElement('button');
                btn.className = 'shrink-0 px-3 py-1.5 text-xs font-medium bg-[var(--primary)] text-[var(--primary-foreground)] rounded-[var(--radius)] hover:opacity-90 transition-opacity';
                btn.textContent = 'Copy';
                btn.dataset.skillName = s.name;
                btn.addEventListener('click', function(evt) {
                    evt.preventDefault();
                    evt.stopPropagation();
                    copyInstall(this.dataset.skillName);
                });
                outerDiv.appendChild(btn);

                a.appendChild(outerDiv);
                container.appendChild(a);
            });
        }

        function copyInstall(name) {
            var cmd = 'ch skill install ' + name;
            navigator.clipboard.writeText(cmd).then(function() {
                var toast = document.getElementById('toast');
                toast.classList.remove('opacity-0', 'translate-y-2');
                setTimeout(function() { toast.classList.add('opacity-0', 'translate-y-2'); }, 1500);
            }).catch(function() {
                var ta = document.createElement('textarea');
                ta.value = cmd;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            });
        }

        function esc(str) {
            var el = document.createElement('div');
            el.textContent = str;
            return el.innerHTML;
        }

        var debounceTimer;
        document.getElementById('search').addEventListener('input', function(e) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                var q = e.target.value.toLowerCase();
                if (!q) return render();
                render(skills.filter(function(s) {
                    return (s.name && s.name.toLowerCase().includes(q)) ||
                           (s.description && s.description.toLowerCase().includes(q)) ||
                           (s.tags && s.tags.some(function(t) { return t.toLowerCase().includes(q); }));
                }));
            }, 150);
        });

        // Setup event listeners for build toggle
        var buildToggle = document.getElementById('build-toggle');
        if (buildToggle) {
            buildToggle.addEventListener('click', function() { toggleSection('build-content'); });
        }

        loadSkills();
    </script>
</body>
</html>
"""
        (repo_path / "registry" / "web" / "index.html").write_text(
            content, encoding="utf-8"
        )

    def _write_scaffold_skill_html(self, repo_path: Path, repo_name: str) -> None:
        """Write skill.html - individual skill detail page with file explorer."""
        content = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skill Details</title>
    <!-- AI Agent Instructions: Read /llms.txt for installation protocol -->
    <meta name="llm-instructions" content="/llms.txt">
    <meta name="description" content="Skill details - Read /llms.txt for installation instructions.">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Noto+Sans+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --background: oklch(0.1450 0 0);
            --foreground: oklch(0.9850 0 0);
            --card: oklch(0.2050 0 0);
            --card-foreground: oklch(0.9850 0 0);
            --primary: oklch(0.9220 0 0);
            --primary-foreground: oklch(0.2050 0 0);
            --secondary: oklch(0.2690 0 0);
            --secondary-foreground: oklch(0.9850 0 0);
            --muted: oklch(0.2690 0 0);
            --muted-foreground: oklch(0.7080 0 0);
            --accent: oklch(0.3710 0 0);
            --accent-foreground: oklch(0.9850 0 0);
            --border: oklch(0.2750 0 0);
            --input: oklch(0.3250 0 0);
            --ring: oklch(0.5560 0 0);
            --radius: 0.625rem;
        }
        * { border-color: var(--border); }
        body { font-family: 'Noto Sans Mono', ui-sans-serif, system-ui, sans-serif; background: var(--background); color: var(--foreground); }
        .font-mono { font-family: 'Fira Code', ui-monospace, monospace; }
        .file-tree { user-select: none; }
        .file-item { cursor: pointer; padding: 0.375rem 0.5rem; border-radius: var(--radius); transition: background 0.15s; }
        .file-item:hover { background: var(--muted); }
        .file-item.active { background: var(--accent); color: var(--accent-foreground); }
        .file-content { white-space: pre-wrap; word-break: break-word; font-family: 'Fira Code', ui-monospace, monospace; font-size: 0.8125rem; line-height: 1.6; }
        .markdown-content h1 { font-size: 1.5rem; font-weight: 600; margin: 1.5rem 0 1rem; }
        .markdown-content h2 { font-size: 1.25rem; font-weight: 600; margin: 1.25rem 0 0.75rem; }
        .markdown-content h3 { font-size: 1.125rem; font-weight: 600; margin: 1rem 0 0.5rem; }
        .markdown-content p { margin: 0.75rem 0; }
        .markdown-content ul, .markdown-content ol { margin: 0.75rem 0; padding-left: 1.5rem; }
        .markdown-content li { margin: 0.25rem 0; }
        .markdown-content code { background: var(--muted); padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.875em; }
        .markdown-content pre { background: var(--background); padding: 1rem; border-radius: var(--radius); overflow-x: auto; margin: 1rem 0; }
        .markdown-content pre code { background: none; padding: 0; }
        .markdown-content blockquote { border-left: 2px solid var(--border); padding-left: 1rem; margin: 1rem 0; color: var(--muted-foreground); }
        .markdown-content a { color: var(--ring); text-decoration: underline; }
        .markdown-content table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        .markdown-content th, .markdown-content td { border: 1px solid var(--border); padding: 0.5rem; text-align: left; }
        .markdown-content th { background: var(--muted); }
    </style>
</head>
<body class="min-h-screen">
    <div class="max-w-6xl mx-auto px-6 py-8">
        <header class="mb-8">
            <a href="index.html" class="inline-flex items-center gap-2 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                Back to Skills
            </a>
            <div id="skill-header" class="flex items-start justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-semibold" id="skill-name">Loading...</h1>
                    <p class="text-[var(--muted-foreground)] mt-1" id="skill-description"></p>
                </div>
                <div id="skill-meta" class="text-right shrink-0"></div>
            </div>
        </header>
        <div id="error-state" class="hidden text-center py-16">
            <p class="text-[var(--muted-foreground)] mb-4">Skill not found</p>
            <a href="index.html" class="text-[var(--ring)] hover:underline">Return to skills list</a>
        </div>
        <div id="skill-content" class="hidden">
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div class="lg:col-span-1">
                    <div class="bg-[var(--card)] border rounded-[var(--radius)] p-4 sticky top-4">
                        <h2 class="text-sm font-medium mb-3 text-[var(--muted-foreground)]">Files</h2>
                        <div id="file-tree" class="file-tree text-sm space-y-0.5">
                            <div class="text-[var(--muted-foreground)] py-2">Loading...</div>
                        </div>
                    </div>
                </div>
                <div class="lg:col-span-3">
                    <div class="bg-[var(--card)] border rounded-[var(--radius)]">
                        <div class="flex items-center justify-between px-4 py-3 border-b">
                            <div class="flex items-center gap-2">
                                <span id="file-icon" class="text-[var(--muted-foreground)]">📄</span>
                                <span id="file-path" class="font-mono text-sm">Select a file</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <button id="view-raw-btn" class="px-2.5 py-1 text-xs bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded hover:opacity-90 transition-opacity">Raw</button>
                                <button id="copy-btn" class="px-2.5 py-1 text-xs bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity">Copy</button>
                            </div>
                        </div>
                        <div id="file-content-wrapper" class="p-4 min-h-[400px] max-h-[70vh] overflow-auto">
                            <div id="file-content" class="markdown-content">Select a file to view its contents</div>
                        </div>
                    </div>
                    <div class="mt-6 p-4 bg-[var(--card)] border rounded-[var(--radius)]">
                        <h3 class="text-sm font-medium mb-2 text-[var(--muted-foreground)]">Install Command</h3>
                        <div class="flex items-center gap-2">
                            <code id="install-cmd" class="flex-1 px-3 py-2 bg-[var(--background)] rounded font-mono text-sm"></code>
                            <button id="install-copy-btn" class="px-3 py-2 text-xs font-medium bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity">Copy</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div id="toast" class="fixed bottom-6 right-6 px-4 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-[var(--radius)] text-sm font-medium opacity-0 translate-y-2 transition-all duration-200 pointer-events-none">Copied to clipboard</div>
    <script>
        var skillName = '';
        var skillMeta = null;
        var fileCache = {};
        var currentFile = null;
        var isRawView = false;
        var params = new URLSearchParams(window.location.search);
        skillName = params.get('name');
        if (!skillName) { document.getElementById('error-state').classList.remove('hidden'); } else { loadSkill(); }
        async function loadSkill() {
            try {
                var res = await fetch('./skills.json');
                if (!res.ok) throw new Error('Failed to fetch skills.json');
                var data = await res.json();
                skillMeta = data.skills && data.skills.find(function(s) { return s.name === skillName; });
                if (!skillMeta) { document.getElementById('error-state').classList.remove('hidden'); return; }
                renderHeader();
                document.getElementById('skill-content').classList.remove('hidden');
                document.getElementById('install-cmd').textContent = 'ch skill install ' + skillName;
                await discoverFiles();
            } catch (e) { console.error('Error loading skill:', e); document.getElementById('error-state').classList.remove('hidden'); }
        }
        function renderHeader() {
            document.getElementById('skill-name').textContent = skillMeta.name;
            document.getElementById('skill-description').textContent = skillMeta.description || 'No description';
            var metaHtml = '<span class="font-mono text-xs px-1.5 py-0.5 bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded">v' + (skillMeta.version || '0.0.0') + '</span>';
            if (skillMeta.author) { metaHtml += '<div class="text-xs text-[var(--muted-foreground)] mt-2">by ' + esc(skillMeta.author) + '</div>'; }
            if (skillMeta.tags && skillMeta.tags.length) { metaHtml += '<div class="flex flex-wrap gap-1 mt-2 justify-end">' + skillMeta.tags.map(function(t) { return '<span class="text-xs px-2 py-0.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-full">' + esc(t) + '</span>'; }).join('') + '</div>'; }
            document.getElementById('skill-meta').innerHTML = metaHtml;
        }
        async function discoverFiles() {
            var basePath = 'skill/' + skillName;
            var files = [];
            var knownFiles = [{ path: 'SKILL.md', icon: '📄', name: 'SKILL.md' }, { path: 'version.txt', icon: '📄', name: 'version.txt' }, { path: 'CHANGELOG.md', icon: '📄', name: 'CHANGELOG.md' }];
            for (var i = 0; i < knownFiles.length; i++) {
                var exists = await checkFileExists(basePath + '/' + knownFiles[i].path);
                if (exists) { files.push(Object.assign({}, knownFiles[i], { type: 'file' })); }
            }
            renderFileTree(files);
            var skillMd = files.find(function(f) { return f.path === 'SKILL.md'; });
            if (skillMd) { selectFile(skillMd); }
        }
        async function checkFileExists(path) {
            try { var res = await fetch(path, { method: 'HEAD' }); return res.ok; }
            catch (e) { return false; }
        }
        function renderFileTree(files) {
            var container = document.getElementById('file-tree');
            if (!files.length) { container.innerHTML = '<div class="text-[var(--muted-foreground)] py-2">No files found</div>'; return; }
            container.innerHTML = '';
            files.forEach(function(f) {
                var div = document.createElement('div');
                div.className = 'file-item flex items-center gap-2';
                div.dataset.path = f.path;
                div.dataset.name = f.name;
                div.dataset.icon = f.icon;
                div.dataset.type = 'file';
                div.innerHTML = '<span>' + f.icon + '</span><span>' + esc(f.name) + '</span>';
                div.addEventListener('click', function(evt) { selectFile(f, evt); });
                container.appendChild(div);
            });
        }
        async function selectFile(file, evt) {
            currentFile = file;
            var items = document.querySelectorAll('.file-item');
            items.forEach(function(el) { el.classList.remove('active'); });
            if (evt && evt.target) { var parent = evt.target.closest('.file-item'); if (parent) parent.classList.add('active'); }
            document.getElementById('file-icon').textContent = file.icon;
            document.getElementById('file-path').textContent = file.path;
            var basePath = 'skill/' + skillName;
            var fullPath = basePath + '/' + file.path;
            try {
                if (!fileCache[fullPath]) { var res = await fetch(fullPath); if (!res.ok) throw new Error('Failed to fetch'); fileCache[fullPath] = await res.text(); }
                var content = fileCache[fullPath];
                renderContent(content, file.path);
            } catch (e) { document.getElementById('file-content').innerHTML = '<div class="text-[var(--muted-foreground)]">Failed to load file</div>'; }
        }
        function renderContent(content, path) {
            var wrapper = document.getElementById('file-content-wrapper');
            var container = document.getElementById('file-content');
            if (isRawView || !path.endsWith('.md')) {
                wrapper.className = 'p-4 min-h-[400px] max-h-[70vh] overflow-auto';
                container.className = 'file-content';
                container.textContent = content;
            } else {
                wrapper.className = 'p-4 min-h-[400px] max-h-[70vh] overflow-auto';
                container.className = 'markdown-content';
                container.innerHTML = renderMarkdown(content);
            }
        }
        function renderMarkdown(text) {
            var html = text;
            html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html = html.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
            html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
            html = html.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, function(match, text, url) {
                var safeUrl = sanitizeUrl(url);
                if (safeUrl === null) return text;
                return '<a href="' + escapeAttr(safeUrl) + '">' + text + '</a>';
            });
            html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
            html = html.replace(/(<li>.*<\\/li>\\n?)+/g, '<ul>$&</ul>');
            html = html.replace(/\\n\\n/g, '</p><p>');
            html = '<p>' + html + '</p>';
            html = html.replace(/<p>\\s*<\\/p>/g, '');
            html = html.replace(/<p>(<h[123]>)/g, '$1');
            html = html.replace(/(<\\/h[123]>)<\\/p>/g, '$1');
            html = html.replace(/<p>(<pre>)/g, '$1');
            html = html.replace(/(<\\/pre>)<\\/p>/g, '$1');
            html = html.replace(/<p>(<ul>)/g, '$1');
            html = html.replace(/(<\\/ul>)<\\/p>/g, '$1');
            return html;
        }
        function sanitizeUrl(url) {
            var trimmed = url.trim();
            var safeProtocols = ['http://', 'https://', 'mailto:', 'tel:', '/'];
            for (var i = 0; i < safeProtocols.length; i++) {
                if (trimmed.toLowerCase().indexOf(safeProtocols[i]) === 0) {
                    return trimmed;
                }
            }
            return null;
        }
        function escapeAttr(str) {
            return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }
        function toggleRawView() {
            isRawView = !isRawView;
            document.getElementById('view-raw-btn').textContent = isRawView ? 'Markdown' : 'Raw';
            if (currentFile) {
                var content = fileCache['skill/' + skillName + '/' + currentFile.path];
                if (content) renderContent(content, currentFile.path);
            }
        }
        function copyFileContent() {
            if (!currentFile) return;
            var content = fileCache['skill/' + skillName + '/' + currentFile.path];
            if (!content) return;
            navigator.clipboard.writeText(content).then(function() { showToast(); }).catch(function() {
                var ta = document.createElement('textarea'); ta.value = content; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); showToast();
            });
        }
        function copyInstall() {
            var cmd = 'ch skill install ' + skillName;
            navigator.clipboard.writeText(cmd).then(function() { showToast(); }).catch(function() {
                var ta = document.createElement('textarea'); ta.value = cmd; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); showToast();
            });
        }
        function showToast() {
            var toast = document.getElementById('toast');
            toast.classList.remove('opacity-0', 'translate-y-2');
            setTimeout(function() { toast.classList.add('opacity-0', 'translate-y-2'); }, 1500);
        }
        function esc(str) {
            if (!str) return '';
            var el = document.createElement('div'); el.textContent = str; return el.innerHTML;
        }
        // Setup event listeners for buttons
        document.getElementById('view-raw-btn').addEventListener('click', toggleRawView);
        document.getElementById('copy-btn').addEventListener('click', copyFileContent);
        document.getElementById('install-copy-btn').addEventListener('click', copyInstall);
    </script>
</body>
</html>
"""
        (repo_path / "registry" / "web" / "skill.html").write_text(
            content, encoding="utf-8"
        )
