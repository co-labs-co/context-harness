"""Unit tests for skills registry resolution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from context_harness.primitives import (
    DEFAULT_SKILLS_REPO,
    OpenCodeConfig,
    ProjectHarnessConfig,
    SKILLS_REPO_ENV_VAR,
    SkillsRegistryConfig,
    Success,
    UserConfig,
)
from context_harness.services.skills_registry import (
    get_skills_repo_info,
    resolve_skills_repo,
    resolve_skills_repo_with_loading,
)


class TestSkillsRegistryConfig:
    """Tests for SkillsRegistryConfig primitive."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = SkillsRegistryConfig()
        assert config.default == DEFAULT_SKILLS_REPO

    def test_custom_repo(self) -> None:
        """Test with custom repo."""
        config = SkillsRegistryConfig(default="my-org/my-skills")
        assert config.default == "my-org/my-skills"

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        config = SkillsRegistryConfig.from_dict({"default": "custom/repo"})
        assert config.default == "custom/repo"

    def test_from_dict_empty(self) -> None:
        """Test creating from empty dictionary uses defaults."""
        config = SkillsRegistryConfig.from_dict({})
        assert config.default == DEFAULT_SKILLS_REPO

    def test_to_dict_default(self) -> None:
        """Test to_dict with default value returns empty dict."""
        config = SkillsRegistryConfig()
        assert config.to_dict() == {}

    def test_to_dict_custom(self) -> None:
        """Test to_dict with custom value."""
        config = SkillsRegistryConfig(default="custom/repo")
        assert config.to_dict() == {"default": "custom/repo"}


class TestUserConfig:
    """Tests for UserConfig primitive."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = UserConfig()
        assert config.skills_registry is None

    def test_with_skills_registry(self) -> None:
        """Test with skills registry."""
        registry = SkillsRegistryConfig(default="my-org/skills")
        config = UserConfig(skills_registry=registry)
        assert config.skills_registry is not None
        assert config.skills_registry.default == "my-org/skills"

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        config = UserConfig.from_dict({"skillsRegistry": {"default": "custom/repo"}})
        assert config.skills_registry is not None
        assert config.skills_registry.default == "custom/repo"

    def test_from_dict_empty(self) -> None:
        """Test creating from empty dictionary."""
        config = UserConfig.from_dict({})
        assert config.skills_registry is None

    def test_to_dict_empty(self) -> None:
        """Test to_dict with no values returns empty dict."""
        config = UserConfig()
        assert config.to_dict() == {}

    def test_to_dict_with_registry(self) -> None:
        """Test to_dict with skills registry."""
        config = UserConfig(skills_registry=SkillsRegistryConfig(default="custom/repo"))
        assert config.to_dict() == {"skillsRegistry": {"default": "custom/repo"}}

    def test_config_path(self) -> None:
        """Test config path is in home directory."""
        path = UserConfig.config_path()
        assert path == Path.home() / ".context-harness" / "config.json"

    def test_config_dir(self) -> None:
        """Test config directory path."""
        dir_path = UserConfig.config_dir()
        assert dir_path == Path.home() / ".context-harness"


class TestProjectHarnessConfig:
    """Tests for ProjectHarnessConfig primitive."""

    def test_default_no_registry(self) -> None:
        """Test default config has no skills registry."""
        config = ProjectHarnessConfig()
        assert config.skills_registry is None

    def test_with_skills_registry(self) -> None:
        """Test config with skills registry."""
        registry = SkillsRegistryConfig(default="my-org/skills")
        config = ProjectHarnessConfig(skills_registry=registry)
        assert config.skills_registry is not None
        assert config.skills_registry.default == "my-org/skills"

    def test_from_dict_with_registry(self) -> None:
        """Test parsing skills registry from dict."""
        config = ProjectHarnessConfig.from_dict(
            {"skillsRegistry": {"default": "custom/repo"}}
        )
        assert config.skills_registry is not None
        assert config.skills_registry.default == "custom/repo"

    def test_from_dict_without_registry(self) -> None:
        """Test parsing without skills registry."""
        config = ProjectHarnessConfig.from_dict({})
        assert config.skills_registry is None

    def test_to_dict_with_registry(self) -> None:
        """Test serializing skills registry."""
        config = ProjectHarnessConfig(
            skills_registry=SkillsRegistryConfig(default="custom/repo")
        )
        result = config.to_dict()
        assert "skillsRegistry" in result
        assert result["skillsRegistry"] == {"default": "custom/repo"}

    def test_to_dict_without_registry(self) -> None:
        """Test serializing without skills registry."""
        config = ProjectHarnessConfig()
        result = config.to_dict()
        assert "skillsRegistry" not in result


class TestOpenCodeConfigNoSkillsRegistry:
    """Tests that OpenCodeConfig no longer has skills_registry."""

    def test_no_skills_registry_field(self) -> None:
        """Test OpenCodeConfig has no skills_registry field."""
        config = OpenCodeConfig()
        assert not hasattr(config, "skills_registry")

    def test_from_dict_ignores_skills_registry(self) -> None:
        """Test from_dict ignores skillsRegistry key (no longer parsed)."""
        config = OpenCodeConfig.from_dict(
            {"skillsRegistry": {"default": "custom/repo"}}
        )
        assert not hasattr(config, "skills_registry")

    def test_to_dict_no_skills_registry(self) -> None:
        """Test to_dict does not include skillsRegistry."""
        config = OpenCodeConfig()
        result = config.to_dict()
        assert "skillsRegistry" not in result


class TestResolveSkillsRepo:
    """Tests for resolve_skills_repo function."""

    def test_default_no_config(self) -> None:
        """Test returns default when no config provided."""
        repo, source = resolve_skills_repo()
        assert repo == DEFAULT_SKILLS_REPO
        assert source == "default"

    def test_env_var_highest_priority(self) -> None:
        """Test environment variable has highest priority."""
        with patch.dict(os.environ, {SKILLS_REPO_ENV_VAR: "env/repo"}):
            project_config = ProjectHarnessConfig(
                skills_registry=SkillsRegistryConfig(default="project/repo")
            )
            user_config = UserConfig(
                skills_registry=SkillsRegistryConfig(default="user/repo")
            )
            repo, source = resolve_skills_repo(project_config, user_config)
            assert repo == "env/repo"
            assert source == "environment"

    def test_project_config_over_user(self) -> None:
        """Test project config takes precedence over user config."""
        project_config = ProjectHarnessConfig(
            skills_registry=SkillsRegistryConfig(default="project/repo")
        )
        user_config = UserConfig(
            skills_registry=SkillsRegistryConfig(default="user/repo")
        )
        repo, source = resolve_skills_repo(project_config, user_config)
        assert repo == "project/repo"
        assert source == "project"

    def test_user_config_over_default(self) -> None:
        """Test user config takes precedence over default."""
        user_config = UserConfig(
            skills_registry=SkillsRegistryConfig(default="user/repo")
        )
        repo, source = resolve_skills_repo(user_config=user_config)
        assert repo == "user/repo"
        assert source == "user"

    def test_project_config_without_registry(self) -> None:
        """Test project config without registry falls through."""
        project_config = ProjectHarnessConfig()  # No skills_registry
        user_config = UserConfig(
            skills_registry=SkillsRegistryConfig(default="user/repo")
        )
        repo, source = resolve_skills_repo(project_config, user_config)
        assert repo == "user/repo"
        assert source == "user"


class TestResolveSkillsRepoWithLoading:
    """Tests for resolve_skills_repo_with_loading function."""

    @pytest.fixture
    def clean_env(self) -> Generator[None, None, None]:
        """Ensure env var is not set."""
        original = os.environ.pop(SKILLS_REPO_ENV_VAR, None)
        yield
        if original is not None:
            os.environ[SKILLS_REPO_ENV_VAR] = original

    def test_env_var_override(self, clean_env: None) -> None:
        """Test environment variable override."""
        with patch.dict(os.environ, {SKILLS_REPO_ENV_VAR: "env/override"}):
            repo, source = resolve_skills_repo_with_loading()
            assert repo == "env/override"
            assert source == "environment"

    def test_default_when_no_config(self, clean_env: None, tmp_path: Path) -> None:
        """Test returns default when no config files exist."""
        with patch(
            "context_harness.services.skills_registry.Path.cwd", return_value=tmp_path
        ):
            with patch.object(
                UserConfig, "config_path", return_value=tmp_path / "nonexistent.json"
            ):
                repo, source = resolve_skills_repo_with_loading()
                assert repo == DEFAULT_SKILLS_REPO
                assert source == "default"

    def test_loads_project_config(self, clean_env: None, tmp_path: Path) -> None:
        """Test loads project config from .context-harness/config.json."""
        # Create .context-harness/config.json with skills registry
        config_dir = tmp_path / ".context-harness"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps({"skillsRegistry": {"default": "project/loaded"}})
        )

        with patch(
            "context_harness.services.skills_registry.Path.cwd", return_value=tmp_path
        ):
            with patch.object(
                UserConfig, "config_path", return_value=tmp_path / "nonexistent.json"
            ):
                repo, source = resolve_skills_repo_with_loading(tmp_path)
                assert repo == "project/loaded"
                assert source == "project"

    def test_loads_user_config(self, clean_env: None, tmp_path: Path) -> None:
        """Test loads user config when project config missing."""
        # Create user config
        user_config_path = tmp_path / "user_config.json"
        user_config_path.write_text(
            json.dumps({"skillsRegistry": {"default": "user/loaded"}})
        )

        with patch(
            "context_harness.services.skills_registry.Path.cwd", return_value=tmp_path
        ):
            with patch.object(UserConfig, "config_path", return_value=user_config_path):
                repo, source = resolve_skills_repo_with_loading()
                assert repo == "user/loaded"
                assert source == "user"


class TestGetSkillsRepoInfo:
    """Tests for get_skills_repo_info function."""

    @pytest.fixture
    def clean_env(self) -> Generator[None, None, None]:
        """Ensure env var is not set."""
        original = os.environ.pop(SKILLS_REPO_ENV_VAR, None)
        yield
        if original is not None:
            os.environ[SKILLS_REPO_ENV_VAR] = original

    def test_returns_success(self, clean_env: None, tmp_path: Path) -> None:
        """Test returns success result."""
        with patch(
            "context_harness.services.skills_registry.Path.cwd", return_value=tmp_path
        ):
            with patch.object(
                UserConfig, "config_path", return_value=tmp_path / "nonexistent.json"
            ):
                result = get_skills_repo_info()
                assert isinstance(result, Success)
                info = result.value
                assert "repo" in info
                assert "source" in info
                assert "env_var" in info
                assert info["env_var"] == SKILLS_REPO_ENV_VAR

    def test_includes_all_values(self, clean_env: None, tmp_path: Path) -> None:
        """Test includes all configuration values."""
        # Set env var
        with patch.dict(os.environ, {SKILLS_REPO_ENV_VAR: "env/repo"}):
            # Create project config (.context-harness/config.json)
            config_dir = tmp_path / ".context-harness"
            config_dir.mkdir()
            config_file = config_dir / "config.json"
            config_file.write_text(
                json.dumps({"skillsRegistry": {"default": "project/repo"}})
            )

            # Create user config
            user_config_path = tmp_path / "user_config.json"
            user_config_path.write_text(
                json.dumps({"skillsRegistry": {"default": "user/repo"}})
            )

            with patch(
                "context_harness.services.skills_registry.Path.cwd",
                return_value=tmp_path,
            ):
                with patch.object(
                    UserConfig, "config_path", return_value=user_config_path
                ):
                    result = get_skills_repo_info()
                    assert isinstance(result, Success)
                    info = result.value

                    assert info["repo"] == "env/repo"
                    assert info["source"] == "environment"
                    assert info["env_value"] == "env/repo"
                    assert info["project_value"] == "project/repo"
                    assert info["user_value"] == "user/repo"
                    assert info["default_value"] == DEFAULT_SKILLS_REPO
