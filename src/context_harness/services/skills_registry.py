"""Skills registry resolution for ContextHarness.

Provides functions to resolve the skills repository with layered precedence:
1. Environment variable (highest priority)
2. Project config (.context-harness/config.json)
3. User config (~/.context-harness/config.json)
4. Default (lowest priority)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple

from context_harness.primitives import (
    DEFAULT_SKILLS_REPO,
    ProjectHarnessConfig,
    Result,
    SKILLS_REPO_ENV_VAR,
    Success,
    UserConfig,
)


def resolve_skills_repo(
    project_config: Optional[ProjectHarnessConfig] = None,
    user_config: Optional[UserConfig] = None,
) -> Tuple[str, str]:
    """Resolve the skills repository with layered precedence.

    Priority (highest to lowest):
    1. CONTEXT_HARNESS_SKILLS_REPO environment variable
    2. Project config (.context-harness/config.json skillsRegistry.default)
    3. User config (~/.context-harness/config.json skillsRegistry.default)
    4. Default (co-labs-co/context-harness-skills)

    Args:
        project_config: Optional project configuration (.context-harness/config.json)
        user_config: Optional user configuration

    Returns:
        Tuple of (repo, source) where source indicates where it came from:
        - "environment" if from env var
        - "project" if from .context-harness/config.json
        - "user" if from user config
        - "default" if using hardcoded default
    """
    # 1. Environment variable (highest priority)
    env_repo = os.environ.get(SKILLS_REPO_ENV_VAR)
    if env_repo:
        return (env_repo, "environment")

    # 2. Project config (.context-harness/config.json)
    if project_config and project_config.skills_registry:
        return (project_config.skills_registry.default, "project")

    # 3. User config
    if user_config and user_config.skills_registry:
        return (user_config.skills_registry.default, "user")

    # 4. Default
    return (DEFAULT_SKILLS_REPO, "default")


def resolve_skills_repo_with_loading(
    project_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Resolve skills repo, loading configs as needed.

    This is a convenience function that loads project and user configs
    automatically. Use resolve_skills_repo() directly if you already
    have the configs loaded.

    Args:
        project_path: Optional project path for loading .context-harness/config.json

    Returns:
        Tuple of (repo, source) - see resolve_skills_repo() for details
    """
    # 1. Check environment variable first (no loading needed)
    env_repo = os.environ.get(SKILLS_REPO_ENV_VAR)
    if env_repo:
        return (env_repo, "environment")

    # 2. Try to load project config (.context-harness/config.json)
    project_config: Optional[ProjectHarnessConfig] = None
    if project_path:
        config_file = project_path / ".context-harness" / "config.json"
    else:
        config_file = Path.cwd() / ".context-harness" / "config.json"

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            project_config = ProjectHarnessConfig.from_dict(data)
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # Invalid or unreadable config, fall through to next option

    if project_config and project_config.skills_registry:
        return (project_config.skills_registry.default, "project")

    # 3. Try to load user config
    user_config: Optional[UserConfig] = None
    user_config_path = UserConfig.config_path()

    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_config = UserConfig.from_dict(data)
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # Invalid or unreadable config, fall through to default

    if user_config and user_config.skills_registry:
        return (user_config.skills_registry.default, "user")

    # 4. Default
    return (DEFAULT_SKILLS_REPO, "default")


def get_skills_repo_info() -> Result[dict]:
    """Get detailed information about skills repo resolution.

    Returns:
        Result containing dict with:
        - repo: The resolved repository
        - source: Where it came from
        - env_var: The environment variable name
        - env_value: Current env var value (if set)
        - project_value: Value from project config (if set)
        - user_value: Value from user config (if set)
        - default_value: The default repository
    """
    env_value = os.environ.get(SKILLS_REPO_ENV_VAR)

    # Load project config (.context-harness/config.json)
    project_value: Optional[str] = None
    config_file = Path.cwd() / ".context-harness" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            project_config = ProjectHarnessConfig.from_dict(data)
            if project_config.skills_registry:
                project_value = project_config.skills_registry.default
        except (json.JSONDecodeError, OSError):
            pass  # Invalid or unreadable config, project_value stays None

    # Load user config
    user_value: Optional[str] = None
    user_config_path = UserConfig.config_path()
    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_config = UserConfig.from_dict(data)
            if user_config.skills_registry:
                user_value = user_config.skills_registry.default
        except (json.JSONDecodeError, OSError):
            pass  # Invalid or unreadable config, user_value stays None

    repo, source = resolve_skills_repo_with_loading()

    return Success(
        value={
            "repo": repo,
            "source": source,
            "env_var": SKILLS_REPO_ENV_VAR,
            "env_value": env_value,
            "project_value": project_value,
            "user_value": user_value,
            "default_value": DEFAULT_SKILLS_REPO,
        }
    )
