"""Tests for MemoryStorage.

Tests the in-memory storage implementation used for testing.
"""

from context_harness.storage import MemoryStorage


class TestMemoryStorageBasics:
    """Test basic read/write operations."""

    def test_write_and_read(self) -> None:
        """Test basic write and read."""
        storage = MemoryStorage()
        storage.write("test.txt", "hello world")

        assert storage.read("test.txt") == "hello world"

    def test_read_nonexistent(self) -> None:
        """Test reading a file that doesn't exist."""
        storage = MemoryStorage()

        assert storage.read("nonexistent.txt") is None

    def test_write_bytes_and_read_bytes(self) -> None:
        """Test binary write and read."""
        storage = MemoryStorage()
        content = b"\x00\x01\x02\x03"
        storage.write_bytes("binary.dat", content)

        assert storage.read_bytes("binary.dat") == content

    def test_read_bytes_nonexistent(self) -> None:
        """Test reading binary from nonexistent file."""
        storage = MemoryStorage()

        assert storage.read_bytes("nonexistent.dat") is None

    def test_write_creates_parent_dirs(self) -> None:
        """Test that write creates parent directories."""
        storage = MemoryStorage()
        storage.write("a/b/c/file.txt", "content")

        assert storage.exists("a")
        assert storage.exists("a/b")
        assert storage.exists("a/b/c")
        assert storage.is_dir("a/b/c")
        assert storage.is_file("a/b/c/file.txt")

    def test_overwrite_existing(self) -> None:
        """Test overwriting an existing file."""
        storage = MemoryStorage()
        storage.write("test.txt", "original")
        storage.write("test.txt", "updated")

        assert storage.read("test.txt") == "updated"


class TestMemoryStorageDelete:
    """Test delete operations."""

    def test_delete_existing_file(self) -> None:
        """Test deleting an existing file."""
        storage = MemoryStorage()
        storage.write("test.txt", "content")

        assert storage.delete("test.txt") is True
        assert storage.exists("test.txt") is False

    def test_delete_nonexistent_file(self) -> None:
        """Test deleting a file that doesn't exist."""
        storage = MemoryStorage()

        assert storage.delete("nonexistent.txt") is False


class TestMemoryStorageExists:
    """Test exists, is_file, and is_dir operations."""

    def test_exists_file(self) -> None:
        """Test exists returns True for files."""
        storage = MemoryStorage()
        storage.write("test.txt", "content")

        assert storage.exists("test.txt") is True

    def test_exists_dir(self) -> None:
        """Test exists returns True for directories."""
        storage = MemoryStorage()
        storage.mkdir("testdir")

        assert storage.exists("testdir") is True

    def test_exists_nonexistent(self) -> None:
        """Test exists returns False for nonexistent paths."""
        storage = MemoryStorage()

        assert storage.exists("nonexistent") is False

    def test_is_file_true(self) -> None:
        """Test is_file returns True for files."""
        storage = MemoryStorage()
        storage.write("test.txt", "content")

        assert storage.is_file("test.txt") is True

    def test_is_file_false_for_dir(self) -> None:
        """Test is_file returns False for directories."""
        storage = MemoryStorage()
        storage.mkdir("testdir")

        assert storage.is_file("testdir") is False

    def test_is_dir_true(self) -> None:
        """Test is_dir returns True for directories."""
        storage = MemoryStorage()
        storage.mkdir("testdir")

        assert storage.is_dir("testdir") is True

    def test_is_dir_false_for_file(self) -> None:
        """Test is_dir returns False for files."""
        storage = MemoryStorage()
        storage.write("test.txt", "content")

        assert storage.is_dir("test.txt") is False


class TestMemoryStorageDirectories:
    """Test directory operations."""

    def test_mkdir(self) -> None:
        """Test creating a directory."""
        storage = MemoryStorage()
        storage.mkdir("newdir")

        assert storage.is_dir("newdir") is True

    def test_mkdir_nested(self) -> None:
        """Test creating nested directories."""
        storage = MemoryStorage()
        storage.mkdir("a/b/c")

        assert storage.is_dir("a") is True
        assert storage.is_dir("a/b") is True
        assert storage.is_dir("a/b/c") is True

    def test_rmdir_empty(self) -> None:
        """Test removing an empty directory."""
        storage = MemoryStorage()
        storage.mkdir("emptydir")

        assert storage.rmdir("emptydir") is True
        assert storage.exists("emptydir") is False

    def test_rmdir_nonempty_fails(self) -> None:
        """Test removing a non-empty directory fails without recursive."""
        storage = MemoryStorage()
        storage.write("dir/file.txt", "content")

        assert storage.rmdir("dir") is False
        assert storage.exists("dir") is True

    def test_rmdir_recursive(self) -> None:
        """Test removing a directory recursively."""
        storage = MemoryStorage()
        storage.write("dir/subdir/file.txt", "content")
        storage.write("dir/other.txt", "content")

        assert storage.rmdir("dir", recursive=True) is True
        assert storage.exists("dir") is False
        assert storage.exists("dir/subdir/file.txt") is False
        assert storage.exists("dir/other.txt") is False

    def test_rmdir_nonexistent(self) -> None:
        """Test removing a nonexistent directory."""
        storage = MemoryStorage()

        assert storage.rmdir("nonexistent") is False


class TestMemoryStorageListDir:
    """Test list_dir operations."""

    def test_list_dir_empty(self) -> None:
        """Test listing an empty directory."""
        storage = MemoryStorage()
        storage.mkdir("emptydir")

        assert storage.list_dir("emptydir") == []

    def test_list_dir_with_files(self) -> None:
        """Test listing a directory with files."""
        storage = MemoryStorage()
        storage.write("dir/a.txt", "a")
        storage.write("dir/b.txt", "b")
        storage.write("dir/c.txt", "c")

        result = storage.list_dir("dir")
        assert sorted(result) == ["a.txt", "b.txt", "c.txt"]

    def test_list_dir_with_subdirs(self) -> None:
        """Test listing a directory with subdirectories."""
        storage = MemoryStorage()
        storage.write("dir/file.txt", "content")
        storage.mkdir("dir/subdir")

        result = storage.list_dir("dir")
        assert sorted(result) == ["file.txt", "subdir"]

    def test_list_dir_root(self) -> None:
        """Test listing the root directory."""
        storage = MemoryStorage()
        storage.write("file.txt", "content")
        storage.mkdir("dir")

        result = storage.list_dir()
        assert "file.txt" in result
        assert "dir" in result

    def test_list_dir_nonexistent(self) -> None:
        """Test listing a nonexistent directory."""
        storage = MemoryStorage()

        assert storage.list_dir("nonexistent") == []


class TestMemoryStorageGlob:
    """Test glob operations."""

    def test_glob_simple_pattern(self) -> None:
        """Test simple glob pattern."""
        storage = MemoryStorage()
        storage.write("a.txt", "a")
        storage.write("b.txt", "b")
        storage.write("c.json", "c")

        result = list(storage.glob("*.txt"))
        assert sorted(result) == ["a.txt", "b.txt"]

    def test_glob_recursive(self) -> None:
        """Test recursive glob pattern."""
        storage = MemoryStorage()
        storage.write("root.txt", "root")
        storage.write("a/file.txt", "a")
        storage.write("a/b/deep.txt", "deep")

        result = list(storage.glob("**/*.txt"))
        assert sorted(result) == ["a/b/deep.txt", "a/file.txt", "root.txt"]

    def test_glob_no_matches(self) -> None:
        """Test glob with no matches."""
        storage = MemoryStorage()
        storage.write("file.txt", "content")

        result = list(storage.glob("*.json"))
        assert result == []


class TestMemoryStorageUtilities:
    """Test utility methods."""

    def test_resolve(self) -> None:
        """Test path resolution."""
        storage = MemoryStorage()

        resolved = storage.resolve("some/path")
        assert str(resolved).endswith("some/path")

    def test_root_property(self) -> None:
        """Test root property."""
        storage = MemoryStorage()

        assert storage.root is not None

    def test_clear(self) -> None:
        """Test clearing storage."""
        storage = MemoryStorage()
        storage.write("file1.txt", "content1")
        storage.write("dir/file2.txt", "content2")
        storage.mkdir("emptydir")

        storage.clear()

        assert storage.exists("file1.txt") is False
        assert storage.exists("dir/file2.txt") is False
        # Root dir should still exist
        assert storage.is_dir(".") is True

    def test_snapshot(self) -> None:
        """Test getting a snapshot of contents."""
        storage = MemoryStorage()
        storage.write("a.txt", "content a")
        storage.write("b.txt", "content b")

        snapshot = storage.snapshot()

        assert snapshot == {
            "a.txt": "content a",
            "b.txt": "content b",
        }

    def test_snapshot_binary_files(self) -> None:
        """Test snapshot with binary files."""
        storage = MemoryStorage()
        storage.write_bytes("binary.dat", b"\x00\x01\x02")

        snapshot = storage.snapshot()

        assert "binary.dat" in snapshot
        assert "binary" in snapshot["binary.dat"]


class TestMemoryStorageEdgeCases:
    """Test edge cases and special scenarios."""

    def test_path_normalization(self) -> None:
        """Test path normalization."""
        storage = MemoryStorage()
        storage.write("./file.txt", "content")

        assert storage.read("file.txt") == "content"
        assert storage.read("./file.txt") == "content"

    def test_unicode_content(self) -> None:
        """Test unicode content handling."""
        storage = MemoryStorage()
        content = "Hello 世界 🌍"
        storage.write("unicode.txt", content)

        assert storage.read("unicode.txt") == content

    def test_large_content(self) -> None:
        """Test handling large content."""
        storage = MemoryStorage()
        content = "x" * 1000000  # 1MB
        storage.write("large.txt", content)

        assert storage.read("large.txt") == content

    def test_empty_content(self) -> None:
        """Test empty content."""
        storage = MemoryStorage()
        storage.write("empty.txt", "")

        assert storage.read("empty.txt") == ""
        assert storage.exists("empty.txt") is True

    def test_custom_root(self) -> None:
        """Test custom root path."""
        storage = MemoryStorage(root="/custom/root")
        storage.write("file.txt", "content")

        resolved = storage.resolve("file.txt")
        assert "/custom/root" in str(resolved)
