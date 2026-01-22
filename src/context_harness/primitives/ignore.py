"""Ignore pattern primitives for ContextHarness.

Provides dataclasses for managing .contextignore files, which allow users
to exclude directories and files from context scanning (similar to .gitignore).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class IgnoreSource(Enum):
    """Source of ignore patterns."""

    CONTEXTIGNORE_FILE = "contextignore_file"  # From .contextignore file
    DEFAULT = "default"  # Built-in defaults
    RUNTIME = "runtime"  # Added programmatically


@dataclass(frozen=True)
class IgnorePattern:
    """A single ignore pattern entry.

    Attributes:
        pattern: The gitignore-style pattern (e.g., "node_modules/", "*.pyc")
        source: Where this pattern came from
        line_number: Line number in source file (if from file)
        comment: Optional comment explaining the pattern
        negation: True if this is a negation pattern (starts with !)
    """

    pattern: str
    source: IgnoreSource = IgnoreSource.DEFAULT
    line_number: Optional[int] = None
    comment: Optional[str] = None
    negation: bool = False

    @classmethod
    def from_line(
        cls,
        line: str,
        source: IgnoreSource = IgnoreSource.CONTEXTIGNORE_FILE,
        line_number: Optional[int] = None,
    ) -> Optional["IgnorePattern"]:
        """Parse a pattern from a line in an ignore file.

        Args:
            line: Raw line from ignore file
            source: Source of the pattern
            line_number: Line number in source file

        Returns:
            IgnorePattern or None if line is empty/comment
        """
        # Strip trailing whitespace but preserve leading for patterns
        stripped = line.rstrip()

        # Skip empty lines
        if not stripped:
            return None

        # Skip comment lines
        if stripped.startswith("#"):
            return None

        # Handle inline comments (not standard gitignore but useful)
        # Only if there's a space before the #
        pattern = stripped
        comment = None
        if " #" in pattern:
            parts = pattern.split(" #", 1)
            pattern = parts[0].rstrip()
            comment = parts[1].strip()

        # Check for negation
        negation = False
        if pattern.startswith("!"):
            negation = True
            pattern = pattern[1:]

        # Skip if pattern is now empty
        if not pattern:
            return None

        return cls(
            pattern=pattern,
            source=source,
            line_number=line_number,
            comment=comment,
            negation=negation,
        )


@dataclass
class IgnoreConfig:
    """Configuration for ignore patterns.

    Manages a collection of patterns from multiple sources.

    Attributes:
        patterns: List of ignore patterns
        source_file: Path to the .contextignore file (if loaded from file)
        include_defaults: Whether to include default patterns
    """

    patterns: List[IgnorePattern] = field(default_factory=list)
    source_file: Optional[Path] = None
    include_defaults: bool = True

    # Default patterns that are always applied unless disabled
    DEFAULT_PATTERNS: List[str] = field(
        default_factory=lambda: [
            # Version control
            ".git/",
            ".svn/",
            ".hg/",
            # Dependencies
            "node_modules/",
            "vendor/",
            ".venv/",
            "venv/",
            "__pycache__/",
            "*.pyc",
            "*.pyo",
            # Build artifacts
            "dist/",
            "build/",
            ".next/",
            ".nuxt/",
            "out/",
            "target/",
            # Cache directories
            ".pytest_cache/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".cache/",
            ".parcel-cache/",
            # IDE directories
            ".idea/",
            ".vscode/",
            "*.swp",
            "*.swo",
            # Logs and temporary files
            "*.log",
            "logs/",
            "tmp/",
            "temp/",
            # Coverage and test output
            "coverage/",
            ".coverage",
            "htmlcov/",
            # OS files
            ".DS_Store",
            "Thumbs.db",
            # Lock files (usually large and not useful for context)
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "poetry.lock",
            "uv.lock",
            "Cargo.lock",
            "Gemfile.lock",
            "composer.lock",
        ],
        init=False,
    )

    def get_all_patterns(self) -> List[IgnorePattern]:
        """Get all patterns including defaults if enabled.

        Returns:
            List of all IgnorePattern objects to apply
        """
        all_patterns: List[IgnorePattern] = []

        # Add defaults first (can be overridden with negation patterns)
        if self.include_defaults:
            for pattern in self.DEFAULT_PATTERNS:
                all_patterns.append(
                    IgnorePattern(pattern=pattern, source=IgnoreSource.DEFAULT)
                )

        # Add explicit patterns (may include negations to override defaults)
        all_patterns.extend(self.patterns)

        return all_patterns

    def get_raw_patterns(self) -> List[str]:
        """Get pattern strings for pathspec matching.

        Returns:
            List of pattern strings in order of precedence
        """
        patterns = []

        # Add defaults first
        if self.include_defaults:
            patterns.extend(self.DEFAULT_PATTERNS)

        # Add explicit patterns
        for p in self.patterns:
            if p.negation:
                patterns.append(f"!{p.pattern}")
            else:
                patterns.append(p.pattern)

        return patterns

    @classmethod
    def from_file(cls, path: Path, include_defaults: bool = True) -> "IgnoreConfig":
        """Load ignore configuration from a .contextignore file.

        Args:
            path: Path to the .contextignore file
            include_defaults: Whether to include default patterns

        Returns:
            IgnoreConfig with patterns from file
        """
        patterns: List[IgnorePattern] = []

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    pattern = IgnorePattern.from_line(
                        line,
                        source=IgnoreSource.CONTEXTIGNORE_FILE,
                        line_number=line_num,
                    )
                    if pattern:
                        patterns.append(pattern)

        return cls(
            patterns=patterns,
            source_file=path,
            include_defaults=include_defaults,
        )

    def add_pattern(
        self,
        pattern: str,
        source: IgnoreSource = IgnoreSource.RUNTIME,
        comment: Optional[str] = None,
    ) -> None:
        """Add a pattern at runtime.

        Args:
            pattern: The gitignore-style pattern
            source: Source of the pattern
            comment: Optional comment
        """
        negation = pattern.startswith("!")
        if negation:
            pattern = pattern[1:]

        self.patterns.append(
            IgnorePattern(
                pattern=pattern,
                source=source,
                comment=comment,
                negation=negation,
            )
        )


@dataclass(frozen=True)
class IgnoreMatch:
    """Result of checking if a path matches ignore patterns.

    Attributes:
        path: The path that was checked
        ignored: Whether the path should be ignored
        matched_pattern: The pattern that matched (if any)
        negated_by: Pattern that negated a previous match (if any)
    """

    path: Path
    ignored: bool
    matched_pattern: Optional[IgnorePattern] = None
    negated_by: Optional[IgnorePattern] = None
