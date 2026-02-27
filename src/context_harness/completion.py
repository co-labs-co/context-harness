"""Shell completion support for ContextHarness CLI.

This module provides tab completion and fuzzy finding for skill names
when using the `ch skill install` command.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from click import Context, Parameter
from click.shell_completion import CompletionItem

if TYPE_CHECKING:
    from context_harness.skills import SkillInfo

# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "context-harness"
SKILLS_CACHE_FILE = CACHE_DIR / "skills-cache.json"
CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_skills() -> Optional[List[dict]]:
    """Get skills from cache if valid.

    Returns:
        List of skill dicts if cache is valid, None otherwise
    """
    if not SKILLS_CACHE_FILE.exists():
        return None

    try:
        cache_data = json.loads(SKILLS_CACHE_FILE.read_text(encoding="utf-8"))
        cached_time = cache_data.get("timestamp", 0)

        # Check if cache is still valid
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            return cache_data.get("skills", [])
    except (json.JSONDecodeError, OSError):
        pass

    return None


def _save_skills_to_cache(skills: List[dict]) -> None:
    """Save skills to cache file.

    Args:
        skills: List of skill dicts to cache
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "timestamp": time.time(),
            "skills": skills,
        }
        SKILLS_CACHE_FILE.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
    except OSError:
        # Silently fail - caching is best-effort
        pass


def _fetch_skills_for_completion() -> List[dict]:
    """Fetch skills list for completion, using cache when available.

    Returns:
        List of skill dicts with name and description
    """
    # Try cache first
    cached = _get_cached_skills()
    if cached is not None:
        return cached

    # Fetch from registry (quiet mode to suppress output during completion)
    try:
        from context_harness.skills import get_skills_registry

        registry = get_skills_registry(quiet=True)
        if registry is None:
            return []

        skills = registry.get("skills", [])

        # Cache the results
        _save_skills_to_cache(skills)

        return skills
    except Exception:
        # Completion should never fail noisily
        return []


def _fuzzy_match(pattern: str, text: str) -> bool:
    """Check if pattern fuzzy-matches text.

    A simple fuzzy match: all characters in pattern appear in text
    in the same order (not necessarily contiguous).

    Args:
        pattern: The pattern to search for (user's incomplete input)
        text: The text to match against (skill name)

    Returns:
        True if pattern fuzzy-matches text

    Examples:
        >>> _fuzzy_match("rf", "react-forms")
        True
        >>> _fuzzy_match("dja", "django-auth")
        True
        >>> _fuzzy_match("xyz", "react-forms")
        False
    """
    pattern = pattern.lower()
    text = text.lower()

    pattern_idx = 0
    for char in text:
        if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
            pattern_idx += 1

    return pattern_idx == len(pattern)


def _fuzzy_score(pattern: str, text: str) -> int:
    """Calculate a fuzzy match score (higher is better).

    Scoring prioritizes:
    - Prefix matches (highest)
    - Contiguous matches
    - Matches at word boundaries (after - or _)

    Args:
        pattern: The pattern to search for
        text: The text to match against

    Returns:
        Score (higher = better match), 0 if no match
    """
    pattern = pattern.lower()
    text = text.lower()

    if not pattern:
        return 1  # Empty pattern matches everything equally

    # Exact prefix match gets highest score
    if text.startswith(pattern):
        return 1000 + (100 - len(text))  # Shorter names rank higher

    # Check for fuzzy match
    if not _fuzzy_match(pattern, text):
        return 0

    score = 100
    pattern_idx = 0
    last_match_idx = -1
    word_boundary_bonus = 0

    for i, char in enumerate(text):
        if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
            # Contiguous match bonus
            if last_match_idx == i - 1:
                score += 10

            # Word boundary bonus (after - or _ or at start)
            if i == 0 or (i > 0 and text[i - 1] in "-_"):
                word_boundary_bonus += 20

            last_match_idx = i
            pattern_idx += 1

    return score + word_boundary_bonus


def complete_skill_names(
    ctx: Context, param: Parameter, incomplete: str
) -> List[CompletionItem]:
    """Provide shell completion for skill names.

    This function is called by Click's shell completion system when
    the user presses Tab after `ch skill install`.

    Args:
        ctx: Click context
        param: The parameter being completed
        incomplete: The partial input typed by the user

    Returns:
        List of CompletionItem objects for matching skills
    """
    skills = _fetch_skills_for_completion()

    if not skills:
        return []

    # Score and filter skills
    scored_skills = []
    for skill in skills:
        name = skill.get("name", "")
        if not name:
            continue

        # If no input yet, include all skills
        if not incomplete:
            scored_skills.append((1, skill))
        else:
            score = _fuzzy_score(incomplete, name)
            if score > 0:
                scored_skills.append((score, skill))

    # Sort by score (descending), then by name
    scored_skills.sort(key=lambda x: (-x[0], x[1].get("name", "")))

    # Convert to CompletionItems with helpful descriptions
    completions = []
    for _score, skill in scored_skills:
        name = skill.get("name", "")
        description = skill.get("description", "")

        # Truncate long descriptions for cleaner display
        if len(description) > 50:
            description = description[:47] + "..."

        completions.append(CompletionItem(value=name, help=description))

    return completions


def clear_skills_cache() -> bool:
    """Clear the skills cache file.

    Returns:
        True if cache was cleared, False if no cache existed
    """
    if SKILLS_CACHE_FILE.exists():
        try:
            SKILLS_CACHE_FILE.unlink()
            return True
        except OSError:
            pass
    return False


def interactive_skill_picker(console) -> Optional[str]:
    """Show an interactive fuzzy-searchable skill picker.

    Args:
        console: Rich console for status messages

    Returns:
        Selected skill name, or None if cancelled/no skills available
    """
    import questionary
    from questionary import Style

    # Fetch skills with a loading indicator
    with console.status("[bold blue]Fetching available skills...[/bold blue]"):
        skills = _fetch_skills_for_completion()

    if not skills:
        console.print("[yellow]No skills available.[/yellow]")
        console.print("[dim]The skills repository may be empty or inaccessible.[/dim]")
        return None

    # Build choices with name and description
    choices = []
    for skill in skills:
        name = skill.get("name", "")
        description = skill.get("description", "")
        if name:
            # Format: "skill-name - Description"
            if description:
                display = f"{name} - {description[:60]}{'...' if len(description) > 60 else ''}"
            else:
                display = name
            choices.append(questionary.Choice(title=display, value=name))

    if not choices:
        console.print("[yellow]No valid skills found.[/yellow]")
        return None

    # Custom style for the picker
    custom_style = Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "fg:white bold"),
            ("answer", "fg:cyan bold"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
            ("instruction", "fg:gray"),
        ]
    )

    # Show the interactive picker
    console.print()
    result = questionary.select(
        "Select a skill to install:",
        choices=choices,
        style=custom_style,
        instruction="(Use arrow keys to navigate, type to filter)",
        use_shortcuts=False,
        use_indicator=True,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    return result


def interactive_local_skill_picker(console, source_path: str = ".") -> Optional[str]:
    """Show an interactive fuzzy-searchable picker for local skills.

    Args:
        console: Rich console for status messages
        source_path: Directory containing .opencode/skill/ (default: current directory)

    Returns:
        Selected skill name, or None if cancelled/no skills available
    """
    import questionary
    from questionary import Style

    from context_harness.skills import list_local_skills

    # Fetch local skills
    skills = list_local_skills(source_path=source_path, quiet=True)

    if not skills:
        console.print("[yellow]No local skills found.[/yellow]")
        console.print("[dim]Expected location: .opencode/skill/[/dim]")
        console.print()
        console.print(
            "[dim]Create a skill with the skill-creator or install one from the repository.[/dim]"
        )
        return None

    # Filter to only valid skills
    valid_skills = [s for s in skills if s.is_valid]

    if not valid_skills:
        console.print("[yellow]No valid skills found.[/yellow]")
        console.print(
            "[dim]All local skills are missing SKILL.md or have errors.[/dim]"
        )
        return None

    # Build choices with name and description
    choices = []
    for skill in valid_skills:
        # Format: "skill-name - Description"
        if skill.description:
            display = f"{skill.name} - {skill.description[:60]}{'...' if len(skill.description) > 60 else ''}"
        else:
            display = skill.name
        choices.append(questionary.Choice(title=display, value=skill.name))

    # Custom style for the picker
    custom_style = Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "fg:white bold"),
            ("answer", "fg:cyan bold"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
            ("instruction", "fg:gray"),
        ]
    )

    # Show the interactive picker
    console.print()
    result = questionary.select(
        "Select a skill to extract:",
        choices=choices,
        style=custom_style,
        instruction="(Use arrow keys to navigate, type to filter)",
        use_shortcuts=False,
        use_indicator=True,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    return result


# =============================================================================
# MCP Server Completion Functions
# =============================================================================


def _get_mcp_servers_for_completion() -> List[dict]:
    """Get MCP servers list for completion.

    Unlike skills which are fetched from a remote registry,
    MCP servers are local to this package.

    Returns:
        List of server dicts with name and description
    """
    try:
        from context_harness.mcp_config import get_mcp_registry

        servers = get_mcp_registry()
        return [
            {
                "name": server.name,
                "description": server.description,
                "auth_type": server.auth_type,
            }
            for server in servers
        ]
    except Exception:
        # Completion should never fail noisily
        return []


def complete_mcp_servers(
    ctx: Context, param: Parameter, incomplete: str
) -> List[CompletionItem]:
    """Provide shell completion for MCP server names.

    This function is called by Click's shell completion system when
    the user presses Tab after `ch mcp add`.

    Args:
        ctx: Click context
        param: The parameter being completed
        incomplete: The partial input typed by the user

    Returns:
        List of CompletionItem objects for matching MCP servers
    """
    servers = _get_mcp_servers_for_completion()

    if not servers:
        return []

    # Score and filter servers
    scored_servers = []
    for server in servers:
        name = server.get("name", "")
        if not name:
            continue

        # If no input yet, include all servers
        if not incomplete:
            scored_servers.append((1, server))
        else:
            score = _fuzzy_score(incomplete, name)
            if score > 0:
                scored_servers.append((score, server))

    # Sort by score (descending), then by name
    scored_servers.sort(key=lambda x: (-x[0], x[1].get("name", "")))

    # Convert to CompletionItems with helpful descriptions
    completions = []
    for _score, server in scored_servers:
        name = server.get("name", "")
        description = server.get("description", "")

        # Truncate long descriptions for cleaner display
        if len(description) > 50:
            description = description[:47] + "..."

        completions.append(CompletionItem(value=name, help=description))

    return completions


def interactive_mcp_picker(console) -> Optional[str]:
    """Show an interactive fuzzy-searchable MCP server picker.

    Args:
        console: Rich console for status messages

    Returns:
        Selected MCP server name, or None if cancelled/no servers available
    """
    import questionary
    from questionary import Style

    servers = _get_mcp_servers_for_completion()

    if not servers:
        console.print("[yellow]No MCP servers available.[/yellow]")
        return None

    # Build choices with name and description
    choices = []
    for server in servers:
        name = server.get("name", "")
        description = server.get("description", "")
        auth_type = server.get("auth_type", "")

        if name:
            # Format: "server-name - Description (auth-type)"
            auth_indicator = f" [{auth_type}]" if auth_type else ""
            if description:
                display = f"{name} - {description[:50]}{'...' if len(description) > 50 else ''}{auth_indicator}"
            else:
                display = f"{name}{auth_indicator}"
            choices.append(questionary.Choice(title=display, value=name))

    if not choices:
        console.print("[yellow]No valid MCP servers found.[/yellow]")
        return None

    # Custom style for the picker
    custom_style = Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "fg:white bold"),
            ("answer", "fg:cyan bold"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
            ("instruction", "fg:gray"),
        ]
    )

    # Show the interactive picker
    console.print()
    result = questionary.select(
        "Select an MCP server to add:",
        choices=choices,
        style=custom_style,
        instruction="(Use arrow keys to navigate, type to filter)",
        use_shortcuts=False,
        use_indicator=True,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    return result
