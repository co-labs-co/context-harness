"""Framework file installer for ContextHarness."""

import shutil
import tempfile
import urllib.request
import urllib.error
from enum import Enum
from pathlib import Path

from rich.console import Console

console = Console()

# GitHub repository info
GITHUB_REPO = "cmtzco/context-harness"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}"


class InstallResult(Enum):
    """Result of an installation attempt."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    ERROR = "error"


def get_templates_dir() -> Path:
    """Get the path to the bundled templates directory."""
    return Path(__file__).parent / "templates"


# Required template files for a valid installation
REQUIRED_TEMPLATE_FILES = [
    ".context-harness/README.md",
    ".context-harness/templates/session-template.md",
    ".opencode/agent/context-harness.md",
    ".opencode/agent/compaction-guide.md",
    ".opencode/agent/docs-subagent.md",
    ".opencode/agent/research-subagent.md",
]

# Optional RLM (Recursive Language Model) files - experimental feature
RLM_TEMPLATE_FILES = [
    ".context-harness/rlm-workspace/README.md",
    ".opencode/agent/rlm-orchestrator.md",
    ".opencode/agent/rlm-worker.md",
]


def validate_templates(templates_dir: Path, quiet: bool = False) -> list[str]:
    """Validate that all required template files exist.

    Args:
        templates_dir: Path to the templates directory
        quiet: If True, suppress output messages

    Returns:
        List of missing files (empty if all present)
    """
    missing = []
    for file_path in REQUIRED_TEMPLATE_FILES:
        if not (templates_dir / file_path).exists():
            missing.append(file_path)

    if missing and not quiet:
        console.print("[red]Error: Bundled templates are incomplete.[/red]")
        console.print("[red]Missing files:[/red]")
        for f in missing:
            console.print(f"[red]  - {f}[/red]")

    return missing


def install_framework(
    target: str, force: bool = False, quiet: bool = False
) -> InstallResult:
    """Install ContextHarness framework files to target directory.

    Args:
        target: Target directory path
        force: If True, overwrite existing files (preserves sessions/)
        quiet: If True, suppress output messages

    Returns:
        InstallResult indicating success or failure reason
    """
    target_path = Path(target).resolve()
    templates_dir = get_templates_dir()

    # Check if templates exist
    if not templates_dir.exists():
        if not quiet:
            console.print(
                f"[red]Error: Templates directory not found at {templates_dir}[/red]"
            )
        return InstallResult.ERROR

    # Validate template structure
    missing_files = validate_templates(templates_dir, quiet=quiet)
    if missing_files:
        return InstallResult.ERROR

    # Define target directories
    context_harness_target = target_path / ".context-harness"
    opencode_target = target_path / ".opencode"

    # Check for existing installation
    if not force:
        if context_harness_target.exists() or opencode_target.exists():
            return InstallResult.ALREADY_EXISTS

    try:
        # Copy .context-harness directory (preserving sessions/)
        context_harness_source = templates_dir / ".context-harness"
        if context_harness_source.exists():
            if not quiet:
                console.print("[dim]Updating .context-harness/ ...[/dim]")
            _copy_preserving_sessions(
                context_harness_source, context_harness_target, force
            )

        # Copy .opencode directory (full replacement is safe - no user data)
        opencode_source = templates_dir / ".opencode"
        if opencode_source.exists():
            if not quiet:
                console.print("[dim]Updating .opencode/agent/ ...[/dim]")
            if opencode_target.exists() and force:
                shutil.rmtree(opencode_target)
            if not opencode_target.exists():
                shutil.copytree(opencode_source, opencode_target)

        if not quiet:
            console.print()
            _print_created_files(target_path)

        return InstallResult.SUCCESS

    except PermissionError:
        if not quiet:
            console.print(
                f"[red]Error: Permission denied writing to {target_path}[/red]"
            )
        return InstallResult.ERROR
    except Exception as e:
        if not quiet:
            console.print(f"[red]Error: {e}[/red]")
        return InstallResult.ERROR


def _copy_preserving_sessions(source: Path, target: Path, force: bool) -> None:
    """Copy .context-harness directory while preserving sessions/.

    Args:
        source: Source template directory
        target: Target installation directory
        force: Whether to overwrite existing files
    """
    sessions_dir = target / "sessions"
    sessions_backup = None

    # Backup sessions if they exist (backup OUTSIDE target directory)
    if sessions_dir.exists():
        sessions_backup = target.parent / ".sessions.backup"
        if sessions_backup.exists():
            shutil.rmtree(sessions_backup)
        shutil.move(str(sessions_dir), str(sessions_backup))

    # Remove existing .context-harness (except sessions which we backed up)
    if target.exists() and force:
        shutil.rmtree(target)

    # Copy fresh template
    if not target.exists():
        shutil.copytree(source, target)

    # Restore sessions
    if sessions_backup and sessions_backup.exists():
        # Remove empty sessions dir from template if it exists
        new_sessions_dir = target / "sessions"
        if new_sessions_dir.exists():
            shutil.rmtree(new_sessions_dir)
        shutil.move(str(sessions_backup), str(new_sessions_dir))


def _print_created_files(target_path: Path) -> None:
    """Print a tree of created files."""
    console.print("[bold]Created files:[/bold]")

    # List .context-harness files
    context_harness_dir = target_path / ".context-harness"
    if context_harness_dir.exists():
        console.print("  📁 .context-harness/")
        for item in sorted(context_harness_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(context_harness_dir)
                console.print(f"     └── {rel_path}")

    # List .opencode files
    opencode_dir = target_path / ".opencode"
    if opencode_dir.exists():
        console.print("  📁 .opencode/")
        for item in sorted(opencode_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(opencode_dir)
                console.print(f"     └── {rel_path}")


def verify_installation(target: str) -> bool:
    """Verify that ContextHarness was installed correctly.

    Args:
        target: Target directory path

    Returns:
        True if all expected files exist, False otherwise
    """
    target_path = Path(target).resolve()

    expected_files = [
        ".context-harness/README.md",
        ".context-harness/templates/session-template.md",
        ".opencode/agent/context-harness.md",
        ".opencode/agent/compaction-guide.md",
        ".opencode/agent/docs-subagent.md",
        ".opencode/agent/research-subagent.md",
    ]

    for file_path in expected_files:
        if not (target_path / file_path).exists():
            return False

    return True


# Files to fetch from GitHub when using --ref
GITHUB_TEMPLATE_FILES = [
    # Core context-harness files
    "src/context_harness/templates/.context-harness/README.md",
    "src/context_harness/templates/.context-harness/templates/session-template.md",
    # Core agent files
    "src/context_harness/templates/.opencode/agent/context-harness.md",
    "src/context_harness/templates/.opencode/agent/compaction-guide.md",
    "src/context_harness/templates/.opencode/agent/docs-subagent.md",
    "src/context_harness/templates/.opencode/agent/research-subagent.md",
    # RLM agent files (experimental)
    "src/context_harness/templates/.opencode/agent/rlm-orchestrator.md",
    "src/context_harness/templates/.opencode/agent/rlm-worker.md",
    "src/context_harness/templates/.context-harness/rlm-workspace/README.md",
]


def _fetch_github_file(ref: str, file_path: str) -> str | None:
    """Fetch a single file from GitHub.

    Args:
        ref: Git ref (branch, tag, or commit)
        file_path: Path to file in repository

    Returns:
        File contents as string, or None if fetch failed
    """
    url = f"{GITHUB_RAW_BASE}/{ref}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # File doesn't exist in this ref
        raise
    except urllib.error.URLError:
        return None


def install_from_github(
    target: str, ref: str, force: bool = False, quiet: bool = False
) -> InstallResult:
    """Install ContextHarness framework files from a specific GitHub ref.

    Args:
        target: Target directory path
        ref: Git ref (branch, tag, or commit)
        force: If True, overwrite existing files (preserves sessions/)
        quiet: If True, suppress output messages

    Returns:
        InstallResult indicating success or failure reason
    """
    target_path = Path(target).resolve()

    # Define target directories
    context_harness_target = target_path / ".context-harness"
    opencode_target = target_path / ".opencode"

    # Check for existing installation
    if not force:
        if context_harness_target.exists() or opencode_target.exists():
            return InstallResult.ALREADY_EXISTS

    if not quiet:
        console.print(f"[dim]Fetching files from GitHub ref: {ref}[/dim]")

    # Backup sessions if they exist
    sessions_dir = context_harness_target / "sessions"
    sessions_backup = None
    if sessions_dir.exists():
        sessions_backup = target_path / ".sessions.backup"
        if sessions_backup.exists():
            shutil.rmtree(sessions_backup)
        shutil.move(str(sessions_dir), str(sessions_backup))

    # Remove existing directories if force
    if force:
        if context_harness_target.exists():
            shutil.rmtree(context_harness_target)
        if opencode_target.exists():
            shutil.rmtree(opencode_target)

    try:
        files_created = []
        files_skipped = []

        for github_path in GITHUB_TEMPLATE_FILES:
            # Convert GitHub path to local target path
            # src/context_harness/templates/.context-harness/... -> .context-harness/...
            local_path = github_path.replace("src/context_harness/templates/", "")
            target_file = target_path / local_path

            if not quiet:
                console.print(f"[dim]  Fetching {local_path}...[/dim]")

            content = _fetch_github_file(ref, github_path)
            if content is None:
                files_skipped.append(local_path)
                continue

            # Create parent directories
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            target_file.write_text(content)
            files_created.append(local_path)

        # Restore sessions
        if sessions_backup and sessions_backup.exists():
            new_sessions_dir = context_harness_target / "sessions"
            if new_sessions_dir.exists():
                shutil.rmtree(new_sessions_dir)
            shutil.move(str(sessions_backup), str(new_sessions_dir))

        if not quiet:
            console.print()
            console.print("[bold]Created files:[/bold]")
            for f in sorted(files_created):
                console.print(f"  └── {f}")
            if files_skipped:
                console.print()
                console.print("[dim]Skipped (not found in ref):[/dim]")
                for f in sorted(files_skipped):
                    console.print(f"  [dim]└── {f}[/dim]")

        # Check if we got the minimum required files
        required_count = len([f for f in files_created if "rlm" not in f])
        if required_count < 4:  # At least 4 core files
            if not quiet:
                console.print(
                    f"[red]Error: Only {required_count} core files found. "
                    f"Check if ref '{ref}' exists.[/red]"
                )
            return InstallResult.ERROR

        return InstallResult.SUCCESS

    except urllib.error.URLError as e:
        if not quiet:
            console.print(f"[red]Error: Network error fetching from GitHub: {e}[/red]")
        return InstallResult.ERROR
    except PermissionError:
        if not quiet:
            console.print(
                f"[red]Error: Permission denied writing to {target_path}[/red]"
            )
        return InstallResult.ERROR
    except Exception as e:
        if not quiet:
            console.print(f"[red]Error: {e}[/red]")
        return InstallResult.ERROR
