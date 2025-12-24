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

console = Console()

# Central skills repository
SKILLS_REPO = "co-labs-co/context-harness-skills"
SKILLS_REGISTRY_PATH = "skills.json"
SKILLS_DIR = "skill"  # singular, matching OpenCode standard


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


def check_repo_access(repo: str = SKILLS_REPO, quiet: bool = False) -> bool:
    """Check if user has access to the skills repository.

    Args:
        repo: Repository in owner/name format
        quiet: If True, suppress output messages

    Returns:
        True if user has access, False otherwise
    """
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

    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{SKILLS_REPO}/contents/{SKILLS_REGISTRY_PATH}",
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
) -> SkillResult:
    """Install a skill from the central repository.

    Args:
        skill_name: Name of the skill to install
        target: Target directory (default: current directory)
        force: If True, overwrite existing skill
        quiet: If True, suppress output messages

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
    skill_dest = target_path / ".opencode" / "skill" / skill_name

    # Check if already exists
    if skill_dest.exists() and not force:
        if not quiet:
            console.print(
                f"[yellow]Skill '{skill_name}' already installed at {skill_dest}[/yellow]"
            )
            console.print("[dim]Use --force to overwrite.[/dim]")
        return SkillResult.ALREADY_EXISTS

    # Remove existing if force
    if skill_dest.exists() and force:
        shutil.rmtree(skill_dest)

    if not quiet:
        console.print(f"[cyan]Installing skill: {skill_name}...[/cyan]")

    # Fetch skill files
    if not _fetch_directory_recursive(SKILLS_REPO, skill.path, skill_dest, quiet):
        if not quiet:
            console.print(f"[red]Failed to install skill '{skill_name}'.[/red]")
        return SkillResult.ERROR

    if not quiet:
        console.print(
            f"\n[green]✅ Skill '{skill_name}' installed successfully![/green]"
        )
        console.print(f"[dim]Location: {skill_dest}[/dim]")

    return SkillResult.SUCCESS


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
) -> tuple[SkillResult, Optional[str]]:
    """Extract a local skill and create a PR to the central repository.

    Args:
        skill_name: Name of the skill to extract
        source_path: Source directory containing .opencode/skill/
        quiet: If True, suppress output messages

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
    skill_source = source / ".opencode" / "skill" / skill_name

    if not skill_source.exists():
        if not quiet:
            console.print(
                f"[red]Skill '{skill_name}' not found at {skill_source}[/red]"
            )
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
            if not quiet:
                console.print("[dim]Cloning skills repository...[/dim]")
            subprocess.run(
                ["gh", "repo", "clone", SKILLS_REPO, tmpdir, "--", "--depth=1"],
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
                    SKILLS_REPO,
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
) -> List[LocalSkillInfo]:
    """List skills installed in the local .opencode/skill/ directory.

    Args:
        source_path: Directory containing .opencode/skill/ (default: current directory)
        quiet: If True, suppress output messages

    Returns:
        List of LocalSkillInfo objects
    """
    source = Path(source_path).resolve()
    skills_dir = source / ".opencode" / "skill"

    if not skills_dir.exists():
        if not quiet:
            console.print("[yellow]No skills directory found.[/yellow]")
            console.print(f"[dim]Expected location: {skills_dir}[/dim]")
            console.print()
            console.print(
                "[dim]Run 'context-harness init' to initialize ContextHarness.[/dim]"
            )
        return []

    skills: List[LocalSkillInfo] = []

    # Iterate over subdirectories in .opencode/skill/
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
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
            console.print("[dim]No skills found in .opencode/skill/[/dim]")
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
