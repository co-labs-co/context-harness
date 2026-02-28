"""Skill service for ContextHarness.

Handles skill listing, installation, extraction, and validation.
Business logic extracted from skills.py module.

Supports both OpenCode (.opencode/skill/) and Claude Code (.claude/skills/) tools.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Protocol

import yaml
from packaging.version import InvalidVersion, Version

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


SKILLS_REGISTRY_PATH = "skills.json"
SKILLS_DIR = "skill"
RELEASE_PLEASE_CONFIG = "release-please-config.json"
RELEASE_PLEASE_MANIFEST = ".release-please-manifest.json"
INITIAL_VERSION = "0.1.0"


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

    def enable_workflow_pr_creation(self, repo: str) -> bool:
        """Enable GitHub Actions to create and approve pull requests.

        Sets ``default_workflow_permissions`` to ``write`` and
        ``can_approve_pull_request_reviews`` to ``true`` on the repository.
        This is required for release-please (and other Actions) to open PRs
        using the default ``GITHUB_TOKEN``.

        Args:
            repo: Repository in "owner/name" format

        Returns:
            True if the setting was applied successfully, False otherwise
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

    def enable_workflow_pr_creation(self, repo: str) -> bool:
        """Enable GitHub Actions to create and approve pull requests.

        Uses the GitHub REST API to set ``default_workflow_permissions`` to
        ``write`` and ``can_approve_pull_request_reviews`` to ``true``.
        Without this, release-please cannot open PRs using ``GITHUB_TOKEN``.

        Args:
            repo: Repository in "owner/name" format

        Returns:
            True if the setting was applied, False otherwise
        """
        try:
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"/repos/{repo}/actions/permissions/workflow",
                    "-X",
                    "PUT",
                    "-f",
                    "default_workflow_permissions=write",
                    "-F",
                    "can_approve_pull_request_reviews=true",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


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

                    # Prefer version.txt (release-please) over frontmatter version
                    version = metadata.version
                    version_txt = skill_dir / "version.txt"
                    if version_txt.exists():
                        try:
                            version = version_txt.read_text(encoding="utf-8").strip()
                        except Exception:
                            pass  # Fall back to frontmatter version

                    all_skills.append(
                        Skill(
                            name=skill_name,
                            description=metadata.description,
                            version=version,
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
            if skill.path and not self.github.fetch_directory(
                self.skills_repo, skill.path, skill_dest
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

        # 3b. Enable GitHub Actions to create PRs (required for release-please).
        #     Resolve the full "owner/repo" form so the API call works even
        #     when the user passed a bare repo name like "my-skills".
        full_name = name
        if "/" not in name:
            full_name = f"{self.github.get_username()}/{name}"
        self.github.enable_workflow_pr_creation(full_name)

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

        # --- Scripts ---
        self._write_scaffold_sync_registry_script(repo_path)
        self._write_scaffold_validate_skills_script(repo_path)

        # --- Example skill ---
        self._write_scaffold_example_skill(repo_path)

        # --- Skill-release skill (bundled operational guide) ---
        self._write_scaffold_skill_release(repo_path)

    # -- Scaffold file writers -----------------------------------------------

    def _write_scaffold_skills_json(self, repo_path: Path) -> None:
        """Write skills.json — empty registry manifest."""
        registry = {"schema_version": "1.0", "skills": []}
        (repo_path / "skills.json").write_text(
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
        """Write .release-please-manifest.json with initial versions."""
        manifest = {
            "skill/example-skill": "0.1.0",
            "skill/skill-release": "0.1.0",
        }
        (repo_path / ".release-please-manifest.json").write_text(
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

    def _write_scaffold_readme(self, repo_path: Path, repo_name: str) -> None:
        """Write README.md with lifecycle documentation."""
        content = f"""\
# {repo_name}

Skills registry for [ContextHarness](https://github.com/co-labs-co/context-harness).

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
    H --> I["CLI: ch skill outdated"]

    style A fill:#f9f,stroke:#333
    style G fill:#9f9,stroke:#333
    style I fill:#9cf,stroke:#333
```

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for adding your first skill.

> **Important:** If you did not create this repo with `ch skill init-repo`,
> you must enable *"Allow GitHub Actions to create and approve pull requests"*
> in **Settings → Actions → General** for release-please to work.
> See [QUICKSTART.md](QUICKSTART.md#repository-setup) for details.

## Configure as Your Registry

```bash
# Set for current project
ch config set skills-repo {repo_name}

# Set for all projects (user-level)
ch config set skills-repo {repo_name} --global
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
│       └── validate-skills.yml   # PR validation checks
├── scripts/
│   ├── sync-registry.py          # Parses skills → skills.json
│   └── validate_skills.py        # Pydantic-based validation
├── skill/
│   └── example-skill/
│       ├── SKILL.md              # Skill content (no version field)
│       └── version.txt           # Managed by release-please
├── skills.json                   # Auto-maintained registry manifest
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
- **GitHub Actions must be allowed to create pull requests** (see below)

## Repository Setup

> **Note:** If you created this repository with `ch skill init-repo`, these
> settings are already configured automatically. Skip to [Steps](#steps).

release-please needs permission to open pull requests using `GITHUB_TOKEN`.
Enable this in your repository settings:

1. Go to **Settings → Actions → General**
2. Under *Workflow permissions*, select **Read and write permissions**
3. Check **Allow GitHub Actions to create and approve pull requests**
4. Click **Save**

Or use the GitHub CLI:

```bash
gh api repos/OWNER/REPO/actions/permissions/workflow \
  -X PUT -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=true
```

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
4. Users can now install: `ch skill install my-first-skill`

## Install Your Skill

```bash
# Configure this registry (one time)
ch config set skills-repo {repo_name}

# Install
ch skill install my-first-skill
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

# IMPORTANT: The repository must also have "Allow GitHub Actions to create
# and approve pull requests" enabled under Settings > Actions > General.
# Without this, the GITHUB_TOKEN cannot open release PRs even with the
# permissions block below.  `ch skill init-repo` enables this automatically;
# if you created the repo manually, enable it in the settings UI or run:
#   gh api repos/OWNER/REPO/actions/permissions/workflow \\
#     -X PUT -f default_workflow_permissions=write \\
#     -F can_approve_pull_request_reviews=true
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
          git add skills.json
          git diff --cached --quiet || git commit -m "chore: sync skills.json [skip ci]"
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

    def _write_scaffold_sync_registry_script(self, repo_path: Path) -> None:
        """Write scripts/sync-registry.py to rebuild skills.json."""
        content = '''\
#!/usr/bin/env python3
"""Rebuild skills.json from skill directories.

Parses SKILL.md frontmatter and version.txt for each skill,
then writes the consolidated skills.json registry manifest.

Usage:
    python scripts/sync-registry.py
"""

import hashlib
import json
from pathlib import Path

import frontmatter


def build_registry() -> dict:
    """Scan skill/ directories and build registry manifest."""
    skills_dir = Path("skill")
    skills = []

    if not skills_dir.exists():
        return {"schema_version": "1.0", "skills": []}

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

    return {"schema_version": "1.0", "skills": skills}


def main() -> None:
    """Rebuild and write skills.json."""
    registry = build_registry()

    Path("skills.json").write_text(
        json.dumps(registry, indent=2) + "\\n", encoding="utf-8"
    )

    print(f"Updated skills.json with {len(registry['skills'])} skill(s)")
    for skill in registry["skills"]:
        print(f"  - {skill['name']} v{skill['version']}")


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
`ch skill init-repo`).

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
8. Users detect update: ch skill outdated
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
            tool_target: Which tool directory to search:
                - "opencode": Only .opencode/skill/
                - "claude-code": Only .claude/skills/
                - "both" or None: Search both directories

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

        # Find the skill in available directories
        detector = ToolDetector(source_path)
        skills_dirs = detector.get_skills_dirs(tool_target if tool_target else "both")

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

                # Create version.txt for release-please (bootstrap version)
                version_file = skill_dest / "version.txt"
                if not version_file.exists():
                    version_file.write_text(f"{INITIAL_VERSION}\n")

                # Strip version from SKILL.md frontmatter (release-please
                # manages versions via version.txt, not frontmatter)
                self._strip_frontmatter_version(skill_dest / "SKILL.md")

                # Update release-please-config.json (add package entry)
                skill_package_path = f"{SKILLS_DIR}/{skill_name}"
                rp_config_path = tmppath / RELEASE_PLEASE_CONFIG
                if rp_config_path.exists():
                    rp_config = json.loads(rp_config_path.read_text(encoding="utf-8"))
                else:
                    rp_config = {
                        "$schema": "https://raw.githubusercontent.com/googleapis/"
                        "release-please/main/schemas/config.json",
                        "separate-pull-requests": True,
                        "include-component-in-tag": True,
                        "tag-separator": "@",
                        "packages": {},
                    }

                if skill_package_path not in rp_config.get("packages", {}):
                    rp_config.setdefault("packages", {})[skill_package_path] = {
                        "release-type": "simple",
                        "component": skill_name,
                    }
                    rp_config_path.write_text(json.dumps(rp_config, indent=2) + "\n")

                # Update .release-please-manifest.json (add version entry)
                rp_manifest_path = tmppath / RELEASE_PLEASE_MANIFEST
                if rp_manifest_path.exists():
                    rp_manifest = json.loads(
                        rp_manifest_path.read_text(encoding="utf-8")
                    )
                else:
                    rp_manifest = {}

                if skill_package_path not in rp_manifest:
                    rp_manifest[skill_package_path] = INITIAL_VERSION
                    rp_manifest_path.write_text(
                        json.dumps(rp_manifest, indent=2) + "\n"
                    )

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
- `{SKILLS_DIR}/{skill_name}/version.txt`
"""
                for item in skill_dest.rglob("*"):
                    if item.is_file() and item.name not in (
                        "SKILL.md",
                        "version.txt",
                    ):
                        rel_path = item.relative_to(skill_dest)
                        pr_body += f"- `{SKILLS_DIR}/{skill_name}/{rel_path}`\n"

                pr_body += f"""
### Registry Files Updated
- `{SKILLS_REGISTRY_PATH}`
- `{RELEASE_PLEASE_CONFIG}`
- `{RELEASE_PLEASE_MANIFEST}`

---
_Extracted via ContextHarness skill extractor_
"""

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

    @staticmethod
    def _strip_frontmatter_version(skill_md_path: Path) -> None:
        """Remove the version field from SKILL.md frontmatter.

        In a skills registry, version is managed by release-please via
        version.txt, not by the SKILL.md frontmatter.

        Args:
            skill_md_path: Path to the SKILL.md file
        """
        if not skill_md_path.exists():
            return

        content = skill_md_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return

        frontmatter_text = content[3:end_idx]
        body = content[end_idx:]

        lines = frontmatter_text.split("\n")
        filtered = [line for line in lines if not line.strip().startswith("version:")]
        new_frontmatter = "\n".join(filtered)

        skill_md_path.write_text(f"---{new_frontmatter}{body}", encoding="utf-8")
