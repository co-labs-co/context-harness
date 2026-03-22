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
    init_repo,
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
    print_success,
    print_warning,
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
@click.option(
    "--registry",
    "-r",
    default=None,
    help="Registry URL to install from (e.g., https://skills.example.com).",
)
def skill_install_cmd(
    skill_name: Optional[str], target: str, force: bool, registry: Optional[str]
) -> None:
    """Install a skill from the central repository.

    Downloads and installs the specified skill to .opencode/skill/ in the
    target directory.

    If no skill name is provided, an interactive picker will be shown
    with fuzzy search to help you find and select a skill.

    Use --registry to install from a specific HTTP registry without
    changing your global configuration.

    Examples:

        context-harness skill install

        context-harness skill install react-forms

        context-harness skill install django-auth --target ./my-project

        context-harness skill install react-forms --force

        context-harness skill install my-skill --registry https://skills.example.com
    """
    import os

    print_header("Skill Installer")

    # If --registry is provided, temporarily set the env var
    original_registry_url = os.environ.get("CONTEXT_HARNESS_REGISTRY_URL")
    if registry:
        os.environ["CONTEXT_HARNESS_REGISTRY_URL"] = registry

    try:
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
    finally:
        # Restore original env var
        if registry:
            if original_registry_url is None:
                os.environ.pop("CONTEXT_HARNESS_REGISTRY_URL", None)
            else:
                os.environ["CONTEXT_HARNESS_REGISTRY_URL"] = original_registry_url


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

        failed_skills: list[str] = []
        for comp in comparisons:
            result = upgrade_skill(
                comp.skill_name,
                source_path=source,
                force_compatibility=force,
            )
            if result != SkillResult.SUCCESS:
                failed_skills.append(comp.skill_name)

        if failed_skills:
            console.print()
            print_error(
                f"Failed to upgrade {len(failed_skills)} skill(s): "
                + ", ".join(failed_skills)
            )
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


@skill_group.command("init-repo")
@click.argument("name")
@click.option(
    "--private/--public",
    default=True,
    help="Repository visibility (default: private).",
)
@click.option(
    "--description",
    "-d",
    default=None,
    help="Repository description.",
)
@click.option(
    "--configure-user",
    is_flag=True,
    help="Set as default skills-repo in user config (~/.context-harness/config.json).",
)
@click.option(
    "--configure-project",
    is_flag=True,
    help="Set as default skills-repo in project config (opencode.json).",
)
def skill_init_repo_cmd(
    name: str,
    private: bool,
    description: Optional[str],
    configure_user: bool,
    configure_project: bool,
) -> None:
    """Initialize a new skills registry repository on GitHub.

    Creates a GitHub repository scaffolded with the standard skills
    registry structure (skills.json, skill directory, README). The
    repository is ready to use as a custom skills-repo immediately.

    NAME is the repository name. Use "owner/repo" format to create
    under an organization, or just "repo" for your personal account.

    Requires: GitHub CLI (gh) installed and authenticated.

    Examples:

        context-harness skill init-repo my-skills

        context-harness skill init-repo my-org/team-skills --public

        context-harness skill init-repo my-skills --configure-user

        context-harness skill init-repo my-org/skills -d "Team AI skills"
    """
    print_header("Skill Registry Initializer")

    result, repo_url = init_repo(
        name=name,
        private=private,
        description=description,
    )

    if result == SkillResult.SUCCESS:
        console.print()
        print_bold("Skills registry created!")
        console.print()

        # Derive owner/repo from URL for config commands (the URL always
        # contains the real owner, which may differ from `name` when the
        # user omits the org prefix).
        config_name = name
        if repo_url:
            # e.g. "https://github.com/cmtzco/my-test-skills" → "cmtzco/my-test-skills"
            stripped = repo_url.rstrip("/").removesuffix(".git")
            parts = stripped.split("/")
            if len(parts) >= 2 and "github.com" in repo_url:
                config_name = f"{parts[-2]}/{parts[-1]}"

        visibility_str = "private" if private else "public"
        print_info(f"Repository: {config_name} ({visibility_str})")
        if repo_url:
            print_info(f"URL: {repo_url}")

        # Auto-configure if requested
        configured = False
        if configure_user:
            _configure_skills_repo_user(config_name)
            configured = True
        if configure_project:
            _configure_skills_repo_project(config_name)
            configured = True

        if not configured:
            console.print()
            console.print("[dim]To use this as your default skills-repo:[/dim]")
            console.print(
                f"[dim]  context-harness config set skills-repo {config_name}        # this project[/dim]"
            )
            console.print(
                f"[dim]  context-harness config set skills-repo {config_name} --user  # all projects[/dim]"
            )

    elif result == SkillResult.ALREADY_EXISTS:
        console.print()
        print_warning(f"Repository '{name}' already exists.")
        print_info("Use this existing repository, or choose a different name.")
        raise SystemExit(0)
    elif result == SkillResult.AUTH_ERROR:
        console.print()
        print_error("Authentication failed.")
        print_info("Make sure GitHub CLI (gh) is installed and authenticated:")
        console.print("[dim]  gh auth login[/dim]")
        raise SystemExit(1)
    elif result == SkillResult.ERROR:
        console.print()
        print_error("Failed to create skills registry.")
        raise SystemExit(1)


def _configure_skills_repo_user(repo_name: str) -> None:
    """Configure the skills-repo in user config.

    Args:
        repo_name: Repository name (owner/repo format)
    """
    try:
        from context_harness.primitives import Failure
        from context_harness.primitives.config import (
            SkillsRegistryConfig,
            UserConfig,
        )
        from context_harness.services.user_config_service import UserConfigService

        service = UserConfigService()

        # Create new config with the skills registry set
        new_config = UserConfig(
            skills_registry=SkillsRegistryConfig(default=repo_name),
        )

        save_result = service.save(new_config)
        if isinstance(save_result, Failure):
            print_warning(f"Could not update user config: {save_result.error}")
            return

        print_success(f"User config updated: skills-repo = {repo_name}")
    except Exception as e:
        print_warning(f"Could not update user config: {e}")


def _configure_skills_repo_project(repo_name: str) -> None:
    """Configure the skills-repo in project config.

    Args:
        repo_name: Repository name (owner/repo format)
    """
    try:
        from pathlib import Path

        from context_harness.primitives import Failure
        from context_harness.primitives.config import (
            OpenCodeConfig,
            SkillsRegistryConfig,
        )
        from context_harness.services.config_service import ConfigService

        service = ConfigService()

        # Load or create config
        result = service.load_or_create()
        if isinstance(result, Failure):
            print_warning(f"Could not load project config: {result.error}")
            return

        config = result.value

        # Create new config with updated skills registry
        new_config = OpenCodeConfig(
            schema_version=config.schema_version,
            mcp=config.mcp,
            agents=config.agents,
            commands=config.commands,
            skills=config.skills,
            skills_registry=SkillsRegistryConfig(default=repo_name),
            project_context=config.project_context,
            raw_data=config.raw_data,
        )

        save_result = service.save(new_config)
        if isinstance(save_result, Failure):
            print_warning(f"Could not update project config: {save_result.error}")
            return

        print_success(f"Project config updated: skills-repo = {repo_name}")
    except Exception as e:
        print_warning(f"Could not update project config: {e}")


@skill_group.command("use-registry")
@click.argument("url")
@click.option(
    "--project",
    "-p",
    is_flag=True,
    help="Set for this project only (default: user-wide).",
)
def skill_use_registry_cmd(url: str, project: bool) -> None:
    """Configure the skills registry URL.

    Sets the registry URL for fetching skills. This is useful for
    organizations hosting their own HTTP-based skill registries.

    By default, sets the registry user-wide (~/.context-harness/config.json).
    Use --project to set it for the current project only.

    Examples:

        context-harness skill use-registry https://skills.example.com

        context-harness skill use-registry https://skills.internal.com --project

        context-harness skill use-registry https://github.com/myorg/skills
    """
    print_header("Configure Skills Registry")

    # Validate URL format
    if not url.startswith(("http://", "https://", "github.com")):
        # Treat as GitHub repo if no protocol
        if "/" in url and not url.startswith("/"):
            url = f"github.com/{url}" if not url.startswith("github.com") else url
        else:
            console.print()
            print_error(f"Invalid registry URL: {url}")
            print_info("Expected format: https://registry.example.com or owner/repo")
            raise SystemExit(1)

    # Determine if it's HTTP or GitHub
    is_http = url.startswith(("http://", "https://"))

    if project:
        _configure_registry_project(url, is_http)
    else:
        _configure_registry_user(url, is_http)


def _configure_registry_user(url: str, is_http: bool) -> None:
    """Configure registry URL in user config."""
    try:
        from context_harness.primitives import Failure
        from context_harness.primitives.config import (
            SkillsRegistryConfig,
            SkillsRegistryAuthConfig,
            UserConfig,
        )
        from context_harness.services.user_config_service import UserConfigService

        service = UserConfigService()

        # Build registry config
        if is_http:
            registry_config = SkillsRegistryConfig(
                type="http",
                url=url,
                auth=None,
                default="",
            )
        else:
            # GitHub repo
            repo = url.replace("github.com/", "").replace("https://github.com/", "")
            registry_config = SkillsRegistryConfig(default=repo)

        new_config = UserConfig(skills_registry=registry_config)

        save_result = service.save(new_config)
        if isinstance(save_result, Failure):
            print_error(f"Could not update user config: {save_result.error}")
            raise SystemExit(1)

        console.print()
        print_success("Registry configured!")
        console.print()
        if is_http:
            print_info(f"URL: {url}")
        else:
            repo = url.replace("github.com/", "").replace("https://github.com/", "")
            print_info(f"GitHub repo: {repo}")
        console.print()
        print_info("Run 'context-harness skill list' to see available skills.")

    except Exception as e:
        print_error(f"Failed to configure registry: {e}")
        raise SystemExit(1)


def _configure_registry_project(url: str, is_http: bool) -> None:
    """Configure registry URL in project config."""
    try:
        from pathlib import Path

        from context_harness.primitives import Failure
        from context_harness.primitives.config import (
            OpenCodeConfig,
            SkillsRegistryConfig,
        )
        from context_harness.services.config_service import ConfigService

        service = ConfigService()

        # Load or create config
        result = service.load_or_create()
        if isinstance(result, Failure):
            print_error(f"Could not load project config: {result.error}")
            raise SystemExit(1)

        config = result.value

        # Build registry config
        if is_http:
            registry_config = SkillsRegistryConfig(
                type="http",
                url=url,
                auth=None,
                default="",
            )
        else:
            repo = url.replace("github.com/", "").replace("https://github.com/", "")
            registry_config = SkillsRegistryConfig(default=repo)

        new_config = OpenCodeConfig(
            schema_version=config.schema_version,
            mcp=config.mcp,
            agents=config.agents,
            commands=config.commands,
            skills=config.skills,
            skills_registry=registry_config,
            project_context=config.project_context,
            raw_data=config.raw_data,
        )

        save_result = service.save(new_config)
        if isinstance(save_result, Failure):
            print_error(f"Could not update project config: {save_result.error}")
            raise SystemExit(1)

        console.print()
        print_success("Project registry configured!")
        console.print()
        if is_http:
            print_info(f"URL: {url}")
        else:
            repo = url.replace("github.com/", "").replace("https://github.com/", "")
            print_info(f"GitHub repo: {repo}")
        console.print()
        print_info("Run 'context-harness skill list' to see available skills.")

    except Exception as e:
        print_error(f"Failed to configure registry: {e}")
        raise SystemExit(1)
