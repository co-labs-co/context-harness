"""Framework file installer for ContextHarness."""

import shutil
from enum import Enum
from pathlib import Path
from typing import Literal

from rich.console import Console

console = Console()


class InstallResult(Enum):
    """Result of an installation attempt."""

    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    ERROR = "error"


# Target tool types
TargetType = Literal["opencode", "claude-code", "both"]


def get_templates_dir() -> Path:
    """Get the path to the bundled templates directory."""
    return Path(__file__).parent / "templates"


# Required template files for OpenCode installation
REQUIRED_OPENCODE_FILES = [
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
    ".opencode/skill/skill-creator/SKILL.md",
    ".opencode/skill/skill-creator/references/workflows.md",
    ".opencode/skill/skill-creator/references/output-patterns.md",
    ".opencode/skill/skill-creator/scripts/init_skill.py",
    ".opencode/skill/skill-creator/scripts/package_skill.py",
    ".opencode/skill/skill-creator/scripts/quick_validate.py",
    "opencode.json",
    "AGENTS.md",
]

# Required template files for Claude Code installation
REQUIRED_CLAUDE_FILES = [
    ".contextignore",
    ".context-harness/README.md",
    ".context-harness/templates/session-template.md",
    ".claude/agents/context-harness.md",
    ".claude/agents/compaction-guide.md",
    ".claude/agents/contexts-subagent.md",
    ".claude/agents/docs-subagent.md",
    ".claude/agents/research-subagent.md",
    ".claude/agents/baseline-discovery.md",
    ".claude/agents/baseline-questions.md",
    ".claude/agents/baseline-answers.md",
    ".claude/commands/ctx.md",
    ".claude/commands/compact.md",
    ".claude/commands/contexts.md",
    ".claude/commands/issue.md",
    ".claude/commands/pr.md",
    ".claude/commands/baseline.md",
    ".claude/commands/extract-skills.md",
    ".claude/skills/skill-creator/SKILL.md",
    ".claude/skills/skill-creator/references/workflows.md",
    ".claude/skills/skill-creator/references/output-patterns.md",
    ".mcp.json",
    "CLAUDE.md",
]

# Legacy alias for backward compatibility
REQUIRED_TEMPLATE_FILES = REQUIRED_OPENCODE_FILES


def validate_templates(
    templates_dir: Path, target: TargetType = "both", quiet: bool = False
) -> list[str]:
    """Validate that all required template files exist.

    Args:
        templates_dir: Path to the templates directory
        target: Which tool to validate templates for
        quiet: If True, suppress output messages

    Returns:
        List of missing files (empty if all present)
    """
    required_files = []

    if target in ("opencode", "both"):
        required_files.extend(REQUIRED_OPENCODE_FILES)

    if target in ("claude-code", "both"):
        required_files.extend(REQUIRED_CLAUDE_FILES)

    # Remove duplicates (e.g., .context-harness files appear in both)
    required_files = list(set(required_files))

    missing = []
    for file_path in required_files:
        if not (templates_dir / file_path).exists():
            missing.append(file_path)

    if missing and not quiet:
        console.print("[red]Error: Bundled templates are incomplete.[/red]")
        console.print("[red]Missing files:[/red]")
        for f in missing:
            console.print(f"[red]  - {f}[/red]")

    return missing


def install_framework(
    target: str,
    force: bool = False,
    quiet: bool = False,
    tool_target: TargetType = "both",
) -> InstallResult:
    """Install ContextHarness framework files to target directory.

    Args:
        target: Target directory path
        force: If True, overwrite existing files (preserves sessions/)
        quiet: If True, suppress output messages
        tool_target: Which tool(s) to install for: "opencode", "claude-code", or "both"

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

    # Validate template structure for requested target
    missing_files = validate_templates(templates_dir, target=tool_target, quiet=quiet)
    if missing_files:
        return InstallResult.ERROR

    # Define target directories
    context_harness_target = target_path / ".context-harness"
    opencode_target = target_path / ".opencode"
    claude_target = target_path / ".claude"

    # Check for existing installation (only if not forcing)
    if not force:
        existing = []
        if context_harness_target.exists():
            existing.append(".context-harness/")
        if opencode_target.exists():
            existing.append(".opencode/")
        if claude_target.exists():
            existing.append(".claude/")

        if existing:
            return InstallResult.ALREADY_EXISTS

    try:
        # Show upgrade message if force and adding new tool support
        if force and not quiet:
            _show_upgrade_message(target_path, tool_target)

        # Copy .context-harness directory (preserving sessions/) - shared by both tools
        context_harness_source = templates_dir / ".context-harness"
        if context_harness_source.exists():
            if not quiet:
                console.print("[dim]Updating .context-harness/ ...[/dim]")
            _copy_preserving_sessions(
                context_harness_source, context_harness_target, force
            )

        # Copy .opencode directory if requested
        if tool_target in ("opencode", "both"):
            opencode_source = templates_dir / ".opencode"
            if opencode_source.exists():
                if not quiet:
                    console.print("[dim]Updating .opencode/ ...[/dim]")
                _copy_preserving_user_content(
                    opencode_source, opencode_target, force, "skill"
                )

            # Copy opencode.json for OpenCode
            opencode_json_source = templates_dir / "opencode.json"
            opencode_json_target = target_path / "opencode.json"
            if opencode_json_source.exists():
                if not opencode_json_target.exists() or force:
                    if not quiet:
                        console.print("[dim]Creating opencode.json ...[/dim]")
                    shutil.copy2(str(opencode_json_source), str(opencode_json_target))
                elif not quiet:
                    console.print("[dim]Preserving existing opencode.json[/dim]")

            # Copy AGENTS.md
            agents_md_source = templates_dir / "AGENTS.md"
            agents_md_target = target_path / "AGENTS.md"
            if agents_md_source.exists():
                if not agents_md_target.exists():
                    if not quiet:
                        console.print("[dim]Creating AGENTS.md ...[/dim]")
                    shutil.copy2(str(agents_md_source), str(agents_md_target))
                elif not quiet:
                    console.print("[dim]Preserving existing AGENTS.md[/dim]")

        # Copy .claude directory if requested
        if tool_target in ("claude-code", "both"):
            claude_source = templates_dir / ".claude"
            if claude_source.exists():
                if not quiet:
                    console.print("[dim]Updating .claude/ ...[/dim]")
                _copy_preserving_user_content(
                    claude_source, claude_target, force, "skills"
                )

            # Copy .mcp.json for Claude Code
            mcp_source = templates_dir / ".mcp.json"
            mcp_target = target_path / ".mcp.json"
            if mcp_source.exists():
                if not mcp_target.exists() or force:
                    if not quiet:
                        console.print("[dim]Creating .mcp.json ...[/dim]")
                    shutil.copy2(str(mcp_source), str(mcp_target))
                elif not quiet:
                    console.print("[dim]Preserving existing .mcp.json[/dim]")

            # Copy CLAUDE.md
            claude_md_source = templates_dir / "CLAUDE.md"
            claude_md_target = target_path / "CLAUDE.md"
            if claude_md_source.exists():
                if not claude_md_target.exists():
                    if not quiet:
                        console.print("[dim]Creating CLAUDE.md ...[/dim]")
                    shutil.copy2(str(claude_md_source), str(claude_md_target))
                elif not quiet:
                    console.print("[dim]Preserving existing CLAUDE.md[/dim]")

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
            _print_created_files(target_path, tool_target)

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


def _show_upgrade_message(target_path: Path, tool_target: TargetType) -> None:
    """Show message about what will be created vs updated."""
    opencode_exists = (target_path / ".opencode").exists()
    claude_exists = (target_path / ".claude").exists()

    if tool_target == "both":
        console.print()
        console.print("[bold]Existing installation detected:[/bold]")
        if opencode_exists:
            console.print("  [green]✅[/green] .opencode/ (will be updated)")
        else:
            console.print("  [yellow]➕[/yellow] .opencode/ (will be created)")
        if claude_exists:
            console.print("  [green]✅[/green] .claude/ (will be updated)")
        else:
            console.print("  [yellow]➕[/yellow] .claude/ (will be created)")
        console.print()
        console.print("[dim]Upgrading to dual-tool support...[/dim]")
        console.print()


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


def _get_template_skill_names(source: Path, skill_dir_name: str) -> set[str]:
    """Get the names of skills included in the template.

    Args:
        source: Source template directory (.opencode or .claude)
        skill_dir_name: Name of the skill directory ("skill" for opencode, "skills" for claude)

    Returns:
        Set of skill directory names from the template
    """
    skill_dir = source / skill_dir_name
    if not skill_dir.exists():
        return set()
    return {d.name for d in skill_dir.iterdir() if d.is_dir()}


def _copy_preserving_user_content(
    source: Path, target: Path, force: bool, skill_dir_name: str
) -> None:
    """Copy tool directory while preserving user-created content.

    Template skills are updated, but user-created skills are preserved.
    Agents and commands are overwritten from the template.

    Args:
        source: Source template directory
        target: Target installation directory
        force: Whether to overwrite existing files
        skill_dir_name: Name of the skill directory ("skill" for opencode, "skills" for claude)
    """
    skill_dir = target / skill_dir_name
    template_skills = _get_template_skill_names(source, skill_dir_name)
    user_skills_backup = None

    # Backup user-created skills (skills not in template)
    if skill_dir.exists():
        user_skills = []
        for skill_path in skill_dir.iterdir():
            if skill_path.is_dir() and skill_path.name not in template_skills:
                user_skills.append(skill_path)

        if user_skills:
            user_skills_backup = target.parent / f".user_{skill_dir_name}.backup"
            if user_skills_backup.exists():
                shutil.rmtree(user_skills_backup)
            user_skills_backup.mkdir()

            for skill_path in user_skills:
                shutil.move(str(skill_path), str(user_skills_backup / skill_path.name))

    # Remove existing directory and copy fresh template
    if target.exists() and force:
        shutil.rmtree(target)

    if not target.exists():
        shutil.copytree(source, target)

    # Restore user-created skills
    if user_skills_backup and user_skills_backup.exists():
        skill_dir = target / skill_dir_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        for skill_path in user_skills_backup.iterdir():
            if skill_path.is_dir():
                dest = skill_dir / skill_path.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(skill_path), str(dest))

        # Clean up backup directory
        shutil.rmtree(user_skills_backup)


# Legacy function for backward compatibility
def _copy_preserving_user_skills(source: Path, target: Path, force: bool) -> None:
    """Legacy wrapper for _copy_preserving_user_content."""
    _copy_preserving_user_content(source, target, force, "skill")


def _print_created_files(target_path: Path, tool_target: TargetType = "both") -> None:
    """Print a tree of created files."""
    console.print("[bold]Created files:[/bold]")

    # Show root-level files
    contextignore = target_path / ".contextignore"
    if contextignore.exists():
        console.print("  📄 .contextignore")

    opencode_json = target_path / "opencode.json"
    if opencode_json.exists() and tool_target in ("opencode", "both"):
        console.print("  📄 opencode.json")

    agents_md = target_path / "AGENTS.md"
    if agents_md.exists() and tool_target in ("opencode", "both"):
        console.print("  📄 AGENTS.md")

    mcp_json = target_path / ".mcp.json"
    if mcp_json.exists() and tool_target in ("claude-code", "both"):
        console.print("  📄 .mcp.json")

    claude_md = target_path / "CLAUDE.md"
    if claude_md.exists() and tool_target in ("claude-code", "both"):
        console.print("  📄 CLAUDE.md")

    # List .context-harness files
    context_harness_dir = target_path / ".context-harness"
    if context_harness_dir.exists():
        console.print("  📁 .context-harness/")
        for item in sorted(context_harness_dir.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(context_harness_dir)
                console.print(f"     └── {rel_path}")

    # List .opencode files
    if tool_target in ("opencode", "both"):
        opencode_dir = target_path / ".opencode"
        if opencode_dir.exists():
            console.print("  📁 .opencode/")
            for item in sorted(opencode_dir.rglob("*")):
                if item.is_file():
                    rel_path = item.relative_to(opencode_dir)
                    console.print(f"     └── {rel_path}")

    # List .claude files
    if tool_target in ("claude-code", "both"):
        claude_dir = target_path / ".claude"
        if claude_dir.exists():
            console.print("  📁 .claude/")
            for item in sorted(claude_dir.rglob("*")):
                if item.is_file():
                    rel_path = item.relative_to(claude_dir)
                    console.print(f"     └── {rel_path}")


def verify_installation(target: str, tool_target: TargetType = "both") -> bool:
    """Verify that ContextHarness was installed correctly.

    Args:
        target: Target directory path
        tool_target: Which tool(s) to verify: "opencode", "claude-code", or "both"

    Returns:
        True if all expected files exist, False otherwise
    """
    target_path = Path(target).resolve()

    expected_files = []

    # Shared files (always expected)
    expected_files.extend(
        [
            ".contextignore",
            ".context-harness/README.md",
            ".context-harness/templates/session-template.md",
        ]
    )

    if tool_target in ("opencode", "both"):
        expected_files.extend(
            [
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
                ".opencode/skill/skill-creator/SKILL.md",
                ".opencode/skill/skill-creator/references/workflows.md",
                ".opencode/skill/skill-creator/references/output-patterns.md",
                ".opencode/skill/skill-creator/scripts/init_skill.py",
                ".opencode/skill/skill-creator/scripts/package_skill.py",
                ".opencode/skill/skill-creator/scripts/quick_validate.py",
                "opencode.json",
                "AGENTS.md",
            ]
        )

    if tool_target in ("claude-code", "both"):
        expected_files.extend(
            [
                ".claude/agents/context-harness.md",
                ".claude/agents/compaction-guide.md",
                ".claude/agents/contexts-subagent.md",
                ".claude/agents/docs-subagent.md",
                ".claude/agents/research-subagent.md",
                ".claude/agents/baseline-discovery.md",
                ".claude/agents/baseline-questions.md",
                ".claude/agents/baseline-answers.md",
                ".claude/commands/ctx.md",
                ".claude/commands/compact.md",
                ".claude/commands/contexts.md",
                ".claude/commands/issue.md",
                ".claude/commands/pr.md",
                ".claude/commands/baseline.md",
                ".claude/commands/extract-skills.md",
                ".claude/skills/skill-creator/SKILL.md",
                ".claude/skills/skill-creator/references/workflows.md",
                ".claude/skills/skill-creator/references/output-patterns.md",
                ".mcp.json",
                "CLAUDE.md",
            ]
        )

    for file_path in expected_files:
        if not (target_path / file_path).exists():
            return False

    return True
