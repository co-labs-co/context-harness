"""Skills management for ContextHarness.

This module provides functionality to:
- List available skills from the central skills repository
- Install skills from the central repository
- Extract local skills and create PRs to the central repository
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from rich.console import Console
from rich.table import Table

from context_harness.primitives.tool_detector import (
    ToolDetector,
    ToolTarget,
)
from context_harness.primitives.skill import VersionStatus
from context_harness.services.skills_registry import resolve_skills_repo_with_loading

console = Console()

SKILLS_REGISTRY_PATH = "skills.json"
SKILLS_DIR = "skill"  # singular, matching OpenCode standard


def get_current_skills_repo() -> str:
    """Get the currently configured skills repository.

    Uses the layered configuration resolution:
    1. CONTEXT_HARNESS_SKILLS_REPO environment variable
    2. Project config (opencode.json skillsRegistry.default)
    3. User config (~/.context-harness/config.json)
    4. Default (co-labs-co/context-harness-skills)

    Returns:
        The skills repository in owner/repo format
    """
    repo, _ = resolve_skills_repo_with_loading()
    return repo


class SkillResult(Enum):
    """Result of a skill operation."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    NOT_FOUND = "not_found"
    AUTH_ERROR = "auth_error"
    ERROR = "error"


@dataclass
class SkillInfo:
    """Information about a skill from the registry."""

    name: str
    description: str
    version: str
    author: str
    tags: List[str]
    path: str
    min_context_harness_version: Optional[str] = None


def check_gh_auth(quiet: bool = False) -> bool:
    """Verify GitHub CLI is authenticated.

    Args:
        quiet: If True, suppress output messages

    Returns:
        True if authenticated, False otherwise
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if not quiet:
                console.print("[red]Error: GitHub CLI is not authenticated.[/red]")
                console.print("[dim]Run 'gh auth login' to authenticate.[/dim]")
            return False
        return True
    except FileNotFoundError:
        if not quiet:
            console.print("[red]Error: GitHub CLI (gh) is not installed.[/red]")
            console.print("[dim]Install it from https://cli.github.com[/dim]")
        return False


def check_repo_access(repo: Optional[str] = None, quiet: bool = False) -> bool:
    """Check if user has access to the skills repository.

    Args:
        repo: Repository in owner/name format (uses configured repo if None)
        quiet: If True, suppress output messages

    Returns:
        True if user has access, False otherwise
    """
    if repo is None:
        repo = get_current_skills_repo()
    result = subprocess.run(
        ["gh", "api", f"/repos/{repo}", "--silent"],
        capture_output=True,
    )
    if result.returncode != 0:
        if not quiet:
            console.print(f"[red]Error: Cannot access repository '{repo}'[/red]")
            console.print(
                "[dim]Make sure you have access to the private skills repository.[/dim]"
            )
        return False
    return True


def get_skills_registry(quiet: bool = False) -> Optional[Dict[str, Any]]:
    """Fetch the skills registry from the central repository.

    Args:
        quiet: If True, suppress output messages

    Returns:
        Registry dict or None if fetch failed
    """
    if not check_gh_auth(quiet=quiet):
        return None

    if not check_repo_access(quiet=quiet):
        return None

    skills_repo = get_current_skills_repo()
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{skills_repo}/contents/{SKILLS_REGISTRY_PATH}",
                "-H",
                "Accept: application/vnd.github.raw+json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        if not quiet:
            if "404" in str(e.stderr):
                console.print(
                    "[yellow]Skills registry not found. "
                    "The repository may be empty.[/yellow]"
                )
            else:
                console.print(f"[red]Error fetching skills registry: {e.stderr}[/red]")
        return None
    except json.JSONDecodeError as e:
        if not quiet:
            console.print(f"[red]Error parsing skills registry: {e}[/red]")
        return None


def parse_skill_info(skill_data: Dict[str, Any]) -> SkillInfo:
    """Parse skill info from registry data.

    Args:
        skill_data: Skill data dict from registry

    Returns:
        SkillInfo dataclass
    """
    return SkillInfo(
        name=skill_data.get("name", ""),
        description=skill_data.get("description", ""),
        version=skill_data.get("version", "0.0.0"),
        author=skill_data.get("author", "unknown"),
        tags=skill_data.get("tags", []),
        path=skill_data.get("path", ""),
        min_context_harness_version=skill_data.get("min_context_harness_version"),
    )


def list_skills(
    tags: Optional[List[str]] = None, quiet: bool = False
) -> List[SkillInfo]:
    """List available skills from the central repository.

    Args:
        tags: Optional list of tags to filter by
        quiet: If True, suppress output messages

    Returns:
        List of SkillInfo objects
    """
    registry = get_skills_registry(quiet=quiet)
    if registry is None:
        return []

    skills = [parse_skill_info(s) for s in registry.get("skills", [])]

    # Filter by tags if specified
    if tags:
        tags_lower = [t.lower() for t in tags]
        skills = [s for s in skills if any(t.lower() in tags_lower for t in s.tags)]

    if not quiet and skills:
        table = Table(title="Available Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Version", style="green")
        table.add_column("Tags", style="dim")

        for skill in skills:
            table.add_row(
                skill.name,
                _truncate_description(skill.description, 50),
                skill.version,
                ", ".join(skill.tags[:3]),
            )

        console.print(table)

    return skills


def get_skill_info(skill_name: str, quiet: bool = False) -> Optional[SkillInfo]:
    """Get detailed information about a specific skill.

    Args:
        skill_name: Name of the skill
        quiet: If True, suppress output messages

    Returns:
        SkillInfo or None if not found
    """
    registry = get_skills_registry(quiet=True)
    if registry is None:
        if not quiet:
            console.print("[red]Could not fetch skills registry.[/red]")
        return None

    for skill_data in registry.get("skills", []):
        if skill_data.get("name") == skill_name:
            skill = parse_skill_info(skill_data)
            if not quiet:
                console.print(f"\n[bold cyan]{skill.name}[/bold cyan] v{skill.version}")
                console.print(f"[dim]by {skill.author}[/dim]\n")
                console.print(skill.description)
                console.print(f"\n[dim]Tags: {', '.join(skill.tags)}[/dim]")
                if skill.min_context_harness_version:
                    console.print(
                        f"[dim]Requires ContextHarness >= {skill.min_context_harness_version}[/dim]"
                    )
            return skill

    if not quiet:
        console.print(f"[red]Skill '{skill_name}' not found.[/red]")
    return None


def _fetch_directory_recursive(
    repo: str, path: str, dest: Path, quiet: bool = False
) -> bool:
    """Recursively fetch a directory from GitHub.

    Args:
        repo: Repository in owner/name format
        path: Path in the repository
        dest: Local destination path
        quiet: If True, suppress output messages

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"/repos/{repo}/contents/{path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        contents = json.loads(result.stdout)

        # Handle case where API returns a single file instead of directory
        if isinstance(contents, dict):
            contents = [contents]

        dest.mkdir(parents=True, exist_ok=True)

        for item in contents:
            item_name = item["name"]
            item_path = dest / item_name

            if item["type"] == "file":
                # Fetch file content
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
                if not quiet:
                    console.print(f"  [dim]Downloaded: {item_name}[/dim]")

            elif item["type"] == "dir":
                # Recursively fetch subdirectory
                if not _fetch_directory_recursive(repo, item["path"], item_path, quiet):
                    return False

        return True

    except subprocess.CalledProcessError as e:
        if not quiet:
            console.print(f"[red]Error fetching {path}: {e.stderr}[/red]")
        return False
    except json.JSONDecodeError as e:
        if not quiet:
            console.print(f"[red]Error parsing response: {e}[/red]")
        return False


def install_skill(
    skill_name: str,
    target: str = ".",
    force: bool = False,
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> SkillResult:
    """Install a skill from the central repository.

    Args:
        skill_name: Name of the skill to install
        target: Target directory (default: current directory)
        force: If True, overwrite existing skill
        quiet: If True, suppress output messages
        tool_target: Which tool(s) to install for:
            - "opencode": Install to .opencode/skill/
            - "claude-code": Install to .claude/skills/
            - "both": Install to both directories
            - None: Auto-detect installed tools

    Returns:
        SkillResult indicating success or failure
    """
    # Get skill info
    skill = get_skill_info(skill_name, quiet=True)
    if skill is None:
        if not quiet:
            console.print(f"[red]Skill '{skill_name}' not found in registry.[/red]")
        return SkillResult.NOT_FOUND

    target_path = Path(target).resolve()
    detector = ToolDetector(target_path)

    # Determine installation directories based on tool_target
    if tool_target == "both":
        install_dirs = [
            detector.get_opencode_paths().skills_dir / skill_name,
            detector.get_claude_code_paths().skills_dir / skill_name,
        ]
    elif tool_target == "opencode":
        install_dirs = [detector.get_opencode_paths().skills_dir / skill_name]
    elif tool_target == "claude-code":
        install_dirs = [detector.get_claude_code_paths().skills_dir / skill_name]
    else:
        # Auto-detect: use primary tool, or default to OpenCode
        detected = detector.detect()
        if detected.primary:
            paths = detected.get_paths(detected.primary)
            if paths:
                install_dirs = [paths.skills_dir / skill_name]
            else:
                install_dirs = [detector.get_opencode_paths().skills_dir / skill_name]
        else:
            # No tools installed, default to OpenCode
            install_dirs = [detector.get_opencode_paths().skills_dir / skill_name]

    # Check if already exists in any target directory
    for skill_dest in install_dirs:
        if skill_dest.exists() and not force:
            if not quiet:
                console.print(
                    f"[yellow]Skill '{skill_name}' already installed at {skill_dest}[/yellow]"
                )
                console.print("[dim]Use --force to overwrite.[/dim]")
            return SkillResult.ALREADY_EXISTS

    # Remove existing if force
    for skill_dest in install_dirs:
        if skill_dest.exists() and force:
            shutil.rmtree(skill_dest)

    if not quiet:
        console.print(f"[cyan]Installing skill: {skill_name}...[/cyan]")

    # Install to all target directories
    skills_repo = get_current_skills_repo()
    for i, skill_dest in enumerate(install_dirs):
        # Ensure parent directory exists
        skill_dest.parent.mkdir(parents=True, exist_ok=True)

        if not _fetch_directory_recursive(skills_repo, skill.path, skill_dest, quiet):
            # Cleanup any partially created skill directory
            if skill_dest.exists():
                shutil.rmtree(skill_dest)
            # Attempt to remove the parent directory if it is now empty
            try:
                skill_dest.parent.rmdir()
            except OSError:
                # Parent directory is not empty or cannot be removed; ignore
                pass
            if not quiet:
                console.print(f"[red]Failed to install skill '{skill_name}'.[/red]")
            return SkillResult.ERROR

        # For subsequent installs (in "both" mode), copy from first install
        if i == 0 and len(install_dirs) > 1:
            # First install succeeded, copy to other directories
            try:
                for other_dest in install_dirs[1:]:
                    other_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(skill_dest, other_dest, dirs_exist_ok=True)
            except Exception as e:
                if not quiet:
                    console.print(
                        f"[red]Failed to copy skill '{skill_name}' to all target "
                        f"directories: {e}[/red]"
                    )
            break  # Don't fetch again, we've copied

    if not quiet:
        console.print(
            f"\n[green]✅ Skill '{skill_name}' installed successfully![/green]"
        )
        for skill_dest in install_dirs:
            console.print(f"[dim]Location: {skill_dest}[/dim]")

    return SkillResult.SUCCESS


def init_repo(
    name: str,
    *,
    private: bool = True,
    description: Optional[str] = None,
    quiet: bool = False,
) -> tuple[SkillResult, Optional[str]]:
    """Initialize a new skills registry repository on GitHub.

    Creates a GitHub repository scaffolded with the standard skills registry
    structure (skills.json, skill/.gitkeep, README.md).

    Args:
        name: Repository name (e.g., "my-skills" or "my-org/my-skills")
        private: Whether the repository should be private
        description: Repository description
        quiet: If True, suppress output messages

    Returns:
        Tuple of (SkillResult, repo URL or None)
    """
    from context_harness.services.skill_service import SkillService
    from context_harness.primitives import Success, Failure, ErrorCode

    service = SkillService()

    if not quiet:
        console.print(f"[cyan]Creating skills registry: {name}...[/cyan]")

    result = service.init_registry_repo(
        name=name,
        private=private,
        description=description,
    )

    if isinstance(result, Success):
        repo = result.value
        if not quiet:
            console.print(f"\n[green]✅ {result.message}[/green]")
            console.print(f"[dim]URL: {repo.url}[/dim]")
        return SkillResult.SUCCESS, repo.url

    if isinstance(result, Failure):
        if result.code == ErrorCode.REPO_ALREADY_EXISTS:
            if not quiet:
                console.print(f"[yellow]⚠️  {result.error}[/yellow]")
            return SkillResult.ALREADY_EXISTS, None
        elif result.code == ErrorCode.AUTH_REQUIRED:
            if not quiet:
                console.print(f"[red]Authentication error: {result.error}[/red]")
                console.print("[dim]Run 'gh auth login' to authenticate.[/dim]")
            return SkillResult.AUTH_ERROR, None
        else:
            if not quiet:
                console.print(f"[red]❌ {result.error}[/red]")
            return SkillResult.ERROR, None

    return SkillResult.ERROR, None


def _validate_skill(skill_path: Path, quiet: bool = False) -> bool:
    """Validate a skill directory structure.

    Args:
        skill_path: Path to the skill directory
        quiet: If True, suppress output messages

    Returns:
        True if valid, False otherwise
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        if not quiet:
            console.print(f"[red]Error: SKILL.md not found in {skill_path}[/red]")
        return False

    # Check for required frontmatter
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        if not quiet:
            console.print("[red]Error: SKILL.md missing YAML frontmatter[/red]")
        return False

    # Check for complete frontmatter
    frontmatter_end = content.find("---", 3)
    if frontmatter_end == -1:
        if not quiet:
            console.print("[red]Error: SKILL.md has incomplete frontmatter[/red]")
        return False

    # Parse frontmatter fields and ensure required ones are present and non-empty
    frontmatter_data = _parse_skill_frontmatter(skill_path)

    name = frontmatter_data.get("name", "").strip()
    if not name:
        if not quiet:
            console.print(
                "[red]Error: SKILL.md frontmatter missing or empty 'name' field[/red]"
            )
        return False

    description = frontmatter_data.get("description", "").strip()
    if not description:
        if not quiet:
            console.print(
                "[red]Error: SKILL.md frontmatter missing or empty 'description' field[/red]"
            )
        return False

    return True


def _validate_skill_name(skill_name: str) -> bool:
    """Validate that a skill name contains only safe characters.

    Safe characters: alphanumeric, hyphens, underscores.
    This prevents potential shell injection when used in commands.

    Args:
        skill_name: Name to validate

    Returns:
        True if valid, False otherwise
    """
    import re

    return bool(re.match(r"^[a-zA-Z0-9_-]+$", skill_name))


def _parse_skill_frontmatter(skill_path: Path) -> Dict[str, str]:
    """Parse skill frontmatter from SKILL.md using YAML parser.

    Args:
        skill_path: Path to the skill directory

    Returns:
        Dict with frontmatter fields
    """
    skill_md = skill_path / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    frontmatter_end = content.find("---", 3)
    frontmatter_str = content[3:frontmatter_end].strip()

    try:
        result = yaml.safe_load(frontmatter_str)
        if result is None:
            return {}
        # Convert all values to strings for consistency
        return {k: str(v) if v is not None else "" for k, v in result.items()}
    except yaml.YAMLError:
        # Fallback to simple parsing if YAML parsing fails
        result = {}
        for line in frontmatter_str.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result


def extract_skill(
    skill_name: str,
    source_path: str = ".",
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> tuple[SkillResult, Optional[str]]:
    """Extract a local skill and create a PR to the central repository.

    Args:
        skill_name: Name of the skill to extract
        source_path: Source directory containing skills
        quiet: If True, suppress output messages
        tool_target: Which tool's skill directory to search:
            - "opencode": Search .opencode/skill/
            - "claude-code": Search .claude/skills/
            - None: Auto-detect, searching all installed tool directories

    Returns:
        Tuple of (SkillResult, PR URL or None)
    """
    # Validate skill name contains only safe characters
    if not _validate_skill_name(skill_name):
        if not quiet:
            console.print(
                f"[red]Error: Invalid skill name '{skill_name}'. "
                "Only alphanumeric characters, hyphens, and underscores are allowed.[/red]"
            )
        return SkillResult.ERROR, None

    if not check_gh_auth(quiet=quiet):
        return SkillResult.AUTH_ERROR, None

    if not check_repo_access(quiet=quiet):
        return SkillResult.AUTH_ERROR, None

    source = Path(source_path).resolve()
    detector = ToolDetector(source)

    # Find the skill in the appropriate directories
    skill_source: Optional[Path] = None

    if tool_target == "opencode":
        candidate = detector._opencode_paths.skills_dir / skill_name
        if candidate.exists():
            skill_source = candidate
    elif tool_target == "claude-code":
        candidate = detector._claude_code_paths.skills_dir / skill_name
        if candidate.exists():
            skill_source = candidate
    else:
        # Auto-detect: search all installed tool directories
        detected = detector.detect()

        # Check OpenCode first (primary/default)
        if detected.opencode:
            candidate = detected.opencode_paths.skills_dir / skill_name
            if candidate.exists():
                skill_source = candidate

        # Check Claude Code if not found
        if skill_source is None and detected.claude_code:
            candidate = detected.claude_code_paths.skills_dir / skill_name
            if candidate.exists():
                skill_source = candidate

        # Fallback: check default OpenCode path even if not installed
        if skill_source is None:
            candidate = detector._opencode_paths.skills_dir / skill_name
            if candidate.exists():
                skill_source = candidate

    if skill_source is None or not skill_source.exists():
        if not quiet:
            console.print(
                f"[red]Skill '{skill_name}' not found in any skills directory[/red]"
            )
            console.print("[dim]Searched:[/dim]")
            console.print(f"[dim]  - {detector._opencode_paths.skills_dir}[/dim]")
            console.print(f"[dim]  - {detector._claude_code_paths.skills_dir}[/dim]")
        return SkillResult.NOT_FOUND, None

    # Validate skill
    if not _validate_skill(skill_source, quiet=quiet):
        return SkillResult.ERROR, None

    # Parse skill metadata
    frontmatter = _parse_skill_frontmatter(skill_source)
    skill_description = frontmatter.get("description", "No description provided")

    if not quiet:
        console.print(f"[cyan]Extracting skill: {skill_name}...[/cyan]")

    # Create branch name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"skill/{skill_name}-{timestamp}"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Clone the skills repo (shallow)
            skills_repo = get_current_skills_repo()
            if not quiet:
                console.print("[dim]Cloning skills repository...[/dim]")
            subprocess.run(
                ["gh", "repo", "clone", skills_repo, tmpdir, "--", "--depth=1"],
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
            if not quiet:
                console.print(f"[dim]Copied skill to {SKILLS_DIR}/{skill_name}/[/dim]")

            # Update or create skills.json registry
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
                "description": _truncate_description(skill_description, 200),
                "version": frontmatter.get("version", "0.1.0"),
                "author": _get_github_username(),
                "tags": [],  # Can be expanded later
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
            if not quiet:
                console.print("[dim]Pushing to remote...[/dim]")
            subprocess.run(
                ["git", "-C", tmpdir, "push", "-u", "origin", branch_name],
                capture_output=True,
                check=True,
            )

            # Create PR
            if not quiet:
                console.print("[dim]Creating pull request...[/dim]")
            pr_body = f"""## New Skill: {skill_name}

{skill_description}

### Files Added
- `{SKILLS_DIR}/{skill_name}/SKILL.md`
"""
            # List additional files
            for item in skill_dest.rglob("*"):
                if item.is_file() and item.name != "SKILL.md":
                    rel_path = item.relative_to(skill_dest)
                    pr_body += f"- `{SKILLS_DIR}/{skill_name}/{rel_path}`\n"

            pr_body += """
---
_Extracted via ContextHarness skill extractor_
"""

            pr_result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    skills_repo,
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

            if not quiet:
                console.print(f"\n[green]✅ Pull request created successfully![/green]")
                console.print(f"[cyan]{pr_url}[/cyan]")
                console.print(
                    "\n[dim]Review and merge the PR to publish your skill.[/dim]"
                )

            return SkillResult.SUCCESS, pr_url

    except subprocess.CalledProcessError as e:
        error_msg = (
            getattr(e, "stderr", None) or getattr(e, "output", None) or "Unknown error"
        )
        if isinstance(error_msg, bytes):
            error_msg = error_msg.decode("utf-8", errors="replace")
        if not quiet:
            console.print(f"[red]Error during extraction: {error_msg}[/red]")
        return SkillResult.ERROR, None


@dataclass
class LocalSkillInfo:
    """Information about a locally installed skill."""

    name: str
    description: str
    path: Path
    version: Optional[str] = None
    is_valid: bool = True


def list_local_skills(
    source_path: str = ".",
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> List[LocalSkillInfo]:
    """List skills installed locally.

    Args:
        source_path: Directory to search for skills (default: current directory)
        quiet: If True, suppress output messages
        tool_target: Which tool's skills to list:
            - "opencode": Only .opencode/skill/
            - "claude-code": Only .claude/skills/
            - "both": Both directories
            - None: Auto-detect, listing from all installed tools

    Returns:
        List of LocalSkillInfo objects
    """
    source = Path(source_path).resolve()
    detector = ToolDetector(source)

    # Determine which directories to search
    if tool_target:
        skills_dirs = detector.get_skills_dirs(tool_target)
    else:
        # Auto-detect: search all installed tool directories
        detected = detector.detect()
        skills_dirs = []
        if detected.opencode:
            skills_dirs.append(detected.opencode_paths.skills_dir)
        if detected.claude_code:
            skills_dirs.append(detected.claude_code_paths.skills_dir)

        # If no tools detected, check default OpenCode path
        if not skills_dirs:
            skills_dirs = [detector._opencode_paths.skills_dir]

    # Check if any skills directories exist
    existing_dirs = [d for d in skills_dirs if d.exists()]

    if not existing_dirs:
        if not quiet:
            console.print("[yellow]No skills directory found.[/yellow]")
            for skills_dir in skills_dirs:
                console.print(f"[dim]Checked: {skills_dir}[/dim]")
            console.print()
            console.print(
                "[dim]Run 'context-harness init' to initialize ContextHarness.[/dim]"
            )
        return []

    skills: List[LocalSkillInfo] = []
    seen_names: set[str] = set()  # Avoid duplicates when both tools have same skill

    # Iterate over all skills directories
    for skills_dir in existing_dirs:
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name

            # Skip if we've already seen this skill (handles both-tool scenario)
            if skill_name in seen_names:
                continue
            seen_names.add(skill_name)

            skill_md = skill_dir / "SKILL.md"

            if not skill_md.exists():
                # Skill directory exists but no SKILL.md - mark as invalid
                skills.append(
                    LocalSkillInfo(
                        name=skill_name,
                        description="(missing SKILL.md)",
                        path=skill_dir,
                        is_valid=False,
                    )
                )
                continue

            # Parse frontmatter for description
            try:
                frontmatter = _parse_skill_frontmatter(skill_dir)
            except Exception as exc:
                # Skill has a SKILL.md but it could not be read or parsed
                skills.append(
                    LocalSkillInfo(
                        name=skill_name,
                        description=f"(error reading SKILL.md: {exc})",
                        path=skill_dir,
                        is_valid=False,
                    )
                )
                continue

            description = frontmatter.get("description", "No description")
            version = frontmatter.get("version")

            skills.append(
                LocalSkillInfo(
                    name=skill_name,
                    description=description,
                    path=skill_dir,
                    version=version,
                    is_valid=True,
                )
            )

    if not quiet:
        if not skills:
            console.print("[dim]No skills found in skills directories[/dim]")
            for skills_dir in existing_dirs:
                console.print(f"[dim]Checked: {skills_dir}[/dim]")
            console.print()
            console.print(
                "[dim]Create a skill with the skill-creator or install one from the repository.[/dim]"
            )
        else:
            table = Table(title="Local Skills")
            table.add_column("Name", style="cyan")
            table.add_column("Description")
            table.add_column("Version", style="green")
            table.add_column("Status", style="dim")

            for skill in skills:
                status = "✓" if skill.is_valid else "⚠ invalid"
                table.add_row(
                    skill.name,
                    _truncate_description(skill.description, 50),
                    skill.version or "-",
                    status,
                )

            console.print(table)
            console.print()
            console.print(
                "[dim]Extract a skill to share: "
                "[cyan]context-harness skill extract <name>[/cyan][/dim]"
            )

    return skills


def _truncate_description(text: str, max_length: int) -> str:
    """Truncate description at word boundary with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text

    # Find the last space before max_length to avoid breaking mid-word
    truncated = text[: max_length - 3]  # Leave room for "..."
    last_space = truncated.rfind(" ")

    if last_space > max_length // 2:  # Only use space if it's reasonably far in
        truncated = truncated[:last_space]

    return truncated + "..."


def _get_github_username() -> str:
    """Get the current GitHub username.

    Returns:
        GitHub username or descriptive placeholder
    """
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


def check_updates(
    skill_name: Optional[str] = None,
    source_path: str = ".",
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> tuple[SkillResult, Optional[List[Any]]]:
    """Check for available skill updates.

    Args:
        skill_name: Specific skill to check, or None to check all installed skills
        source_path: Directory containing local skills
        quiet: If True, suppress output messages
        tool_target: Which tool directory to search

    Returns:
        Tuple of (SkillResult, list of VersionComparison dicts or None)
    """
    from pathlib import Path as _Path
    from context_harness.services.skill_service import SkillService
    from context_harness.primitives import Success, Failure

    service = SkillService()
    project_path = _Path(source_path).resolve()

    if skill_name is not None:
        result = service.check_skill_updates(skill_name, project_path, tool_target)
        if isinstance(result, Failure):
            if not quiet:
                console.print(
                    f"[red]Error checking updates for '{skill_name}': {result.error}[/red]"
                )
            return SkillResult.ERROR, None
        comparisons = [result.value]
    else:
        result = service.list_outdated_skills(project_path, tool_target)
        if isinstance(result, Failure):
            if not quiet:
                console.print(f"[red]Error checking for updates: {result.error}[/red]")
            return SkillResult.ERROR, None
        comparisons = result.value

    if not quiet:
        if not comparisons:
            console.print("[green]✅ All skills are up to date.[/green]")
        else:
            table = Table(title="Skill Updates Available")
            table.add_column("Name", style="cyan")
            table.add_column("Installed", style="dim")
            table.add_column("Available", style="green")
            table.add_column("Status", style="yellow")

            for comp in comparisons:
                local_v = comp.local_version or "-"
                remote_v = comp.remote_version or "-"
                if comp.status == VersionStatus.INCOMPATIBLE:
                    status_str = f"[red]incompatible (needs CH >= {comp.context_harness_min})[/red]"
                elif comp.status == VersionStatus.UPGRADE_AVAILABLE:
                    status_str = "[yellow]upgrade available[/yellow]"
                else:
                    status_str = str(comp.status.value)
                table.add_row(comp.skill_name, local_v, remote_v, status_str)

            console.print(table)

    return SkillResult.SUCCESS, comparisons


def upgrade_skill(
    skill_name: str,
    source_path: str = ".",
    force_compatibility: bool = False,
    quiet: bool = False,
    tool_target: Optional[ToolTarget] = None,
) -> SkillResult:
    """Upgrade a skill to the latest version.

    Args:
        skill_name: Name of the skill to upgrade
        source_path: Directory containing local skills
        force_compatibility: If True, bypass compatibility checks
        quiet: If True, suppress output messages
        tool_target: Which tool directory to upgrade

    Returns:
        SkillResult indicating success or failure
    """
    from pathlib import Path as _Path
    from context_harness.services.skill_service import SkillService
    from context_harness.primitives import Success, Failure, ErrorCode

    service = SkillService()
    project_path = _Path(source_path).resolve()

    if not quiet:
        console.print(f"[cyan]Upgrading skill: {skill_name}...[/cyan]")

    result = service.upgrade_skill(
        skill_name=skill_name,
        project_path=project_path,
        force_compatibility=force_compatibility,
        tool_target=tool_target,
    )

    if isinstance(result, Success):
        if not quiet:
            console.print(f"\n[green]✅ {result.message}[/green]")
        return SkillResult.SUCCESS

    if isinstance(result, Failure):
        if result.code == ErrorCode.SKILL_NO_UPGRADE_AVAILABLE:
            if not quiet:
                console.print(f"[green]✅ {result.error}[/green]")
            return SkillResult.SUCCESS  # Not an error — already up to date
        elif result.code == ErrorCode.SKILL_INCOMPATIBLE_VERSION:
            if not quiet:
                console.print(f"[red]❌ {result.error}[/red]")
                console.print("[dim]Use --force to bypass compatibility check.[/dim]")
            return SkillResult.ERROR
        elif result.code == ErrorCode.SKILL_NOT_FOUND:
            if not quiet:
                console.print(f"[red]Skill '{skill_name}' not found.[/red]")
            return SkillResult.NOT_FOUND
        elif result.code in (ErrorCode.AUTH_REQUIRED, ErrorCode.PERMISSION_DENIED):
            if not quiet:
                console.print(f"[red]Authentication error: {result.error}[/red]")
            return SkillResult.AUTH_ERROR
        else:
            if not quiet:
                console.print(f"[red]Error upgrading skill: {result.error}[/red]")
            return SkillResult.ERROR

    return SkillResult.ERROR
