"""In-memory storage implementation.

Provides storage backed by an in-memory dictionary.
Used for testing to avoid filesystem side effects.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath
from typing import Dict, Iterator, List, Optional, Set, Union

PathLike = Union[str, Path]


class MemoryStorage:
    """In-memory storage implementation.

    Implements StorageProtocol using in-memory dictionaries.
    Perfect for unit testing without filesystem side effects.

    Example:
        storage = MemoryStorage()
        storage.write("config.json", '{"key": "value"}')
        assert storage.read("config.json") == '{"key": "value"}'

        # Check file exists
        assert storage.exists("config.json")
        assert storage.is_file("config.json")

        # Delete file
        storage.delete("config.json")
        assert not storage.exists("config.json")

    Attributes:
        _files: Dictionary mapping paths to (content, mode)
        _dirs: Set of directory paths
        _root: Virtual root path
    """

    def __init__(self, root: Optional[PathLike] = None):
        """Initialize memory storage.

        Args:
            root: Virtual root path (defaults to "/memory")
        """
        if root is None:
            self._root = Path("/memory")
        else:
            self._root = Path(root)

        # Files: path -> (content_bytes, mode)
        self._files: Dict[str, tuple[bytes, int]] = {}
        # Directories (including implicit parents)
        self._dirs: Set[str] = {"."}

    @property
    def root(self) -> Path:
        """Get the virtual root path."""
        return self._root

    def _normalize(self, path: PathLike) -> str:
        """Normalize path to string key.

        Args:
            path: Path to normalize

        Returns:
            Normalized path string
        """
        p = PurePosixPath(path)
        # Remove leading slashes and dots
        parts = [part for part in p.parts if part not in ("", "/", ".")]
        if not parts:
            return "."
        return str(PurePosixPath(*parts))

    def _ensure_parent_dirs(self, path: str) -> None:
        """Ensure all parent directories exist.

        Args:
            path: Normalized path
        """
        p = PurePosixPath(path)
        for parent in reversed(p.parents):
            parent_str = str(parent)
            if parent_str and parent_str != ".":
                self._dirs.add(parent_str)

    def resolve(self, path: PathLike) -> Path:
        """Resolve a relative path to absolute.

        Args:
            path: Relative path

        Returns:
            Absolute Path object (virtual)
        """
        return self._root / self._normalize(path)

    def read(self, path: PathLike) -> Optional[str]:
        """Read content from a file.

        Args:
            path: Relative path to read from

        Returns:
            File content as string, or None if not found
        """
        key = self._normalize(path)
        if key in self._files:
            content, _ = self._files[key]
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return None
        return None

    def read_bytes(self, path: PathLike) -> Optional[bytes]:
        """Read binary content from a file.

        Args:
            path: Relative path to read from

        Returns:
            File content as bytes, or None if not found
        """
        key = self._normalize(path)
        if key in self._files:
            content, _ = self._files[key]
            return content
        return None

    def write(self, path: PathLike, content: str, mode: int = 0o644) -> None:
        """Write content to a file.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Content to write
            mode: File permissions (default: 0o644)
        """
        key = self._normalize(path)
        self._ensure_parent_dirs(key)
        self._files[key] = (content.encode("utf-8"), mode)

    def write_bytes(self, path: PathLike, content: bytes, mode: int = 0o644) -> None:
        """Write binary content to a file.

        Creates parent directories if they don't exist.

        Args:
            path: Relative path to write to
            content: Binary content to write
            mode: File permissions (default: 0o644)
        """
        key = self._normalize(path)
        self._ensure_parent_dirs(key)
        self._files[key] = (content, mode)

    def delete(self, path: PathLike) -> bool:
        """Delete a file.

        Args:
            path: Relative path to delete

        Returns:
            True if file was deleted, False if not found
        """
        key = self._normalize(path)
        if key in self._files:
            del self._files[key]
            return True
        return False

    def exists(self, path: PathLike) -> bool:
        """Check if a path exists.

        Args:
            path: Relative path to check

        Returns:
            True if path exists
        """
        key = self._normalize(path)
        return key in self._files or key in self._dirs

    def is_file(self, path: PathLike) -> bool:
        """Check if path is a file.

        Args:
            path: Relative path to check

        Returns:
            True if path is a file
        """
        key = self._normalize(path)
        return key in self._files

    def is_dir(self, path: PathLike) -> bool:
        """Check if path is a directory.

        Args:
            path: Relative path to check

        Returns:
            True if path is a directory
        """
        key = self._normalize(path)
        return key in self._dirs

    def mkdir(self, path: PathLike, mode: int = 0o755, parents: bool = True) -> None:
        """Create a directory.

        Args:
            path: Relative path for directory
            mode: Directory permissions (ignored in memory)
            parents: Create parent directories if needed
        """
        key = self._normalize(path)
        if parents:
            self._ensure_parent_dirs(key)
        self._dirs.add(key)

    def rmdir(self, path: PathLike, recursive: bool = False) -> bool:
        """Remove a directory.

        Args:
            path: Relative path to remove
            recursive: Remove contents recursively

        Returns:
            True if directory was removed, False if not found
        """
        key = self._normalize(path)

        if key not in self._dirs:
            return False

        # Check for contents
        prefix = key + "/" if key != "." else ""
        has_contents = any(f.startswith(prefix) for f in self._files) or any(
            d.startswith(prefix) and d != key for d in self._dirs
        )

        if has_contents and not recursive:
            return False

        if recursive:
            # Remove all files under this directory
            to_remove_files = [f for f in self._files if f.startswith(prefix)]
            for f in to_remove_files:
                del self._files[f]

            # Remove all subdirectories
            to_remove_dirs = [d for d in self._dirs if d.startswith(prefix) or d == key]
            for d in to_remove_dirs:
                self._dirs.discard(d)
        else:
            self._dirs.discard(key)

        return True

    def list_dir(self, path: PathLike = ".") -> List[str]:
        """List contents of a directory.

        Args:
            path: Relative path to list (default: root)

        Returns:
            List of names in directory (not full paths)
        """
        key = self._normalize(path)

        if key != "." and key not in self._dirs:
            return []

        prefix = key + "/" if key != "." else ""
        prefix_len = len(prefix)

        names: Set[str] = set()

        # Files directly in this directory
        for f in self._files:
            if prefix:
                if f.startswith(prefix):
                    rest = f[prefix_len:]
                    # Only direct children (no "/" in rest)
                    if "/" not in rest:
                        names.add(rest)
                    else:
                        # Add immediate subdirectory
                        names.add(rest.split("/")[0])
            else:
                # Root directory
                if "/" not in f:
                    names.add(f)
                else:
                    names.add(f.split("/")[0])

        # Directories directly in this directory
        for d in self._dirs:
            if d == key or d == ".":
                continue
            if prefix:
                if d.startswith(prefix):
                    rest = d[prefix_len:]
                    if "/" not in rest:
                        names.add(rest)
            else:
                if "/" not in d:
                    names.add(d)

        return sorted(names)

    def glob(self, pattern: str, path: PathLike = ".") -> Iterator[str]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.json", "**/*.py")
            path: Base path for the pattern

        Yields:
            Relative paths matching the pattern
        """
        base = self._normalize(path)
        prefix = base + "/" if base != "." else ""

        # Handle ** for recursive matching
        if "**" in pattern:
            # For **/*.ext pattern, we need to match at any depth including root
            # Convert **/*.txt to match both root files and nested files
            for file_path in sorted(self._files.keys()):
                if prefix and not file_path.startswith(prefix):
                    continue
                rel_path = file_path[len(prefix) :] if prefix else file_path

                # Check against the full pattern
                if fnmatch.fnmatch(rel_path, pattern):
                    yield file_path
                # Also check without the **/ prefix for root-level matches
                elif pattern.startswith("**/"):
                    suffix_pattern = pattern[3:]  # Remove **/
                    if fnmatch.fnmatch(rel_path, suffix_pattern):
                        yield file_path
        else:
            # Non-recursive glob
            for file_path in sorted(self._files.keys()):
                if prefix and not file_path.startswith(prefix):
                    continue
                rel_path = file_path[len(prefix) :] if prefix else file_path
                if fnmatch.fnmatch(rel_path, pattern):
                    yield file_path

    def clear(self) -> None:
        """Clear all files and directories.

        Useful for resetting state between tests.
        """
        self._files.clear()
        self._dirs = {"."}

    def snapshot(self) -> Dict[str, str]:
        """Get a snapshot of all file contents.

        Returns:
            Dictionary mapping paths to content (decoded as UTF-8, or
            placeholder for binary content)
        """
        result = {}
        for path, (content, _) in self._files.items():
            # Check if content is valid UTF-8
            try:
                # First try to decode
                decoded = content.decode("utf-8")
                # Also check if it contains non-printable characters (except common ones)
                if all(c.isprintable() or c in "\n\r\t" for c in decoded):
                    result[path] = decoded
                else:
                    result[path] = f"<binary: {len(content)} bytes>"
            except UnicodeDecodeError:
                result[path] = f"<binary: {len(content)} bytes>"
        return result
