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
from typing import TYPE_CHECKING, List, Optional, Protocol

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

        # --- HTTP serving (Docker/nginx) ---
        (repo_path / "nginx").mkdir(exist_ok=True)
        self._write_scaffold_dockerfile(repo_path)
        self._write_scaffold_docker_compose(repo_path)
        self._write_scaffold_nginx_conf(repo_path)

        # Create web directory for frontend files
        (repo_path / "web").mkdir(exist_ok=True)

        self._write_scaffold_index_html(repo_path)
        self._write_scaffold_skill_page(repo_path)

        # --- Example skill ---
        self._write_scaffold_example_skill(repo_path)

        # --- Skill-release skill (bundled operational guide) ---
        self._write_scaffold_skill_release(repo_path)

    # -- Scaffold file writers -----------------------------------------------

    def _write_scaffold_skills_json(self, repo_path: Path) -> None:
        """Write skills.json — registry manifest with scaffolded skills."""
        registry = {
            "schema_version": "1.0",
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

    def _write_scaffold_auto_rebase_workflow(self, repo_path: Path) -> None:
        """Write .github/workflows/auto-rebase.yml for automatic PR rebasing.

        Automatically rebases PRs when main changes to resolve conflicts
        with shared files (skills.json, release-please-config.json, etc.)
        that occur when multiple skills are extracted in parallel.
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

      - name: Get open PRs targeting main
        id: prs
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          echo "prs=$(gh pr list --base main --state open --json number,headRefName --jq '[.[] | "\\(.number):\\(.headRefName)"]' | tr '\\n' ' ')" >> $GITHUB_OUTPUT

      - name: Rebase PRs
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          for pr_info in ${{ steps.prs.outputs.prs }}; do
            pr_number=$(echo "$pr_info" | cut -d: -f1)
            pr_branch=$(echo "$pr_info" | cut -d: -f2)

            echo "Attempting to rebase PR #$pr_number ($pr_branch)"

            # Fetch the PR branch
            git fetch origin "$pr_branch"

            # Checkout the PR branch
            git checkout "$pr_branch"

            # Try to rebase onto main
            if git rebase origin/main; then
              echo "Rebase successful, pushing..."
              git push origin "$pr_branch" --force-with-lease
              echo "✅ PR #$pr_number rebased successfully"
            else
              echo "❌ Rebase failed for PR #$pr_number, aborting"
              git rebase --abort
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

        # Generate .listing.json for frontend file discovery
        listing = build_listing(skill_dir)
        (skill_dir / ".listing.json").write_text(
            json.dumps(listing, indent=2) + "\\n", encoding="utf-8"
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

    def _write_scaffold_dockerfile(self, repo_path: Path) -> None:
        """Write Dockerfile for serving the registry via HTTP.

        Uses nginx to serve static files, enabling users without GitHub
        access to consume skills from this registry.
        """
        content = """\
# Skills Registry HTTP Server
# Serves the registry via HTTP for users without GitHub access
#
# Build: docker build -t skills-registry .
# Run:   docker run -p 8080:80 skills-registry
#
# Usage with ContextHarness:
#   export CONTEXT_HARNESS_REGISTRY_URL=http://localhost:8080
#   context-harness skill list

FROM nginx:alpine

# Copy nginx configuration
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Copy web frontend
COPY web/index.html /usr/share/nginx/html/
COPY web/skill.html /usr/share/nginx/html/

# Copy registry files
COPY skills.json /usr/share/nginx/html/
COPY skill/ /usr/share/nginx/html/skill/

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost/skills.json || exit 1

# Expose port 80
EXPOSE 80

# Labels for container metadata
LABEL org.opencontainers.image.title="ContextHarness Skills Registry"
LABEL org.opencontainers.image.description="HTTP server for ContextHarness skills registry"
LABEL org.opencontainers.image.source="https://github.com/co-labs-co/context-harness"
"""
        (repo_path / "Dockerfile").write_text(content, encoding="utf-8")

    def _write_scaffold_docker_compose(self, repo_path: Path) -> None:
        """Write docker-compose.yml for easy local deployment."""
        content = """\
# Skills Registry - Docker Compose
#
# Quick start:
#   docker-compose up -d
#   export CONTEXT_HARNESS_REGISTRY_URL=http://localhost:8080
#   context-harness skill list
#
# Stop:
#   docker-compose down

services:
  skills-registry:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:80"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost/skills.json"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s

  # Optional: Add authentication with a reverse proxy
  # auth-proxy:
  #   image: nginx:alpine
  #   ports:
  #     - "443:443"
  #   volumes:
  #     - ./auth-nginx.conf:/etc/nginx/nginx.conf:ro
  #   depends_on:
  #     - skills-registry
"""
        (repo_path / "docker-compose.yml").write_text(content, encoding="utf-8")

    def _write_scaffold_nginx_conf(self, repo_path: Path) -> None:
        """Write nginx.conf for serving the registry.

        Configures nginx to serve static files with appropriate headers
        for CORS and caching.
        """
        content = """\
# Nginx configuration for ContextHarness Skills Registry
# Serves static files over HTTP with CORS support

server {
    listen 80;
    server_name localhost;

    # Serve files from the html directory
    root /usr/share/nginx/html;
    index index.html;

    # Enable gzip compression for JSON and text files
    gzip on;
    gzip_types application/json text/markdown text/plain text/html text/css application/javascript;
    gzip_min_length 256;

    # Cache control - skills don't change frequently
    location ~* \\.(json|md|txt)$ {
        expires 5m;
        add_header Cache-Control "public, max-age=300";
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, X-API-Key" always;
    }

    # Skills directory - serve all files
    location /skill/ {
        autoindex on;
        expires 5m;
        add_header Cache-Control "public, max-age=300";
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, X-API-Key" always;
    }

    # Health check endpoint
    location /health {
        add_header Content-Type text/plain always;
        add_header Access-Control-Allow-Origin * always;
        return 200 'OK';
    }

    # Handle OPTIONS requests for CORS preflight
    location / {
        if ($request_method = OPTIONS) {
            return 204;
        }

        # Serve index.html for root, skills.json for API clients
        try_files $uri $uri/ /index.html;

        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, X-API-Key" always;
    }
}
"""
        (repo_path / "nginx" / "nginx.conf").write_text(content, encoding="utf-8")

    def _write_scaffold_index_html(self, repo_path: Path) -> None:
        """Write index.html - static frontend for browsing skills.

        A clean shadcn-inspired UI using Tailwind CSS with the project theme.
        """
        content = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skills Registry</title>
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

        * {
            border-color: var(--border);
        }

        body {
            font-family: 'Noto Sans Mono', ui-sans-serif, system-ui, sans-serif;
            background: var(--background);
            color: var(--foreground);
        }

        .font-mono {
            font-family: 'Fira Code', ui-monospace, monospace;
        }
    </style>
</head>
<body class="min-h-screen">
    <div class="max-w-5xl mx-auto px-6 py-12">
        <!-- Header -->
        <header class="mb-12">
            <h1 class="text-3xl font-semibold tracking-tight mb-2">Skills Registry</h1>
            <p class="text-[var(--muted-foreground)]">Extend your AI assistant with specialized capabilities</p>
        </header>

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

        async function loadSkills() {
            try {
                const res = await fetch('./skills.json');
                if (!res.ok) throw new Error('Failed to fetch');
                const data = await res.json();
                skills = data.skills || [];
                render();
            } catch (e) {
                document.getElementById('skills-list').innerHTML = `
                    <div class="text-center py-12 text-[var(--muted-foreground)]">
                        Failed to load skills
                    </div>
                `;
            }
        }

        function render(list = skills) {
            const container = document.getElementById('skills-list');

            if (!list.length) {
                container.innerHTML = `
                    <div class="text-center py-12 text-[var(--muted-foreground)]">
                        No skills found
                    </div>
                `;
                return;
            }

            container.innerHTML = list.map(s => `
                <a href="skill.html?name=${encodeURIComponent(s.name)}" class="block group p-4 bg-[var(--card)] border rounded-[var(--radius)] hover:border-[var(--ring)] transition-colors">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <h3 class="font-medium">${esc(s.name)}</h3>
                                <span class="font-mono text-xs px-1.5 py-0.5 bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded">
                                    v${esc(s.version || '0.0.0')}
                                </span>
                            </div>
                            <p class="text-sm text-[var(--muted-foreground)] line-clamp-2 mb-2">
                                ${esc(s.description || 'No description')}
                            </p>
                            ${s.tags?.length ? `
                                <div class="flex flex-wrap gap-1.5">
                                    ${s.tags.slice(0, 3).map(t => `
                                        <span class="text-xs px-2 py-0.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-full">
                                            ${esc(t)}
                                        </span>
                                    `).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <span class="shrink-0 px-3 py-1.5 text-xs font-medium bg-[var(--primary)] text-[var(--primary-foreground)] rounded-[var(--radius)] hover:opacity-90 transition-opacity">
                            View
                        </span>
                    </div>
                </a>
            `).join('');
        }

        function copyInstall(name) {
            const cmd = `ch skill install ${name}`;
            navigator.clipboard.writeText(cmd).then(() => {
                const toast = document.getElementById('toast');
                toast.classList.remove('opacity-0', 'translate-y-2');
                setTimeout(() => toast.classList.add('opacity-0', 'translate-y-2'), 1500);
            }).catch(() => {
                const ta = document.createElement('textarea');
                ta.value = cmd;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            });
        }

        function esc(str) {
            const el = document.createElement('div');
            el.textContent = str;
            return el.innerHTML;
        }

        let debounceTimer;
        document.getElementById('search').addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const q = e.target.value.toLowerCase();
                if (!q) return render();
                render(skills.filter(s =>
                    s.name?.toLowerCase().includes(q) ||
                    s.description?.toLowerCase().includes(q) ||
                    s.tags?.some(t => t.toLowerCase().includes(q))
                ));
            }, 150);
        });

        loadSkills();
    </script>
</body>
</html>
"""
        (repo_path / "web" / "index.html").write_text(content, encoding="utf-8")

    def _write_scaffold_skill_page(self, repo_path: Path) -> None:
        """Write skill.html - individual skill detail page with file explorer."""
        content = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skill Details</title>
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

        body {
            font-family: 'Noto Sans Mono', ui-sans-serif, system-ui, sans-serif;
            background: var(--background);
            color: var(--foreground);
        }

        .font-mono { font-family: 'Fira Code', ui-monospace, monospace; }

        .file-tree { user-select: none; }

        .file-item {
            cursor: pointer;
            padding: 0.375rem 0.5rem;
            border-radius: var(--radius);
            transition: background 0.15s;
        }

        .file-item:hover { background: var(--muted); }
        .file-item.active { background: var(--accent); color: var(--accent-foreground); }

        .file-content {
            white-space: pre-wrap;
            word-break: break-word;
            font-family: 'Fira Code', ui-monospace, monospace;
            font-size: 0.8125rem;
            line-height: 1.6;
        }
    </style>
</head>
<body class="min-h-screen">
    <div class="max-w-6xl mx-auto px-6 py-8">
        <!-- Header -->
        <header class="mb-8">
            <a href="index.html" class="inline-flex items-center gap-2 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] mb-4 transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                </svg>
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

        <!-- Main Content -->
        <div id="error-state" class="hidden text-center py-16">
            <p class="text-[var(--muted-foreground)] mb-4">Skill not found</p>
            <a href="index.html" class="text-[var(--ring)] hover:underline">Return to skills list</a>
        </div>

        <div id="skill-content" class="hidden">
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <!-- File Tree -->
                <div class="lg:col-span-1">
                    <div class="bg-[var(--card)] border rounded-[var(--radius)] p-4 sticky top-4">
                        <h2 class="text-sm font-medium mb-3 text-[var(--muted-foreground)]">Files</h2>
                        <div id="file-tree" class="file-tree text-sm space-y-0.5">
                            <div class="text-[var(--muted-foreground)] py-2">Loading...</div>
                        </div>
                    </div>
                </div>

                <!-- File Content -->
                <div class="lg:col-span-3">
                    <div class="bg-[var(--card)] border rounded-[var(--radius)]">
                        <!-- File toolbar -->
                        <div class="flex items-center justify-between px-4 py-3 border-b">
                            <div class="flex items-center gap-2">
                                <span id="file-icon" class="text-[var(--muted-foreground)]">📄</span>
                                <span id="file-path" class="font-mono text-sm">Select a file</span>
                            </div>
                            <button id="copy-btn" class="px-2.5 py-1 text-xs bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity" onclick="copyFileContent()">
                                Copy
                            </button>
                        </div>
                        <!-- File content -->
                        <div id="file-content-wrapper" class="p-4 min-h-[400px] max-h-[70vh] overflow-auto">
                            <div id="file-content" class="file-content">Select a file to view its contents</div>
                        </div>
                    </div>

                    <!-- Getting Started -->
                    <div class="mt-6 space-y-4">
                        <!-- Setup -->
                        <div class="p-4 bg-[var(--card)] border rounded-[var(--radius)]">
                            <h3 class="text-sm font-medium mb-3 text-[var(--muted-foreground)]">Getting Started</h3>
                            <div class="space-y-3 text-sm">
                                <p class="text-[var(--muted-foreground)]">First, configure ContextHarness to use this registry:</p>
                                <div class="flex items-center gap-2">
                                    <code id="setup-cmd" class="flex-1 px-3 py-2 bg-[var(--background)] rounded font-mono text-xs"></code>
                                    <button onclick="copySetup()" class="px-2.5 py-2 text-xs font-medium bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity">
                                        Copy
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Install command -->
                        <div class="p-4 bg-[var(--card)] border rounded-[var(--radius)]">
                            <h3 class="text-sm font-medium mb-2 text-[var(--muted-foreground)]">Install Skill</h3>
                            <div class="flex items-center gap-2">
                                <code id="install-cmd" class="flex-1 px-3 py-2 bg-[var(--background)] rounded font-mono text-sm"></code>
                                <button onclick="copyInstall()" class="px-3 py-2 text-xs font-medium bg-[var(--primary)] text-[var(--primary-foreground)] rounded hover:opacity-90 transition-opacity">
                                    Copy
                                </button>
                            </div>
                            <p class="text-xs text-[var(--muted-foreground)] mt-2">Or install directly without configuring: <code id="install-direct-cmd" class="px-1.5 py-0.5 bg-[var(--background)] rounded font-mono text-xs"></code></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div id="toast" class="fixed bottom-6 right-6 px-4 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-[var(--radius)] text-sm font-medium opacity-0 translate-y-2 transition-all duration-200 pointer-events-none">
        Copied to clipboard
    </div>

    <script>
        let skillName = '';
        let skillMeta = null;
        let fileCache = {};
        let currentFile = null;

        // Get skill name from URL
        const params = new URLSearchParams(window.location.search);
        skillName = params.get('name');

        if (!skillName) {
            document.getElementById('error-state').classList.remove('hidden');
        } else {
            loadSkill();
        }

        async function loadSkill() {
            try {
                // Fetch skills.json to get metadata
                const res = await fetch('./skills.json');
                if (!res.ok) throw new Error('Failed to fetch skills.json');
                const data = await res.json();
                skillMeta = data.skills?.find(s => s.name === skillName);

                if (!skillMeta) {
                    document.getElementById('error-state').classList.remove('hidden');
                    return;
                }

                renderHeader();
                document.getElementById('skill-content').classList.remove('hidden');
                document.getElementById('install-cmd').textContent = `ch skill install ${skillName}`;
                document.getElementById('setup-cmd').textContent = `ch skill use-registry ${window.location.origin}`;
                document.getElementById('install-direct-cmd').textContent = `ch skill install ${skillName} --registry ${window.location.origin}`;

                // Discover and render file tree
                await discoverFiles();
            } catch (e) {
                console.error('Error loading skill:', e);
                document.getElementById('error-state').classList.remove('hidden');
            }
        }

        function renderHeader() {
            document.getElementById('skill-name').textContent = skillMeta.name;
            document.getElementById('skill-description').textContent = skillMeta.description || 'No description';

            let metaHtml = `<span class="font-mono text-xs px-1.5 py-0.5 bg-[var(--secondary)] text-[var(--secondary-foreground)] rounded">v${skillMeta.version || '0.0.0'}</span>`;
            if (skillMeta.author) {
                metaHtml += `<div class="text-xs text-[var(--muted-foreground)] mt-2">by ${esc(skillMeta.author)}</div>`;
            }
            if (skillMeta.tags?.length) {
                metaHtml += `<div class="flex flex-wrap gap-1 mt-2 justify-end">${skillMeta.tags.map(t => `<span class="text-xs px-2 py-0.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded-full">${esc(t)}</span>`).join('')}</div>`;
            }
            document.getElementById('skill-meta').innerHTML = metaHtml;
        }

        async function discoverFiles() {
            const basePath = `skill/${skillName}`;
            const files = [];

            // Known files at root level
            const knownFiles = [
                { path: 'SKILL.md', icon: '📄', name: 'SKILL.md' },
                { path: 'version.txt', icon: '📄', name: 'version.txt' },
                { path: 'CHANGELOG.md', icon: '📄', name: 'CHANGELOG.md' },
            ];

            // Known directories with their expected file extensions
            const knownDirs = [
                { dir: 'references', extensions: ['.md', '.txt'] },
                { dir: 'scripts', extensions: ['.sh', '.py', '.js', '.ts'] },
                { dir: 'examples', extensions: ['.md', '.txt', '.json', '.yaml', '.yml'] },
                { dir: 'templates', extensions: ['.md', '.txt', '.json', '.yaml', '.yml'] },
                { dir: 'assets', extensions: ['.png', '.jpg', '.svg', '.gif'] },
            ];

            // Check known files at root
            for (const file of knownFiles) {
                const exists = await checkFileExists(`${basePath}/${file.path}`);
                if (exists) {
                    files.push({ ...file, type: 'file' });
                }
            }

            // Try to fetch .listing.json first (most reliable)
            let listing = null;
            try {
                const listingRes = await fetch(`${basePath}/.listing.json`);
                if (listingRes.ok) {
                    listing = await listingRes.json();
                }
            } catch (e) {}

            if (listing) {
                // Use listing as source of truth
                for (const item of (listing.files || [])) {
                    // Handle both string format ("SKILL.md") and object format ({path: "SKILL.md"})
                    const filePath = typeof item === 'string' ? item : (item.path || item.name);
                    if (!filePath) continue;
                    if (!files.find(f => f.path === filePath)) {
                        files.push({
                            path: filePath,
                            name: typeof item === 'string' ? item : (item.name || filePath.split('/').pop()),
                            icon: getFileIcon(filePath),
                            type: 'file'
                        });
                    }
                }
                for (const item of (listing.directories || [])) {
                    const dirName = typeof item === 'string' ? item : (item.name || item.path);
                    if (!dirName) continue;
                    const dirFiles = (listing.directory_files || {})[dirName] || [];
                    files.push({
                        path: dirName,
                        name: dirName,
                        icon: '📁',
                        type: 'dir',
                        files: dirFiles.map(f => ({
                            path: `${dirName}/${f}`,
                            name: f,
                            icon: getFileIcon(f),
                            type: 'file'
                        }))
                    });
                }
            } else {
                // Probe known directories
                for (const dir of knownDirs) {
                    const dirFiles = await probeDirectory(`${basePath}/${dir.dir}`, dir.extensions);
                    if (dirFiles.length > 0) {
                        files.push({
                            path: dir.dir,
                            name: dir.dir,
                            icon: '📁',
                            type: 'dir',
                            files: dirFiles
                        });
                    }
                }
            }

            renderFileTree(files);

            // Auto-select SKILL.md if it exists
            const skillMd = files.find(f => f.path === 'SKILL.md');
            if (skillMd) {
                selectFile(skillMd);
            }
        }

        async function probeDirectory(dirPath, extensions) {
            const files = [];
            // Common file name patterns to probe
            const patterns = [
                'README', 'readme', 'index', 'main', 'guide', 'intro',
                'getting-started', 'setup', 'config', 'example',
                'output-patterns', 'workflows', 'troubleshooting',
                'init_skill', 'package_skill', 'quick_validate',
                'utils', 'helpers', 'common'
            ];

            for (const pattern of patterns) {
                for (const ext of extensions) {
                    const filePath = `${pattern}${ext}`;
                    const exists = await checkFileExists(`${dirPath}/${filePath}`);
                    if (exists) {
                        files.push({
                            path: filePath,
                            name: filePath,
                            icon: getFileIcon(filePath),
                            type: 'file'
                        });
                    }
                }
            }

            return files;
        }

        async function checkFileExists(path) {
            try {
                const res = await fetch(path, { method: 'HEAD' });
                return res.ok;
            } catch (e) {
                return false;
            }
        }

        function getFileIcon(path) {
            const ext = path.split('.').pop()?.toLowerCase();
            const icons = {
                'md': '📄', 'txt': '📄', 'json': '📄',
                'sh': '⚡', 'py': '🐍', 'js': '⚡', 'ts': '⚡',
                'yaml': '⚙️', 'yml': '⚙️',
                'png': '🖼️', 'jpg': '🖼️', 'svg': '🖼️', 'gif': '🖼️',
            };
            return icons[ext] || '📄';
        }

        function renderFileTree(files) {
            const container = document.getElementById('file-tree');

            if (!files.length) {
                container.innerHTML = '<div class="text-[var(--muted-foreground)] py-2">No files found</div>';
                return;
            }

            container.innerHTML = files.map(f => {
                if (f.type === 'dir') {
                    return `
                        <div class="directory">
                            <div class="file-item flex items-center gap-2" onclick="toggleDir(this)">
                                <span class="transform transition-transform">${f.icon}</span>
                                <span>${esc(f.name)}</span>
                            </div>
                            <div class="pl-4 hidden">
                                ${f.files?.map(sf => `
                                    <div class="file-item flex items-center gap-2" onclick="selectFile({path: '${f.path}/${sf.name}', name: '${sf.name}', icon: '${sf.icon}', type: 'file'})">
                                        <span>${sf.icon}</span>
                                        <span>${esc(sf.name)}</span>
                                    </div>
                                `).join('') || ''}
                            </div>
                        </div>
                    `;
                }
                return `
                    <div class="file-item flex items-center gap-2" onclick="selectFile({path: '${esc(f.path)}', name: '${esc(f.name)}', icon: '${f.icon}', type: 'file'})">
                        <span>${f.icon}</span>
                        <span>${esc(f.name)}</span>
                    </div>
                `;
            }).join('');
        }

        function toggleDir(el) {
            const content = el.nextElementSibling;
            content.classList.toggle('hidden');
        }

        async function selectFile(file) {
            currentFile = file;

            // Update active state
            document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
            event?.target?.closest('.file-item')?.classList.add('active');

            // Update toolbar
            document.getElementById('file-icon').textContent = file.icon;
            document.getElementById('file-path').textContent = file.path;

            // Fetch and display content
            const basePath = `skill/${skillName}`;
            const fullPath = `${basePath}/${file.path}`;

            try {
                if (!fileCache[fullPath]) {
                    const res = await fetch(fullPath);
                    if (!res.ok) throw new Error('Failed to fetch');
                    fileCache[fullPath] = await res.text();
                }

                const content = fileCache[fullPath];
                renderContent(content, file.path);
            } catch (e) {
                document.getElementById('file-content').innerHTML = '<div class="text-[var(--muted-foreground)]">Failed to load file</div>';
            }
        }

        function renderContent(content, path) {
            const container = document.getElementById('file-content');
            container.textContent = content;
        }

        async function copyFileContent() {
            if (!currentFile) return;
            const content = fileCache[`skill/${skillName}/${currentFile.path}`];
            if (!content) return;

            try {
                await navigator.clipboard.writeText(content);
                showToast();
            } catch (e) {
                const ta = document.createElement('textarea');
                ta.value = content;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast();
            }
        }

        function copyInstall() {
            const cmd = `ch skill install ${skillName}`;
            navigator.clipboard.writeText(cmd).then(() => {
                showToast();
            }).catch(() => {
                const ta = document.createElement('textarea');
                ta.value = cmd;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast();
            });
        }

        function copySetup() {
            const cmd = document.getElementById('setup-cmd').textContent;
            navigator.clipboard.writeText(cmd).then(() => {
                showToast();
            }).catch(() => {
                const ta = document.createElement('textarea');
                ta.value = cmd;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast();
            });
        }

        function showToast() {
            const toast = document.getElementById('toast');
            toast.classList.remove('opacity-0', 'translate-y-2');
            setTimeout(() => toast.classList.add('opacity-0', 'translate-y-2'), 1500);
        }

        function esc(str) {
            if (!str) return '';
            const el = document.createElement('div');
            el.textContent = str;
            return el.innerHTML;
        }
    </script>
</body>
</html>
"""
        (repo_path / "web" / "skill.html").write_text(content, encoding="utf-8")

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
