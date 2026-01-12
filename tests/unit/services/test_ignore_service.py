"""Unit tests for IgnoreService."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_harness.primitives import (
    Failure,
    IgnoreConfig,
    IgnoreMatch,
    IgnorePattern,
    IgnoreSource,
    Success,
)
from context_harness.services import IgnoreService


class TestIgnorePattern:
    """Tests for IgnorePattern dataclass."""

    def test_from_line_simple_pattern(self) -> None:
        """Should parse a simple pattern."""
        pattern = IgnorePattern.from_line("node_modules/")

        assert pattern is not None
        assert pattern.pattern == "node_modules/"
        assert pattern.negation is False
        assert pattern.source == IgnoreSource.CONTEXTIGNORE_FILE

    def test_from_line_negation_pattern(self) -> None:
        """Should parse a negation pattern."""
        pattern = IgnorePattern.from_line("!important.txt")

        assert pattern is not None
        assert pattern.pattern == "important.txt"
        assert pattern.negation is True

    def test_from_line_empty_line(self) -> None:
        """Should return None for empty lines."""
        assert IgnorePattern.from_line("") is None
        assert IgnorePattern.from_line("   ") is None

    def test_from_line_comment_line(self) -> None:
        """Should return None for comment lines."""
        assert IgnorePattern.from_line("# This is a comment") is None
        assert IgnorePattern.from_line("  # Indented comment") is None

    def test_from_line_inline_comment(self) -> None:
        """Should parse pattern with inline comment."""
        pattern = IgnorePattern.from_line("node_modules/ # Dependencies")

        assert pattern is not None
        assert pattern.pattern == "node_modules/"
        assert pattern.comment == "Dependencies"

    def test_from_line_with_line_number(self) -> None:
        """Should store line number."""
        pattern = IgnorePattern.from_line("*.pyc", line_number=42)

        assert pattern is not None
        assert pattern.line_number == 42


class TestIgnoreConfig:
    """Tests for IgnoreConfig dataclass."""

    def test_default_patterns_included(self) -> None:
        """Should include default patterns by default."""
        config = IgnoreConfig()
        patterns = config.get_raw_patterns()

        assert "node_modules/" in patterns
        assert ".git/" in patterns
        assert "__pycache__/" in patterns

    def test_default_patterns_excluded(self) -> None:
        """Should exclude default patterns when disabled."""
        config = IgnoreConfig(include_defaults=False)
        patterns = config.get_raw_patterns()

        assert len(patterns) == 0

    def test_add_pattern_simple(self) -> None:
        """Should add a pattern at runtime."""
        config = IgnoreConfig(include_defaults=False)
        config.add_pattern("custom_dir/")

        patterns = config.get_raw_patterns()
        assert "custom_dir/" in patterns

    def test_add_pattern_negation(self) -> None:
        """Should handle negation patterns."""
        config = IgnoreConfig(include_defaults=False)
        config.add_pattern("!important.txt")

        patterns = config.get_raw_patterns()
        assert "!important.txt" in patterns

    def test_from_file_parses_correctly(self, tmp_path: Path) -> None:
        """Should parse .contextignore file correctly."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("""
# Comment
node_modules/
*.pyc
!important.pyc

vendor/
        """)

        config = IgnoreConfig.from_file(ignore_file, include_defaults=False)

        assert len(config.patterns) == 4
        assert config.source_file == ignore_file

    def test_from_file_missing(self, tmp_path: Path) -> None:
        """Should return empty patterns for missing file."""
        ignore_file = tmp_path / ".contextignore"

        config = IgnoreConfig.from_file(ignore_file, include_defaults=False)

        assert len(config.patterns) == 0


class TestIgnoreServiceLoad:
    """Tests for IgnoreService.load()."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Should load existing .contextignore file."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("custom_dir/\n")

        service = IgnoreService()
        result = service.load(tmp_path)

        assert isinstance(result, Success)
        # Should have defaults plus custom pattern
        patterns = result.value.get_raw_patterns()
        assert "custom_dir/" in patterns
        assert "node_modules/" in patterns  # default

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Should succeed with defaults when file missing."""
        service = IgnoreService()
        result = service.load(tmp_path)

        # Should still succeed, just with defaults only
        assert isinstance(result, Success)
        assert len(result.value.patterns) == 0  # No file patterns
        # But defaults are included
        patterns = result.value.get_raw_patterns()
        assert "node_modules/" in patterns

    def test_load_or_default_missing_file(self, tmp_path: Path) -> None:
        """Should return defaults when file is missing."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        patterns = config.get_raw_patterns()
        assert "node_modules/" in patterns


class TestIgnoreServiceShouldIgnore:
    """Tests for IgnoreService.should_ignore()."""

    def test_should_ignore_node_modules(self, tmp_path: Path) -> None:
        """Should ignore node_modules contents by default."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        # Files inside node_modules should be ignored
        assert service.should_ignore(Path("node_modules/foo.js"), config) is True
        assert (
            service.should_ignore(Path("node_modules/package/index.js"), config) is True
        )

    def test_should_ignore_pycache(self, tmp_path: Path) -> None:
        """Should ignore __pycache__ by default."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("__pycache__/module.pyc"), config) is True

    def test_should_ignore_pyc_files(self, tmp_path: Path) -> None:
        """Should ignore .pyc files by default."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("module.pyc"), config) is True
        assert service.should_ignore(Path("src/module.pyc"), config) is True

    def test_should_not_ignore_source_files(self, tmp_path: Path) -> None:
        """Should not ignore regular source files."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("src/main.py"), config) is False
        assert service.should_ignore(Path("README.md"), config) is False

    def test_should_ignore_custom_pattern(self, tmp_path: Path) -> None:
        """Should ignore paths matching custom patterns."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("custom_dir/\n")

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("custom_dir/file.txt"), config) is True
        assert service.should_ignore(Path("other_dir/file.txt"), config) is False

    def test_should_ignore_with_absolute_path(self, tmp_path: Path) -> None:
        """Should handle absolute paths correctly."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        abs_path = tmp_path / "node_modules" / "foo.js"
        assert service.should_ignore(abs_path, config, root=tmp_path) is True

    def test_negation_pattern_overrides(self, tmp_path: Path) -> None:
        """Should allow negation patterns to un-ignore files."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("""
*.log
!important.log
        """)

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        # Regular log files should be ignored (from default patterns)
        assert service.should_ignore(Path("debug.log"), config) is True
        # But important.log should not be ignored (negated)
        assert service.should_ignore(Path("important.log"), config) is False


class TestIgnoreServiceFilterPaths:
    """Tests for IgnoreService.filter_paths()."""

    def test_filter_paths_removes_ignored(self, tmp_path: Path) -> None:
        """Should remove ignored paths from list."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        paths = [
            Path("src/main.py"),
            Path("node_modules/package/index.js"),
            Path("README.md"),
            Path("__pycache__/module.pyc"),
        ]

        filtered = service.filter_paths(paths, config)

        assert Path("src/main.py") in filtered
        assert Path("README.md") in filtered
        assert Path("node_modules/package/index.js") not in filtered
        assert Path("__pycache__/module.pyc") not in filtered

    def test_filter_paths_empty_input(self, tmp_path: Path) -> None:
        """Should handle empty path list."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        filtered = service.filter_paths([], config)

        assert filtered == []


class TestIgnoreServiceCheckPath:
    """Tests for IgnoreService.check_path()."""

    def test_check_path_returns_match_info(self, tmp_path: Path) -> None:
        """Should return detailed match information."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        result = service.check_path(Path("node_modules/foo.js"), config)

        assert isinstance(result, IgnoreMatch)
        assert result.ignored is True
        assert result.path == Path("node_modules/foo.js")

    def test_check_path_not_ignored(self, tmp_path: Path) -> None:
        """Should return not ignored for regular files."""
        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        result = service.check_path(Path("src/main.py"), config)

        assert result.ignored is False


class TestIgnoreServiceExists:
    """Tests for IgnoreService.exists()."""

    def test_exists_true(self, tmp_path: Path) -> None:
        """Should return True when .contextignore exists."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("# empty")

        service = IgnoreService()
        assert service.exists(tmp_path) is True

    def test_exists_false(self, tmp_path: Path) -> None:
        """Should return False when .contextignore missing."""
        service = IgnoreService()
        assert service.exists(tmp_path) is False


class TestIgnoreServiceExclusionPatterns:
    """Tests for IgnoreService.get_exclusion_patterns()."""

    def test_get_exclusion_patterns(self, tmp_path: Path) -> None:
        """Should return patterns for external tools."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("custom/\n")

        service = IgnoreService()
        result = service.get_exclusion_patterns(tmp_path)

        assert isinstance(result, Success)
        patterns = result.value
        assert "custom/" in patterns
        assert "node_modules/" in patterns  # default


class TestIgnoreServicePatternMatching:
    """Tests for various pattern matching scenarios."""

    def test_wildcard_pattern(self, tmp_path: Path) -> None:
        """Should match wildcard patterns."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("*.generated.ts\n")

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("api.generated.ts"), config) is True
        assert service.should_ignore(Path("src/types.generated.ts"), config) is True
        assert service.should_ignore(Path("types.ts"), config) is False

    def test_directory_pattern(self, tmp_path: Path) -> None:
        """Should match directory patterns."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("build/\n")

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("build/output.js"), config) is True
        assert service.should_ignore(Path("src/build.py"), config) is False

    def test_double_star_pattern(self, tmp_path: Path) -> None:
        """Should match ** recursive patterns."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("**/test_*.py\n")

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert service.should_ignore(Path("test_main.py"), config) is True
        assert service.should_ignore(Path("tests/test_main.py"), config) is True
        assert service.should_ignore(Path("tests/unit/test_service.py"), config) is True

    def test_monorepo_subproject_pattern(self, tmp_path: Path) -> None:
        """Should match monorepo subproject patterns."""
        ignore_file = tmp_path / ".contextignore"
        ignore_file.write_text("apps/legacy-app/\npackages/deprecated/\n")

        service = IgnoreService()
        config = service.load_or_default(tmp_path)

        assert (
            service.should_ignore(Path("apps/legacy-app/src/main.ts"), config) is True
        )
        assert (
            service.should_ignore(Path("packages/deprecated/index.js"), config) is True
        )
        assert service.should_ignore(Path("apps/new-app/src/main.ts"), config) is False
