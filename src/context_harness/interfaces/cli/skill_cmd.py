"""Skill commands for ContextHarness CLI.

Handles the `context-harness skill` command group for skill management.
"""

from __future__ import annotations

from typing import Optional, Tuple

import click

from context_harness.skills import (
    list_skills,
    list_local_skills,
    get_skill_info,
    install_skill,
    extract_skill,
    check_updates,
    upgrade_skill,
    SkillResult,
)
from context_harness.completion import (
    complete_skill_names,
    interactive_skill_picker,
    interactive_local_skill_picker,
)
from context_harness.interfaces.cli.formatters import (
    console,
    print_header,
    print_error,
    print_info,
    print_bold,
)


@click.group("skill")
def skill_group() -> None:
    """Manage ContextHarness skills.

    List, install, and extract skills from the central skills repository.
    Skills extend agent capabilities with specialized knowledge and workflows.
    """
    pass


@skill_group.command("list")
@click.option(
    "--tags",
    "-t",
    multiple=True,
    help="Filter skills by tag (can be specified multiple times).",
)
def skill_list(tags: Tuple[str, ...]) -> None:
    """List available skills from the central repository.

    Shows all skills available for installation, with optional tag filtering.

    Examples:

        context-harness skill list

        context-harness skill list --tags react

        context-harness skill list --tags frontend --tags forms
    """
    print_header("Skills")

    tags_list = list(tags) if tags else None
    skills = list_skills(tags=tags_list)

    if not skills:
        print_info("No skills found.")
        console.print()
        print_info("The skills repository may be empty or inaccessible.")


@skill_group.command("list-local")
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing .opencode/skill/ (default: current directory).",
)
def skill_list_local(source: str) -> None:
    """List skills installed in your local project.

    Discovers all skills in the .opencode/skill/ directory and displays
    their name, description, and version. Useful for finding skills to extract.

    Examples:

        context-harness skill list-local

        context-harness skill list-local --source ./my-project
    """
    print_header("Local Skills")
    list_local_skills(source_path=source)


@skill_group.command("info")
@click.argument("skill_name")
def skill_info_cmd(skill_name: str) -> None:
    """Show detailed information about a skill.

    Displays the skill's description, version, author, and requirements.

    Examples:

        context-harness skill info react-forms

        context-harness skill info django-auth
    """
    console.print()
    skill_data = get_skill_info(skill_name)
    if skill_data is None:
        raise SystemExit(1)
    console.print()


@skill_group.command("install")
@click.argument(
    "skill_name", required=False, default=None, shell_complete=complete_skill_names
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(),
    help="Target directory for installation (default: current directory).",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing skill if already installed.",
)
def skill_install_cmd(skill_name: Optional[str], target: str, force: bool) -> None:
    """Install a skill from the central repository.

    Downloads and installs the specified skill to .opencode/skill/ in the
    target directory.

    If no skill name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a skill.

    Examples:

        context-harness skill install

        context-harness skill install react-forms

        context-harness skill install django-auth --target ./my-project

        context-harness skill install react-forms --force
    """
    print_header("Skill Installer")

    # If no skill name provided, show interactive picker
    if skill_name is None:
        skill_name = interactive_skill_picker(console)
        if skill_name is None:
            # User cancelled or no skills available
            raise SystemExit(0)
        console.print()

    result = install_skill(skill_name, target=target, force=force)

    if result == SkillResult.SUCCESS:
        console.print()
        print_bold("Skill installed!")
        console.print()
        print_info("The skill is now available in your project.")
        print_info("It will be automatically loaded when relevant.")
    elif result == SkillResult.ALREADY_EXISTS:
        raise SystemExit(0)  # Not an error, just informational
    elif result == SkillResult.NOT_FOUND:
        console.print()
        print_error(f"Skill '{skill_name}' not found.")
        print_info("Use 'context-harness skill list' to see available skills.")
        raise SystemExit(1)
    elif result in (SkillResult.AUTH_ERROR, SkillResult.ERROR):
        console.print()
        print_error("Failed to install skill.")
        raise SystemExit(1)


@skill_group.command("extract")
@click.argument("skill_name", required=False, default=None)
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing .opencode/skill/ (default: current directory).",
)
def skill_extract_cmd(skill_name: Optional[str], source: str) -> None:
    """Extract a local skill and create a PR to the central repository.

    Takes a skill from your local .opencode/skill/ directory and creates
    a pull request to add it to the central skills repository for review.

    If no skill name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a skill.

    Examples:

        context-harness skill extract

        context-harness skill extract my-custom-skill

        context-harness skill extract react-auth --source ./my-project
    """
    print_header("Skill Extractor")

    # If no skill name provided, show interactive picker
    if skill_name is None:
        skill_name = interactive_local_skill_picker(console, source_path=source)
        if skill_name is None:
            # User cancelled or no skills available
            raise SystemExit(0)
        console.print()

    result, pr_url = extract_skill(skill_name, source_path=source)

    if result == SkillResult.SUCCESS:
        console.print()
        print_bold("Pull request created!")
        console.print()
        print_info("Once merged, the skill will be available to all users.")
    elif result == SkillResult.NOT_FOUND:
        console.print()
        print_error(f"Skill '{skill_name}' not found locally.")
        print_info(f"Expected location: {source}/.opencode/skill/{skill_name}/")
        raise SystemExit(1)
    elif result == SkillResult.AUTH_ERROR:
        console.print()
        print_error("Authentication failed.")
        print_info("Make sure you're logged in with 'gh auth login'.")
        raise SystemExit(1)
    elif result == SkillResult.ERROR:
        console.print()
        print_error("Failed to extract skill.")
        raise SystemExit(1)


@skill_group.command("outdated")
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing local skills (default: current directory).",
)
def skill_outdated_cmd(source: str) -> None:
    """Show skills with available updates.

    Compares locally installed skills against the remote registry and
    lists any skills that have a newer version available.

    Examples:

        context-harness skill outdated

        context-harness skill outdated --source ./my-project
    """
    print_header("Skill Updates")

    result, comparisons = check_updates(source_path=source)

    if result != SkillResult.SUCCESS:
        console.print()
        print_error("Failed to check for updates.")
        raise SystemExit(1)

    if comparisons:
        console.print()
        print_info(
            f"Found {len(comparisons)} skill(s) with updates available. "
            "Run 'context-harness skill upgrade <name>' to upgrade."
        )
    else:
        console.print()
        console.print("[green]✅ All skills are up to date.[/green]")


@skill_group.command("upgrade")
@click.argument("skill_name", required=False, default=None)
@click.option(
    "--source",
    "-s",
    default=".",
    type=click.Path(exists=True),
    help="Source directory containing local skills (default: current directory).",
)
@click.option(
    "--all",
    "upgrade_all",
    is_flag=True,
    help="Upgrade all outdated skills.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Bypass compatibility checks.",
)
def skill_upgrade_cmd(
    skill_name: Optional[str], source: str, upgrade_all: bool, force: bool
) -> None:
    """Upgrade a skill to the latest version.

    Downloads and installs the latest version of the specified skill.
    Use --all to upgrade all outdated skills at once.

    If the skill requires a newer version of ContextHarness, you will
    be warned. Use --force to bypass the compatibility check.

    Examples:

        context-harness skill upgrade react-forms

        context-harness skill upgrade --all

        context-harness skill upgrade react-forms --force
    """
    print_header("Skill Upgrade")

    if not skill_name and not upgrade_all:
        console.print()
        print_error("Specify a skill name or use --all to upgrade all outdated skills.")
        print_info("Use 'context-harness skill outdated' to see what's available.")
        raise SystemExit(1)

    if upgrade_all:
        # Check for all outdated skills and upgrade them
        check_result, comparisons = check_updates(source_path=source, quiet=True)
        if check_result != SkillResult.SUCCESS or comparisons is None:
            console.print()
            print_error("Failed to check for updates.")
            raise SystemExit(1)

        if not comparisons:
            console.print()
            console.print("[green]✅ All skills are already up to date.[/green]")
            return

        console.print()
        print_info(f"Upgrading {len(comparisons)} skill(s)...")
        console.print()

        had_error = False
        for comp in comparisons:
            result = upgrade_skill(
                comp.skill_name,
                source_path=source,
                force_compatibility=force,
            )
            if result != SkillResult.SUCCESS:
                had_error = True

        if had_error:
            raise SystemExit(1)
    else:
        assert skill_name is not None  # guaranteed by the guard above
        result = upgrade_skill(
            skill_name,
            source_path=source,
            force_compatibility=force,
        )

        if result == SkillResult.SUCCESS:
            console.print()
            print_bold("Skill upgraded!")
        elif result == SkillResult.NOT_FOUND:
            console.print()
            print_error(f"Skill '{skill_name}' not found locally.")
            print_info(
                "Use 'context-harness skill list-local' to see installed skills."
            )
            raise SystemExit(1)
        elif result == SkillResult.AUTH_ERROR:
            console.print()
            print_error("Authentication failed.")
            print_info("Make sure you're logged in with 'gh auth login'.")
            raise SystemExit(1)
        elif result == SkillResult.ERROR:
            console.print()
            print_error("Failed to upgrade skill.")
            raise SystemExit(1)
