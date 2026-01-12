"""Ignore service for ContextHarness.

Provides gitignore-style pattern matching for excluding files and directories
from context scanning. Uses the pathspec library for accurate gitignore
pattern matching.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Protocol

from context_harness.primitives import ErrorCode, Failure, Result, Success
from context_harness.primitives.ignore import IgnoreConfig, IgnoreMatch, IgnorePattern


class PathMatcher(Protocol):
    """Protocol for path matching implementations.

    Allows dependency injection for testing without pathspec.
    """

    def match_file(self, path: str) -> bool:
        """Check if a path matches the ignore patterns.

        Args:
            path: Relative path to check (forward slashes)

        Returns:
            True if the path should be ignored
        """
        ...


class PathSpecMatcher:
    """Default path matcher using pathspec library.

    Uses pathspec's gitignore pattern for accurate gitignore matching.
    """

    def __init__(self, patterns: List[str]):
        """Initialize matcher with patterns.

        Args:
            patterns: List of gitignore-style patterns
        """
        try:
            import pathspec

            # Use 'gitignore' style which is the modern, non-deprecated option
            self._spec = pathspec.PathSpec.from_lines("gitignore", patterns)
        except ImportError:
            raise ImportError(
                "pathspec library is required for .contextignore support. "
                "Install it with: pip install pathspec"
            )

    def match_file(self, path: str) -> bool:
        """Check if a path matches the ignore patterns.

        Args:
            path: Relative path to check (forward slashes)

        Returns:
            True if the path should be ignored
        """
        return self._spec.match_file(path)


class FnmatchMatcher:
    """Fallback path matcher using fnmatch.

    Less accurate than pathspec but works without external dependencies.
    Use this when pathspec is not available.
    """

    def __init__(self, patterns: List[str]):
        """Initialize matcher with patterns.

        Args:
            patterns: List of gitignore-style patterns
        """
        import fnmatch

        self._patterns = patterns
        self._fnmatch = fnmatch

    def match_file(self, path: str) -> bool:
        """Check if a path matches the ignore patterns.

        Args:
            path: Relative path to check (forward slashes)

        Returns:
            True if the path should be ignored
        """
        # Track whether path is ignored (can be toggled by negation patterns)
        ignored = False

        for pattern in self._patterns:
            is_negation = pattern.startswith("!")
            check_pattern = pattern[1:] if is_negation else pattern

            # Convert gitignore pattern to fnmatch pattern
            match_pattern = check_pattern

            # Handle directory-specific patterns
            if check_pattern.endswith("/"):
                # Match both the directory and its contents
                check_pattern = check_pattern.rstrip("/")
                if self._matches(path, check_pattern) or self._matches(
                    path, f"{check_pattern}/*"
                ):
                    ignored = not is_negation
            else:
                # Standard pattern
                if self._matches(path, check_pattern):
                    ignored = not is_negation

        return ignored

    def _matches(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern using fnmatch rules.

        Args:
            path: Path to check
            pattern: Pattern to match against

        Returns:
            True if path matches pattern
        """
        # Check direct match
        if self._fnmatch.fnmatch(path, pattern):
            return True

        # Check if pattern matches any path component
        if "/" not in pattern:
            for component in path.split("/"):
                if self._fnmatch.fnmatch(component, pattern):
                    return True

        # Check if pattern should match at any level
        if not pattern.startswith("/") and "/" not in pattern:
            # Pattern like "*.pyc" should match at any depth
            if self._fnmatch.fnmatch(path.split("/")[-1], pattern):
                return True

        return False


class IgnoreService:
    """Service for managing and applying ignore patterns.

    Handles loading .contextignore files and checking paths against patterns.

    Example:
        service = IgnoreService()
        result = service.load(Path("/project"))
        if isinstance(result, Success):
            config = result.value
            if service.should_ignore(Path("node_modules/foo.js"), config):
                print("Ignoring node_modules/foo.js")
    """

    # Default name for the ignore file
    IGNORE_FILE_NAME = ".contextignore"

    def __init__(self, matcher: Optional[PathMatcher] = None):
        """Initialize the ignore service.

        Args:
            matcher: Custom path matcher. If None, uses PathSpecMatcher.
        """
        self._custom_matcher = matcher
        self._cached_matchers: dict[int, PathMatcher] = {}

    def load(
        self,
        project_path: Optional[Path] = None,
        include_defaults: bool = True,
    ) -> Result[IgnoreConfig]:
        """Load ignore configuration from a project directory.

        Args:
            project_path: Project root directory. Uses CWD if None.
            include_defaults: Whether to include default patterns

        Returns:
            Result containing IgnoreConfig
        """
        root = project_path or Path.cwd()
        ignore_file = root / self.IGNORE_FILE_NAME

        try:
            config = IgnoreConfig.from_file(
                ignore_file, include_defaults=include_defaults
            )
            return Success(value=config)
        except PermissionError:
            return Failure(
                error=f"Permission denied reading: {ignore_file}",
                code=ErrorCode.PERMISSION_DENIED,
                details={"path": str(ignore_file)},
            )
        except Exception as e:
            return Failure(
                error=f"Error loading ignore file: {e}",
                code=ErrorCode.UNKNOWN,
                details={"path": str(ignore_file), "error": str(e)},
            )

    def load_or_default(
        self,
        project_path: Optional[Path] = None,
        include_defaults: bool = True,
    ) -> IgnoreConfig:
        """Load ignore config, returning defaults if file doesn't exist.

        Args:
            project_path: Project root directory. Uses CWD if None.
            include_defaults: Whether to include default patterns

        Returns:
            IgnoreConfig (from file or defaults)
        """
        result = self.load(project_path, include_defaults)
        if isinstance(result, Success):
            return result.value
        # Return default config on any error
        return IgnoreConfig(include_defaults=include_defaults)

    def _get_matcher(self, config: IgnoreConfig) -> PathMatcher:
        """Get or create a matcher for the given config.

        Args:
            config: Ignore configuration

        Returns:
            PathMatcher for the configuration
        """
        if self._custom_matcher:
            return self._custom_matcher

        # Use config's pattern list hash as cache key
        patterns = config.get_raw_patterns()
        cache_key = hash(tuple(patterns))

        if cache_key not in self._cached_matchers:
            try:
                self._cached_matchers[cache_key] = PathSpecMatcher(patterns)
            except ImportError:
                # Fallback to fnmatch if pathspec not available
                self._cached_matchers[cache_key] = FnmatchMatcher(patterns)

        return self._cached_matchers[cache_key]

    def should_ignore(
        self,
        path: Path,
        config: IgnoreConfig,
        root: Optional[Path] = None,
    ) -> bool:
        """Check if a path should be ignored.

        Args:
            path: Path to check (can be relative or absolute)
            config: Ignore configuration to apply
            root: Root directory for relative path calculation

        Returns:
            True if the path should be ignored
        """
        # Convert to relative path string with forward slashes
        if path.is_absolute() and root:
            try:
                rel_path = path.relative_to(root)
            except ValueError:
                # Path is not under root
                return False
        else:
            rel_path = path

        # Normalize path separators for consistent matching
        path_str = str(rel_path).replace("\\", "/")

        # Get matcher and check
        matcher = self._get_matcher(config)
        return matcher.match_file(path_str)

    def filter_paths(
        self,
        paths: Iterable[Path],
        config: IgnoreConfig,
        root: Optional[Path] = None,
    ) -> List[Path]:
        """Filter a list of paths, removing ignored ones.

        Args:
            paths: Paths to filter
            config: Ignore configuration to apply
            root: Root directory for relative path calculation

        Returns:
            List of paths that are NOT ignored
        """
        return [p for p in paths if not self.should_ignore(p, config, root)]

    def check_path(
        self,
        path: Path,
        config: IgnoreConfig,
        root: Optional[Path] = None,
    ) -> IgnoreMatch:
        """Check a path and return detailed match information.

        Args:
            path: Path to check
            config: Ignore configuration to apply
            root: Root directory for relative path calculation

        Returns:
            IgnoreMatch with details about the match
        """
        ignored = self.should_ignore(path, config, root)

        # Find the matching pattern for detailed reporting
        matched_pattern: Optional[IgnorePattern] = None
        negated_by: Optional[IgnorePattern] = None

        if ignored:
            # Try to find which pattern caused the match
            for pattern in config.get_all_patterns():
                if not pattern.negation:
                    # Check if this pattern matches
                    # (simplified - full implementation would track this during matching)
                    matched_pattern = pattern
                    break

        return IgnoreMatch(
            path=path,
            ignored=ignored,
            matched_pattern=matched_pattern,
            negated_by=negated_by,
        )

    def exists(self, project_path: Optional[Path] = None) -> bool:
        """Check if a .contextignore file exists.

        Args:
            project_path: Project root directory. Uses CWD if None.

        Returns:
            True if .contextignore file exists
        """
        root = project_path or Path.cwd()
        return (root / self.IGNORE_FILE_NAME).exists()

    def get_exclusion_patterns(
        self,
        project_path: Optional[Path] = None,
        include_defaults: bool = True,
    ) -> Result[List[str]]:
        """Get exclusion patterns for use with external tools.

        Returns patterns suitable for passing to glob, grep, or find.

        Args:
            project_path: Project root directory. Uses CWD if None.
            include_defaults: Whether to include default patterns

        Returns:
            Result containing list of pattern strings
        """
        config = self.load_or_default(project_path, include_defaults)
        return Success(value=config.get_raw_patterns())
