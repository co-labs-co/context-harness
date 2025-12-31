"""Storage protocol definition.

Defines the abstract interface that all storage implementations must follow.
This enables dependency injection and easy testing with mock storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List, Optional, Protocol, Union

PathLike = Union[str, Path]


class StorageProtocol(Protocol):
    """Protocol for storage operations.

    This protocol defines the contract for all storage backends.
    Implementations can be filesystem-based, in-memory, cloud-based, etc.

    All path operations are relative to a base path (root).
    Implementations should handle path normalization and validation.

    Example:
        class MyStorage:
            def read(self, path: PathLike) -> Optional[str]:
                ...
            def write(self, path: PathLike, content: str) -> None:
                ...
            # ... implement all methods
    """

    def read(self, path: PathLike) -> Optional[str]:
        """Read content from a path.

        Args:
            path: Relative path to read from

        Returns:
            File content as string, or None if not found
        """
        ...

    def read_bytes(self, path: PathLike) -> Optional[bytes]:
        """Read binary content from a path.

        Args:
            path: Relative path to read from

        Returns:
            File content as bytes, or None if not found
        """
        ...

    def write(self, path: PathLike, content: str, mode: int = 0o644) -> None:
        """Write content to a path.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Content to write
            mode: File permissions (default: 0o644)
        """
        ...

    def write_bytes(self, path: PathLike, content: bytes, mode: int = 0o644) -> None:
        """Write binary content to a path.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Binary content to write
            mode: File permissions (default: 0o644)
        """
        ...

    def delete(self, path: PathLike) -> bool:
        """Delete a file.

        Args:
            path: Relative path to delete

        Returns:
            True if file was deleted, False if not found
        """
        ...

    def exists(self, path: PathLike) -> bool:
        """Check if a path exists.

        Args:
            path: Relative path to check

        Returns:
            True if path exists
        """
        ...

    def is_file(self, path: PathLike) -> bool:
        """Check if path is a file.

        Args:
            path: Relative path to check

        Returns:
            True if path is a file
        """
        ...

    def is_dir(self, path: PathLike) -> bool:
        """Check if path is a directory.

        Args:
            path: Relative path to check

        Returns:
            True if path is a directory
        """
        ...

    def mkdir(self, path: PathLike, mode: int = 0o755, parents: bool = True) -> None:
        """Create a directory.

        Args:
            path: Relative path for directory
            mode: Directory permissions (default: 0o755)
            parents: Create parent directories if needed
        """
        ...

    def rmdir(self, path: PathLike, recursive: bool = False) -> bool:
        """Remove a directory.

        Args:
            path: Relative path to remove
            recursive: Remove contents recursively

        Returns:
            True if directory was removed, False if not found
        """
        ...

    def list_dir(self, path: PathLike = ".") -> List[str]:
        """List contents of a directory.

        Args:
            path: Relative path to list (default: root)

        Returns:
            List of names in directory (not full paths)
        """
        ...

    def glob(self, pattern: str, path: PathLike = ".") -> Iterator[str]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.json", "**/*.py")
            path: Base path for the pattern

        Yields:
            Relative paths matching the pattern
        """
        ...

    def resolve(self, path: PathLike) -> Path:
        """Resolve a relative path to absolute.

        Args:
            path: Relative path

        Returns:
            Absolute Path object
        """
        ...

    @property
    def root(self) -> Path:
        """Get the root/base path for this storage.

        Returns:
            Absolute path to storage root
        """
        ...
