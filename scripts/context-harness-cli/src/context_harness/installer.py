"""Framework file installer for ContextHarness."""

import shutil
from enum import Enum
from pathlib import Path

from rich.console import Console

console = Console()


class InstallResult(Enum):
    """Result of an installation attempt."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    ERROR = "error"


def get_templates_dir() -> Path:
    """Get the path to the bundled templates directory."""
    return Path(__file__).parent / "templates"


def install_framework(
    target: str, force: bool = False, quiet: bool = False
) -> InstallResult:
    """Install ContextHarness framework files to target directory.

    Args:
        target: Target directory path
        force: If True, overwrite existing files
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

    # Define target directories
    context_harness_target = target_path / ".context-harness"
    opencode_target = target_path / ".opencode"

    # Check for existing installation
    if not force:
        if context_harness_target.exists() or opencode_target.exists():
            return InstallResult.ALREADY_EXISTS

    try:
        # Copy .context-harness directory
        context_harness_source = templates_dir / ".context-harness"
        if context_harness_source.exists():
            if not quiet:
                console.print(f"[dim]Creating .context-harness/ ...[/dim]")
            if context_harness_target.exists() and force:
                shutil.rmtree(context_harness_target)
            shutil.copytree(context_harness_source, context_harness_target)

        # Copy .opencode directory
        opencode_source = templates_dir / ".opencode"
        if opencode_source.exists():
            if not quiet:
                console.print(f"[dim]Creating .opencode/agent/ ...[/dim]")
            if opencode_target.exists() and force:
                shutil.rmtree(opencode_target)
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
