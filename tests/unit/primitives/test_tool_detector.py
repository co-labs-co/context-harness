"""Unit tests for ToolDetector, ToolPaths, DetectedTools, and convenience functions.

Tests cover:
- ToolType enum values
- ToolPaths factory methods (.for_opencode, .for_claude_code) and path correctness
- DetectedTools properties (any_installed, both_installed, installed_tools, get_paths)
- ToolDetector.detect() with various directory configurations
- ToolDetector.get_skills_dirs() with explicit targets and auto-detect
- ToolDetector.get_mcp_config_paths() with explicit targets and auto-detect
- ToolDetector.resolve_skill_install_dir() with explicit targets and auto-detect
- ToolDetector.get_memory_file_path() with explicit targets and auto-detect
- ToolDetector.get_opencode_paths() / get_claude_code_paths() accessors
- Convenience functions: detect_tools(), get_skills_dir(), get_all_skills_dirs()
"""

from pathlib import Path

import pytest

from context_harness.primitives.tool_detector import (
    DetectedTools,
    ToolDetector,
    ToolPaths,
    ToolType,
    detect_tools,
    get_all_skills_dirs,
    get_skills_dir,
)


# ---------------------------------------------------------------------------
# ToolType
# ---------------------------------------------------------------------------


class TestToolType:
    """Tests for ToolType enum."""

    def test_opencode_value(self):
        assert ToolType.OPENCODE.value == "opencode"

    def test_claude_code_value(self):
        assert ToolType.CLAUDE_CODE.value == "claude-code"

    def test_is_string_enum(self):
        assert isinstance(ToolType.OPENCODE, str)
        assert ToolType.OPENCODE == "opencode"


# ---------------------------------------------------------------------------
# ToolPaths
# ---------------------------------------------------------------------------


class TestToolPaths:
    """Tests for ToolPaths factory methods."""

    def test_for_opencode_paths(self, tmp_path):
        paths = ToolPaths.for_opencode(tmp_path)

        assert paths.tool == ToolType.OPENCODE
        assert paths.config_dir == tmp_path / ".opencode"
        assert paths.skills_dir == tmp_path / ".opencode" / "skill"
        assert paths.agents_dir == tmp_path / ".opencode" / "agent"
        assert paths.commands_dir == tmp_path / ".opencode" / "command"
        assert paths.mcp_config == tmp_path / "opencode.json"
        assert paths.memory_file == tmp_path / "AGENTS.md"

    def test_for_claude_code_paths(self, tmp_path):
        paths = ToolPaths.for_claude_code(tmp_path)

        assert paths.tool == ToolType.CLAUDE_CODE
        assert paths.config_dir == tmp_path / ".claude"
        assert paths.skills_dir == tmp_path / ".claude" / "skills"
        assert paths.agents_dir == tmp_path / ".claude" / "agents"
        assert paths.commands_dir == tmp_path / ".claude" / "commands"
        assert paths.mcp_config == tmp_path / ".mcp.json"
        assert paths.memory_file == tmp_path / "CLAUDE.md"

    def test_opencode_uses_singular_directories(self, tmp_path):
        """OpenCode uses singular names (skill, agent, command)."""
        paths = ToolPaths.for_opencode(tmp_path)
        assert paths.skills_dir.name == "skill"
        assert paths.agents_dir.name == "agent"
        assert paths.commands_dir.name == "command"

    def test_claude_code_uses_plural_directories(self, tmp_path):
        """Claude Code uses plural names (skills, agents, commands)."""
        paths = ToolPaths.for_claude_code(tmp_path)
        assert paths.skills_dir.name == "skills"
        assert paths.agents_dir.name == "agents"
        assert paths.commands_dir.name == "commands"

    def test_frozen_dataclass(self, tmp_path):
        """ToolPaths is frozen — attributes cannot be reassigned."""
        paths = ToolPaths.for_opencode(tmp_path)
        with pytest.raises(AttributeError):
            paths.tool = ToolType.CLAUDE_CODE  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DetectedTools
# ---------------------------------------------------------------------------


class TestDetectedTools:
    """Tests for DetectedTools properties."""

    @pytest.fixture
    def _both_paths(self, tmp_path):
        return (
            ToolPaths.for_opencode(tmp_path),
            ToolPaths.for_claude_code(tmp_path),
        )

    # -- any_installed --
    def test_any_installed_both(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, True, ToolType.OPENCODE, oc, cc)
        assert d.any_installed is True

    def test_any_installed_opencode_only(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, False, ToolType.OPENCODE, oc, cc)
        assert d.any_installed is True

    def test_any_installed_claude_only(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(False, True, ToolType.CLAUDE_CODE, oc, cc)
        assert d.any_installed is True

    def test_any_installed_none(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(False, False, None, oc, cc)
        assert d.any_installed is False

    # -- both_installed --
    def test_both_installed_true(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, True, ToolType.OPENCODE, oc, cc)
        assert d.both_installed is True

    def test_both_installed_false(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, False, ToolType.OPENCODE, oc, cc)
        assert d.both_installed is False

    # -- installed_tools --
    def test_installed_tools_both(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, True, ToolType.OPENCODE, oc, cc)
        assert d.installed_tools == [ToolType.OPENCODE, ToolType.CLAUDE_CODE]

    def test_installed_tools_none(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(False, False, None, oc, cc)
        assert d.installed_tools == []

    # -- get_paths --
    def test_get_paths_primary(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, False, ToolType.OPENCODE, oc, cc)
        assert d.get_paths() == oc

    def test_get_paths_explicit_opencode(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, True, ToolType.OPENCODE, oc, cc)
        assert d.get_paths(ToolType.OPENCODE) == oc

    def test_get_paths_explicit_claude(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(True, True, ToolType.OPENCODE, oc, cc)
        assert d.get_paths(ToolType.CLAUDE_CODE) == cc

    def test_get_paths_returns_none_if_not_installed(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(False, False, None, oc, cc)
        assert d.get_paths(ToolType.OPENCODE) is None
        assert d.get_paths(ToolType.CLAUDE_CODE) is None

    def test_get_paths_none_primary_returns_none(self, _both_paths):
        oc, cc = _both_paths
        d = DetectedTools(False, False, None, oc, cc)
        assert d.get_paths() is None


# ---------------------------------------------------------------------------
# ToolDetector.detect()
# ---------------------------------------------------------------------------


class TestToolDetectorDetect:
    """Tests for ToolDetector.detect()."""

    def test_detect_opencode_only(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        detected = ToolDetector(tmp_path).detect()

        assert detected.opencode is True
        assert detected.claude_code is False
        assert detected.primary == ToolType.OPENCODE

    def test_detect_claude_code_only(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        detected = ToolDetector(tmp_path).detect()

        assert detected.opencode is False
        assert detected.claude_code is True
        assert detected.primary == ToolType.CLAUDE_CODE

    def test_detect_both_prefers_opencode(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".claude").mkdir()
        detected = ToolDetector(tmp_path).detect()

        assert detected.opencode is True
        assert detected.claude_code is True
        assert detected.primary == ToolType.OPENCODE

    def test_detect_neither(self, tmp_path):
        detected = ToolDetector(tmp_path).detect()

        assert detected.opencode is False
        assert detected.claude_code is False
        assert detected.primary is None

    def test_detect_resolves_path(self, tmp_path):
        """Detector resolves symlinks / relative segments."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".opencode").mkdir()

        # Use a path with a '..' component
        indirect = tmp_path / "project" / "subdir" / ".."
        indirect.mkdir(parents=True, exist_ok=True)
        detector = ToolDetector(indirect)

        detected = detector.detect()
        assert detected.opencode is True


# ---------------------------------------------------------------------------
# ToolDetector.get_skills_dirs()
# ---------------------------------------------------------------------------


class TestToolDetectorGetSkillsDirs:
    """Tests for ToolDetector.get_skills_dirs()."""

    def test_explicit_opencode(self, tmp_path):
        dirs = ToolDetector(tmp_path).get_skills_dirs("opencode")
        assert len(dirs) == 1
        assert dirs[0] == tmp_path / ".opencode" / "skill"

    def test_explicit_claude_code(self, tmp_path):
        dirs = ToolDetector(tmp_path).get_skills_dirs("claude-code")
        assert len(dirs) == 1
        assert dirs[0] == tmp_path / ".claude" / "skills"

    def test_explicit_both(self, tmp_path):
        dirs = ToolDetector(tmp_path).get_skills_dirs("both")
        assert len(dirs) == 2

    def test_auto_detect_opencode_installed(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        dirs = ToolDetector(tmp_path).get_skills_dirs()
        assert len(dirs) == 1
        assert dirs[0].name == "skill"

    def test_auto_detect_none_installed(self, tmp_path):
        dirs = ToolDetector(tmp_path).get_skills_dirs()
        assert dirs == []


# ---------------------------------------------------------------------------
# ToolDetector.get_mcp_config_paths()
# ---------------------------------------------------------------------------


class TestToolDetectorGetMCPConfigPaths:
    """Tests for ToolDetector.get_mcp_config_paths()."""

    def test_explicit_opencode(self, tmp_path):
        paths = ToolDetector(tmp_path).get_mcp_config_paths("opencode")
        assert paths == [tmp_path / "opencode.json"]

    def test_explicit_claude_code(self, tmp_path):
        paths = ToolDetector(tmp_path).get_mcp_config_paths("claude-code")
        assert paths == [tmp_path / ".mcp.json"]

    def test_explicit_both(self, tmp_path):
        paths = ToolDetector(tmp_path).get_mcp_config_paths("both")
        assert len(paths) == 2
        assert tmp_path / "opencode.json" in paths
        assert tmp_path / ".mcp.json" in paths

    def test_auto_detect_both_installed(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".claude").mkdir()
        paths = ToolDetector(tmp_path).get_mcp_config_paths()
        assert len(paths) == 2

    def test_auto_detect_none_installed(self, tmp_path):
        paths = ToolDetector(tmp_path).get_mcp_config_paths()
        assert paths == []


# ---------------------------------------------------------------------------
# ToolDetector.resolve_skill_install_dir()
# ---------------------------------------------------------------------------


class TestToolDetectorResolveSkillInstallDir:
    """Tests for ToolDetector.resolve_skill_install_dir()."""

    def test_explicit_opencode(self, tmp_path):
        result = ToolDetector(tmp_path).resolve_skill_install_dir("opencode")
        assert result == tmp_path / ".opencode" / "skill"

    def test_explicit_claude_code(self, tmp_path):
        result = ToolDetector(tmp_path).resolve_skill_install_dir("claude-code")
        assert result == tmp_path / ".claude" / "skills"

    def test_explicit_both_returns_opencode(self, tmp_path):
        result = ToolDetector(tmp_path).resolve_skill_install_dir("both")
        assert result == tmp_path / ".opencode" / "skill"

    def test_auto_detect_primary(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        result = ToolDetector(tmp_path).resolve_skill_install_dir()
        assert result == tmp_path / ".claude" / "skills"

    def test_auto_detect_none_returns_none(self, tmp_path):
        result = ToolDetector(tmp_path).resolve_skill_install_dir()
        assert result is None


# ---------------------------------------------------------------------------
# ToolDetector.get_memory_file_path()
# ---------------------------------------------------------------------------


class TestToolDetectorGetMemoryFilePath:
    """Tests for ToolDetector.get_memory_file_path()."""

    def test_explicit_opencode(self, tmp_path):
        result = ToolDetector(tmp_path).get_memory_file_path("opencode")
        assert result == tmp_path / "AGENTS.md"

    def test_explicit_claude_code(self, tmp_path):
        result = ToolDetector(tmp_path).get_memory_file_path("claude-code")
        assert result == tmp_path / "CLAUDE.md"

    def test_auto_detect(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        result = ToolDetector(tmp_path).get_memory_file_path()
        assert result == tmp_path / "AGENTS.md"

    def test_auto_detect_none(self, tmp_path):
        result = ToolDetector(tmp_path).get_memory_file_path()
        assert result is None


# ---------------------------------------------------------------------------
# ToolDetector accessor methods
# ---------------------------------------------------------------------------


class TestToolDetectorAccessors:
    """Tests for get_opencode_paths / get_claude_code_paths."""

    def test_get_opencode_paths_always_available(self, tmp_path):
        paths = ToolDetector(tmp_path).get_opencode_paths()
        assert paths.tool == ToolType.OPENCODE

    def test_get_claude_code_paths_always_available(self, tmp_path):
        paths = ToolDetector(tmp_path).get_claude_code_paths()
        assert paths.tool == ToolType.CLAUDE_CODE


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_detect_tools(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        detected = detect_tools(tmp_path)
        assert detected.opencode is True

    def test_get_skills_dir_returns_first(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        result = get_skills_dir(tmp_path)
        assert result is not None
        assert result.name == "skill"

    def test_get_skills_dir_none_installed(self, tmp_path):
        result = get_skills_dir(tmp_path)
        assert result is None

    def test_get_skills_dir_with_target(self, tmp_path):
        result = get_skills_dir(tmp_path, "claude-code")
        assert result is not None
        assert result.name == "skills"

    def test_get_all_skills_dirs(self, tmp_path):
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".claude").mkdir()
        dirs = get_all_skills_dirs(tmp_path)
        assert len(dirs) == 2
