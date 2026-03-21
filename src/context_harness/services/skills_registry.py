"""Skills registry resolution for ContextHarness.

Provides functions to resolve the skills registry configuration with layered precedence:
1. Environment variables (highest priority)
2. Project config (opencode.json)
3. User config (~/.context-harness/config.json)
4. Default (lowest priority)

Supports both GitHub and HTTP-based registries.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple, Union

from context_harness.primitives import (
    DEFAULT_SKILLS_REPO,
    OpenCodeConfig,
    RegistryAuthConfig,
    Result,
    SKILLS_REPO_ENV_VAR,
    SKILLS_REGISTRY_TOKEN_ENV_VAR,
    SKILLS_REGISTRY_TYPE_ENV_VAR,
    SKILLS_REGISTRY_URL_ENV_VAR,
    SkillsRegistryConfig,
    Success,
    UserConfig,
)
from context_harness.services.registry_client import (
    AuthType,
    GitHubRegistryClient,
    HttpRegistryClient,
    RegistryAuth,
    RegistryClient,
    RegistryConfig,
    RegistryType,
    create_registry_client,
)


def resolve_registry_config(
    project_config: Optional[OpenCodeConfig] = None,
    user_config: Optional[UserConfig] = None,
) -> Tuple[RegistryConfig, str]:
    """Resolve the skills registry configuration with layered precedence.

    Priority (highest to lowest):
    1. CONTEXT_HARNESS_REGISTRY_URL environment variable (HTTP registry)
    2. CONTEXT_HARNESS_SKILLS_REPO environment variable (GitHub)
    3. Project config (opencode.json skillsRegistry)
    4. User config (~/.context-harness/config.json skillsRegistry)
    5. Default (co-labs-co/context-harness-skills)

    Args:
        project_config: Optional project configuration (opencode.json)
        user_config: Optional user configuration

    Returns:
        Tuple of (RegistryConfig, source) where source indicates where it came from:
        - "environment" if from env vars
        - "project" if from opencode.json
        - "user" if from user config
        - "default" if using hardcoded default
    """
    # 1. Check for HTTP registry URL environment variable (highest priority)
    env_url = os.environ.get(SKILLS_REGISTRY_URL_ENV_VAR)
    if env_url:
        auth = _resolve_auth_from_env()
        return (
            RegistryConfig.http(env_url, auth),
            "environment",
        )

    # 2. Check for GitHub repo environment variable
    env_repo = os.environ.get(SKILLS_REPO_ENV_VAR)
    if env_repo:
        return (
            RegistryConfig.github(env_repo),
            "environment",
        )

    # 3. Project config
    if project_config and project_config.skills_registry:
        config = _config_from_skills_registry(project_config.skills_registry)
        return (config, "project")

    # 4. User config
    if user_config and user_config.skills_registry:
        config = _config_from_skills_registry(user_config.skills_registry)
        return (config, "user")

    # 5. Default
    return (RegistryConfig.github(DEFAULT_SKILLS_REPO), "default")


def _resolve_auth_from_env() -> Optional[RegistryAuth]:
    """Resolve authentication from environment variables."""
    token = os.environ.get(SKILLS_REGISTRY_TOKEN_ENV_VAR)
    if not token:
        return None

    # Default to bearer auth when token is provided
    return RegistryAuth(
        type=AuthType.BEARER,
        token_env=SKILLS_REGISTRY_TOKEN_ENV_VAR,
    )


def _config_from_skills_registry(config: SkillsRegistryConfig) -> RegistryConfig:
    """Convert SkillsRegistryConfig to RegistryConfig."""
    if config.is_http and config.url:
        auth = None
        if config.auth:
            auth = RegistryAuth(
                type=AuthType(config.auth.type) if config.auth.type in [e.value for e in AuthType] else AuthType.NONE,
                token_env=config.auth.token_env,
                header_name=config.auth.header_name,
                username_env=config.auth.username_env,
                password_env=config.auth.password_env,
            )
        return RegistryConfig.http(config.url, auth)
    else:
        return RegistryConfig.github(config.default)


def resolve_registry_config_with_loading(
    project_path: Optional[Path] = None,
) -> Tuple[RegistryConfig, str]:
    """Resolve registry config, loading configs as needed.

    This is a convenience function that loads project and user configs
    automatically. Use resolve_registry_config() directly if you already
    have the configs loaded.

    Args:
        project_path: Optional project path for loading opencode.json

    Returns:
        Tuple of (RegistryConfig, source) - see resolve_registry_config() for details
    """
    # 1. Check environment variables first (no loading needed)
    env_url = os.environ.get(SKILLS_REGISTRY_URL_ENV_VAR)
    if env_url:
        auth = _resolve_auth_from_env()
        return (RegistryConfig.http(env_url, auth), "environment")

    env_repo = os.environ.get(SKILLS_REPO_ENV_VAR)
    if env_repo:
        return (RegistryConfig.github(env_repo), "environment")

    # 2. Try to load project config
    project_config: Optional[OpenCodeConfig] = None
    if project_path:
        config_file = project_path / "opencode.json"
    else:
        config_file = Path.cwd() / "opencode.json"

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            project_config = OpenCodeConfig.from_dict(data)
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # Invalid or unreadable config, fall through to next option

    if project_config and project_config.skills_registry:
        config = _config_from_skills_registry(project_config.skills_registry)
        return (config, "project")

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
        config = _config_from_skills_registry(user_config.skills_registry)
        return (config, "user")

    # 4. Default
    return (RegistryConfig.github(DEFAULT_SKILLS_REPO), "default")


def get_registry_client(
    project_path: Optional[Path] = None,
) -> RegistryClient:
    """Get the appropriate registry client based on configuration.

    This is the main entry point for getting a registry client.
    It resolves the configuration and returns the appropriate client.

    Args:
        project_path: Optional project path for loading opencode.json

    Returns:
        RegistryClient implementation (GitHub or HTTP)
    """
    config, _ = resolve_registry_config_with_loading(project_path)
    return create_registry_client(config)


def get_registry_info() -> Result[dict]:
    """Get detailed information about registry configuration.

    Returns:
        Result containing dict with:
        - type: Registry type (github, http)
        - url: Registry URL or repo
        - source: Where the config came from
        - auth_type: Authentication type (if configured)
        - env_vars: Dictionary of environment variable values
    """
    # Check environment variables
    env_url = os.environ.get(SKILLS_REGISTRY_URL_ENV_VAR)
    env_repo = os.environ.get(SKILLS_REPO_ENV_VAR)
    env_token = os.environ.get(SKILLS_REGISTRY_TOKEN_ENV_VAR)
    env_type = os.environ.get(SKILLS_REGISTRY_TYPE_ENV_VAR)

    # Load project config
    project_config: Optional[SkillsRegistryConfig] = None
    config_file = Path.cwd() / "opencode.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            oc = OpenCodeConfig.from_dict(data)
            project_config = oc.skills_registry
        except (json.JSONDecodeError, OSError):
            pass

    # Load user config
    user_config: Optional[SkillsRegistryConfig] = None
    user_config_path = UserConfig.config_path()
    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            uc = UserConfig.from_dict(data)
            user_config = uc.skills_registry
        except (json.JSONDecodeError, OSError):
            pass

    # Resolve final config
    registry_config, source = resolve_registry_config_with_loading()

    return Success(
        value={
            "type": registry_config.type.value,
            "url": registry_config.url,
            "source": source,
            "auth_type": registry_config.auth.type.value if registry_config.auth else "none",
            "env_vars": {
                "registry_url": env_url,
                "skills_repo": env_repo,
                "registry_token": "***" if env_token else None,
                "registry_type": env_type,
            },
            "project_config": project_config.to_dict() if project_config else None,
            "user_config": user_config.to_dict() if user_config else None,
            "default_repo": DEFAULT_SKILLS_REPO,
        }
    )


# Backward compatibility functions
def resolve_skills_repo(
    project_config: Optional[OpenCodeConfig] = None,
    user_config: Optional[UserConfig] = None,
) -> Tuple[str, str]:
    """Resolve the skills repository with layered precedence.

    DEPRECATED: Use resolve_registry_config() instead.

    This function is maintained for backward compatibility.
    It returns only the GitHub repo string, not the full registry config.

    Priority (highest to lowest):
    1. CONTEXT_HARNESS_SKILLS_REPO environment variable
    2. Project config (opencode.json skillsRegistry.default)
    3. User config (~/.context-harness/config.json skillsRegistry.default)
    4. Default (co-labs-co/context-harness-skills)

    Args:
        project_config: Optional project configuration (opencode.json)
        user_config: Optional user configuration

    Returns:
        Tuple of (repo, source) where source indicates where it came from:
        - "environment" if from env var
        - "project" if from opencode.json
        - "user" if from user config
        - "default" if using hardcoded default
    """
    config, source = resolve_registry_config(project_config, user_config)
    # Return the URL (which is the repo for GitHub)
    return (config.url, source)


def resolve_skills_repo_with_loading(
    project_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Resolve skills repo, loading configs as needed.

    DEPRECATED: Use resolve_registry_config_with_loading() instead.

    This is a convenience function that loads project and user configs
    automatically. Use resolve_skills_repo() directly if you already
    have the configs loaded.

    Args:
        project_path: Optional project path for loading opencode.json

    Returns:
        Tuple of (repo, source) - see resolve_skills_repo() for details
    """
    config, source = resolve_registry_config_with_loading(project_path)
    return (config.url, source)


def get_skills_repo_info() -> Result[dict]:
    """Get detailed information about skills repo resolution.

    DEPRECATED: Use get_registry_info() instead.

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
    result = get_registry_info()
    if isinstance(result, Success):
        # Map new registry info to old skills repo info format
        info = result.value
        return Success(
            value={
                "repo": info.get("url", DEFAULT_SKILLS_REPO),
                "source": info.get("source", "default"),
                "env_var": info.get("env_vars", {}).get("skills_repo_env", SKILLS_REPO_ENV_VAR),
                "env_value": info.get("env_vars", {}).get("skills_repo"),
                "project_value": info.get("project_config", {}).get("default") if info.get("project_config") else None,
                "user_value": info.get("user_config", {}).get("default") if info.get("user_config") else None,
                "default_value": DEFAULT_SKILLS_REPO,
            }
        )
    return result
