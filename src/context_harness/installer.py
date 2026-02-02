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


# Required template files for a valid installation
REQUIRED_TEMPLATE_FILES = [
    ".contextignore",
    ".context-harness/README.md",
    ".context-harness/templates/session-template.md",
    ".opencode/agent/context-harness.md",
    ".opencode/agent/compaction-guide.md",
    ".opencode/agent/contexts-subagent.md",
    ".opencode/agent/docs-subagent.md",
    ".opencode/agent/research-subagent.md",
    ".opencode/agent/baseline-discovery.md",
    ".opencode/agent/baseline-questions.md",
    ".opencode/agent/baseline-answers.md",
    ".opencode/command/ctx.md",
    ".opencode/command/compact.md",
    ".opencode/command/contexts.md",
    ".opencode/command/issue.md",
    ".opencode/command/pr.md",
    ".opencode/command/baseline.md",
    ".opencode/command/extract-skills.md",
    # Plugin: session-tracker (auto-updates SESSION.md before compaction)
    ".opencode/plugins/session-tracker.ts",
    ".opencode/plugins/README.md",
    # Skill: skill-creator (for deriving project-specific skills)
    ".opencode/skill/skill-creator/SKILL.md",
    ".opencode/skill/skill-creator/references/workflows.md",
    ".opencode/skill/skill-creator/references/output-patterns.md",
    ".opencode/skill/skill-creator/scripts/init_skill.py",
    ".opencode/skill/skill-creator/scripts/package_skill.py",
    ".opencode/skill/skill-creator/scripts/quick_validate.py",
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

        # Copy .opencode directory (preserving user-created skills)
        opencode_source = templates_dir / ".opencode"
        if opencode_source.exists():
            if not quiet:
                console.print(
                    "[dim]Updating .opencode/agent/, .opencode/command/, and .opencode/skill/ ...[/dim]"
                )
            _copy_preserving_user_skills(opencode_source, opencode_target, force)

        # Copy .contextignore (only if doesn't exist - never overwrite user's config)
        contextignore_source = templates_dir / ".contextignore"
        contextignore_target = target_path / ".contextignore"
        if contextignore_source.exists():
            if not contextignore_target.exists():
                if not quiet:
                    console.print("[dim]Creating .contextignore ...[/dim]")
                shutil.copy2(str(contextignore_source), str(contextignore_target))
            elif not quiet:
                console.print("[dim]Preserving existing .contextignore[/dim]")

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


def _get_template_skill_names(source: Path) -> set[str]:
    """Get the names of skills included in the template.

    Args:
        source: Source template .opencode directory

    Returns:
        Set of skill directory names from the template
    """
    skill_dir = source / "skill"
    if not skill_dir.exists():
        return set()
    return {d.name for d in skill_dir.iterdir() if d.is_dir()}


def _copy_preserving_user_skills(source: Path, target: Path, force: bool) -> None:
    """Copy .opencode directory while preserving user-created skills.

    Template skills (like skill-creator) are updated, but user-created skills
    are preserved.

    Args:
        source: Source template directory
        target: Target installation directory
        force: Whether to overwrite existing files
    """
    skill_dir = target / "skill"
    template_skills = _get_template_skill_names(source)
    user_skills_backup = None

    # Backup user-created skills (skills not in template)
    if skill_dir.exists():
        user_skills = []
        for skill_path in skill_dir.iterdir():
            if skill_path.is_dir() and skill_path.name not in template_skills:
                user_skills.append(skill_path)

        if user_skills:
            user_skills_backup = target.parent / ".user_skills.backup"
            if user_skills_backup.exists():
                shutil.rmtree(user_skills_backup)
            user_skills_backup.mkdir()

            for skill_path in user_skills:
                shutil.move(str(skill_path), str(user_skills_backup / skill_path.name))

    # Remove existing .opencode and copy fresh template
    if target.exists() and force:
        shutil.rmtree(target)

    if not target.exists():
        shutil.copytree(source, target)

    # Restore user-created skills
    if user_skills_backup and user_skills_backup.exists():
        skill_dir = target / "skill"
        skill_dir.mkdir(parents=True, exist_ok=True)

        for skill_path in user_skills_backup.iterdir():
            if skill_path.is_dir():
                dest = skill_dir / skill_path.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(skill_path), str(dest))

        # Clean up backup directory
        shutil.rmtree(user_skills_backup)


def _print_created_files(target_path: Path) -> None:
    """Print a tree of created files."""
    console.print("[bold]Created files:[/bold]")

    # Show .contextignore at root
    contextignore = target_path / ".contextignore"
    if contextignore.exists():
        console.print("  📄 .contextignore")

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
        ".contextignore",
        ".context-harness/README.md",
        ".context-harness/templates/session-template.md",
        ".opencode/agent/context-harness.md",
        ".opencode/agent/compaction-guide.md",
        ".opencode/agent/contexts-subagent.md",
        ".opencode/agent/docs-subagent.md",
        ".opencode/agent/research-subagent.md",
        ".opencode/agent/baseline-discovery.md",
        ".opencode/agent/baseline-questions.md",
        ".opencode/agent/baseline-answers.md",
        ".opencode/command/ctx.md",
        ".opencode/command/compact.md",
        ".opencode/command/contexts.md",
        ".opencode/command/issue.md",
        ".opencode/command/pr.md",
        ".opencode/command/baseline.md",
        ".opencode/command/extract-skills.md",
        # Plugin: session-tracker
        ".opencode/plugins/session-tracker.ts",
        ".opencode/plugins/README.md",
        # Skill: skill-creator
        ".opencode/skill/skill-creator/SKILL.md",
        ".opencode/skill/skill-creator/references/workflows.md",
        ".opencode/skill/skill-creator/references/output-patterns.md",
        ".opencode/skill/skill-creator/scripts/init_skill.py",
        ".opencode/skill/skill-creator/scripts/package_skill.py",
        ".opencode/skill/skill-creator/scripts/quick_validate.py",
    ]

    for file_path in expected_files:
        if not (target_path / file_path).exists():
            return False

    return True
