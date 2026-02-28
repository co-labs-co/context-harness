"""Unit tests for ProjectHarnessConfigService."""

from __future__ import annotations

import json
from pathlib import Path

from context_harness.primitives import (
    Failure,
    ProjectHarnessConfig,
    SkillsRegistryConfig,
    Success,
)
from context_harness.services.project_harness_config_service import (
    ProjectHarnessConfigService,
)


class TestProjectHarnessConfigService:
    """Tests for ProjectHarnessConfigService."""

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        """Test loading nonexistent config returns empty ProjectHarnessConfig."""
        config_path = tmp_path / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)

        result = service.load()

        assert isinstance(result, Success)
        assert result.value.skills_registry is None

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading valid config file."""
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"skillsRegistry": {"default": "my-org/skills"}})
        )
        service = ProjectHarnessConfigService(config_path=config_path)

        result = service.load()

        assert isinstance(result, Success)
        assert result.value.skills_registry is not None
        assert result.value.skills_registry.default == "my-org/skills"

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON returns failure."""
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json {{{")
        service = ProjectHarnessConfigService(config_path=config_path)

        result = service.load()

        assert isinstance(result, Failure)
        assert "Invalid JSON" in result.error

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Test save creates config directory if missing."""
        config_path = tmp_path / "subdir" / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)
        config = ProjectHarnessConfig(
            skills_registry=SkillsRegistryConfig(default="my-org/skills")
        )

        result = service.save(config)

        assert isinstance(result, Success)
        assert config_path.exists()
        assert config_path.parent.exists()

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Test saving and loading preserves data."""
        config_path = tmp_path / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)
        original = ProjectHarnessConfig(
            skills_registry=SkillsRegistryConfig(default="my-org/skills")
        )

        service.save(original)
        result = service.load()

        assert isinstance(result, Success)
        assert result.value.skills_registry is not None
        assert result.value.skills_registry.default == "my-org/skills"

    def test_exists_false_when_missing(self, tmp_path: Path) -> None:
        """Test exists returns false when file missing."""
        config_path = tmp_path / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)

        assert service.exists() is False

    def test_exists_true_when_present(self, tmp_path: Path) -> None:
        """Test exists returns true when file present."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        service = ProjectHarnessConfigService(config_path=config_path)

        assert service.exists() is True

    def test_config_path_property(self, tmp_path: Path) -> None:
        """Test config_path property."""
        config_path = tmp_path / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)

        assert service.config_path == config_path

    def test_config_dir_property(self, tmp_path: Path) -> None:
        """Test config_dir property."""
        config_path = tmp_path / "subdir" / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)

        assert service.config_dir == tmp_path / "subdir"

    def test_ensure_config_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test ensure_config_dir creates directory."""
        config_path = tmp_path / "new_dir" / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)

        result = service.ensure_config_dir()

        assert isinstance(result, Success)
        assert (tmp_path / "new_dir").exists()

    def test_ensure_config_dir_idempotent(self, tmp_path: Path) -> None:
        """Test ensure_config_dir is idempotent."""
        config_path = tmp_path / "existing_dir" / "config.json"
        (tmp_path / "existing_dir").mkdir()
        service = ProjectHarnessConfigService(config_path=config_path)

        result = service.ensure_config_dir()

        assert isinstance(result, Success)
        assert (tmp_path / "existing_dir").exists()

    def test_save_empty_config(self, tmp_path: Path) -> None:
        """Test saving empty config creates minimal file."""
        config_path = tmp_path / "config.json"
        service = ProjectHarnessConfigService(config_path=config_path)
        config = ProjectHarnessConfig()

        result = service.save(config)

        assert isinstance(result, Success)
        # Empty config should produce {}
        content = json.loads(config_path.read_text())
        assert content == {}

    def test_default_config_path(self) -> None:
        """Test default config path is CWD .context-harness."""
        service = ProjectHarnessConfigService()
        expected = Path.cwd() / ".context-harness" / "config.json"
        assert service.config_path == expected
