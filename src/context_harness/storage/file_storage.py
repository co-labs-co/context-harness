"""File-based storage implementation.

Provides filesystem storage backed by the real filesystem.
Used in production for actual file operations.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator, List, Optional, Union

PathLike = Union[str, Path]


class FileStorage:
    """File system storage implementation.

    Implements StorageProtocol using the real filesystem.
    All operations are relative to a configurable root path.

    Example:
        # Storage rooted at home directory
        storage = FileStorage(Path.home())
        storage.write(".context-harness/config.json", '{"key": "value"}')

        # Storage rooted at current directory
        storage = FileStorage()
        storage.write("data/file.txt", "content")

    Attributes:
        _root: Base path for all operations
    """

    def __init__(self, root: Optional[PathLike] = None):
        """Initialize file storage.

        Args:
            root: Base path for storage (defaults to current directory)
        """
        if root is None:
            self._root = Path.cwd()
        else:
            self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        """Get the root path."""
        return self._root

    def _resolve(self, path: PathLike) -> Path:
        """Resolve relative path to absolute.

        Args:
            path: Relative or absolute path

        Returns:
            Absolute path under root
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return self._root / p

    def resolve(self, path: PathLike) -> Path:
        """Resolve a relative path to absolute.

        Args:
            path: Relative path

        Returns:
            Absolute Path object
        """
        return self._resolve(path)

    def read(self, path: PathLike) -> Optional[str]:
        """Read content from a file.

        Args:
            path: Relative path to read from

        Returns:
            File content as string, or None if not found
        """
        full_path = self._resolve(path)
        try:
            return full_path.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError):
            return None
        except PermissionError:
            return None

    def read_bytes(self, path: PathLike) -> Optional[bytes]:
        """Read binary content from a file.

        Args:
            path: Relative path to read from

        Returns:
            File content as bytes, or None if not found
        """
        full_path = self._resolve(path)
        try:
            return full_path.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            return None
        except PermissionError:
            return None

    def write(self, path: PathLike, content: str, mode: int = 0o644) -> None:
        """Write content to a file.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Content to write
            mode: File permissions (default: 0o644)
        """
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        full_path.chmod(mode)

    def write_bytes(self, path: PathLike, content: bytes, mode: int = 0o644) -> None:
        """Write binary content to a file.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Binary content to write
            mode: File permissions (default: 0o644)
        """
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        full_path.chmod(mode)

    def delete(self, path: PathLike) -> bool:
        """Delete a file.

        Args:
            path: Relative path to delete

        Returns:
            True if file was deleted, False if not found
        """
        full_path = self._resolve(path)
        try:
            full_path.unlink()
            return True
        except FileNotFoundError:
            return False
        except IsADirectoryError:
            return False

    def exists(self, path: PathLike) -> bool:
        """Check if a path exists.

        Args:
            path: Relative path to check

        Returns:
            True if path exists
        """
        return self._resolve(path).exists()

    def is_file(self, path: PathLike) -> bool:
        """Check if path is a file.

        Args:
            path: Relative path to check

        Returns:
            True if path is a file
        """
        return self._resolve(path).is_file()

    def is_dir(self, path: PathLike) -> bool:
        """Check if path is a directory.

        Args:
            path: Relative path to check

        Returns:
            True if path is a directory
        """
        return self._resolve(path).is_dir()

    def mkdir(self, path: PathLike, mode: int = 0o755, parents: bool = True) -> None:
        """Create a directory.

        Args:
            path: Relative path for directory
            mode: Directory permissions (default: 0o755)
            parents: Create parent directories if needed
        """
        full_path = self._resolve(path)
        full_path.mkdir(mode=mode, parents=parents, exist_ok=True)

    def rmdir(self, path: PathLike, recursive: bool = False) -> bool:
        """Remove a directory.

        Args:
            path: Relative path to remove
            recursive: Remove contents recursively

        Returns:
            True if directory was removed, False if not found
        """
        full_path = self._resolve(path)
        try:
            if recursive:
                shutil.rmtree(full_path)
            else:
                full_path.rmdir()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            # Directory not empty (when not recursive)
            return False

    def list_dir(self, path: PathLike = ".") -> List[str]:
        """List contents of a directory.

        Args:
            path: Relative path to list (default: root)

        Returns:
            List of names in directory (not full paths)
        """
        full_path = self._resolve(path)
        try:
            return [item.name for item in full_path.iterdir()]
        except (FileNotFoundError, NotADirectoryError):
            return []

    def glob(self, pattern: str, path: PathLike = ".") -> Iterator[str]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.json", "**/*.py")
            path: Base path for the pattern

        Yields:
            Relative paths matching the pattern
        """
        full_path = self._resolve(path)
        try:
            for match in full_path.glob(pattern):
                # Return path relative to root
                try:
                    yield str(match.relative_to(self._root))
                except ValueError:
                    # Match is outside root, yield absolute path
                    yield str(match)
        except (FileNotFoundError, NotADirectoryError):
            return
