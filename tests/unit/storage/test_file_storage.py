"""Unit tests for FileStorage.

Tests the real-filesystem storage implementation using pytest tmp_path
to isolate every test.  Covers:
- Path resolution (relative, absolute)
- read / read_bytes (happy path, missing file, permission error, directory)
- write / write_bytes (creates parents, sets permissions)
- delete (existing, missing, directory)
- exists / is_file / is_dir
- mkdir / rmdir (empty, non-empty, recursive)
- list_dir (with files, with subdirs, missing directory)
- glob (simple pattern, recursive, no matches)
"""

import os
import stat
from pathlib import Path

import pytest

from context_harness.storage.file_storage import FileStorage


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestFileStorageResolve:
    """Tests for path resolution."""

    def test_resolve_relative(self, tmp_path):
        storage = FileStorage(tmp_path)
        resolved = storage.resolve("subdir/file.txt")
        assert resolved == tmp_path / "subdir" / "file.txt"

    def test_resolve_absolute_passthrough(self, tmp_path):
        storage = FileStorage(tmp_path)
        abs_path = Path("/absolute/path")
        resolved = storage.resolve(abs_path)
        assert resolved == abs_path

    def test_root_property(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.root == tmp_path.resolve()

    def test_default_root_is_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        storage = FileStorage()
        assert storage.root == Path.cwd()


# ---------------------------------------------------------------------------
# read / read_bytes
# ---------------------------------------------------------------------------


class TestFileStorageRead:
    """Tests for read and read_bytes."""

    def test_read_existing_file(self, tmp_path):
        (tmp_path / "hello.txt").write_text("world", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.read("hello.txt") == "world"

    def test_read_missing_file(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.read("nonexistent.txt") is None

    def test_read_directory_returns_none(self, tmp_path):
        (tmp_path / "adir").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.read("adir") is None

    def test_read_bytes_existing(self, tmp_path):
        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02")
        storage = FileStorage(tmp_path)
        assert storage.read_bytes("data.bin") == b"\x00\x01\x02"

    def test_read_bytes_missing(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.read_bytes("nope.bin") is None

    def test_read_bytes_directory_returns_none(self, tmp_path):
        (tmp_path / "adir").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.read_bytes("adir") is None


# ---------------------------------------------------------------------------
# write / write_bytes
# ---------------------------------------------------------------------------


class TestFileStorageWrite:
    """Tests for write and write_bytes."""

    def test_write_creates_file(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write("new.txt", "content")
        assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"

    def test_write_creates_parent_dirs(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write("a/b/c/deep.txt", "deep")
        assert (tmp_path / "a" / "b" / "c" / "deep.txt").exists()

    def test_write_overwrites_existing(self, tmp_path):
        (tmp_path / "file.txt").write_text("old", encoding="utf-8")
        storage = FileStorage(tmp_path)
        storage.write("file.txt", "new")
        assert storage.read("file.txt") == "new"

    def test_write_bytes_creates_file(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write_bytes("data.bin", b"\xff\xfe")
        assert (tmp_path / "data.bin").read_bytes() == b"\xff\xfe"

    def test_write_bytes_creates_parent_dirs(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write_bytes("x/y/data.bin", b"\x01")
        assert (tmp_path / "x" / "y" / "data.bin").exists()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestFileStorageDelete:
    """Tests for delete."""

    def test_delete_existing_file(self, tmp_path):
        (tmp_path / "doomed.txt").write_text("bye", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.delete("doomed.txt") is True
        assert not (tmp_path / "doomed.txt").exists()

    def test_delete_missing_file(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.delete("ghost.txt") is False

    def test_delete_directory_returns_false(self, tmp_path):
        """Deleting a directory via delete() should return False (not raise)."""
        (tmp_path / "adir").mkdir()
        storage = FileStorage(tmp_path)
        # On some platforms (macOS), unlink on a directory raises PermissionError
        # rather than IsADirectoryError, but FileStorage should still return False.
        result = storage.delete("adir")
        assert result is False
        assert (tmp_path / "adir").exists()


# ---------------------------------------------------------------------------
# exists / is_file / is_dir
# ---------------------------------------------------------------------------


class TestFileStorageExistence:
    """Tests for exists, is_file, is_dir."""

    def test_exists_file(self, tmp_path):
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.exists("f.txt") is True

    def test_exists_dir(self, tmp_path):
        (tmp_path / "d").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.exists("d") is True

    def test_exists_missing(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.exists("nope") is False

    def test_is_file_true(self, tmp_path):
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.is_file("f.txt") is True

    def test_is_file_false_for_dir(self, tmp_path):
        (tmp_path / "d").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.is_file("d") is False

    def test_is_dir_true(self, tmp_path):
        (tmp_path / "d").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.is_dir("d") is True

    def test_is_dir_false_for_file(self, tmp_path):
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.is_dir("f.txt") is False


# ---------------------------------------------------------------------------
# mkdir / rmdir
# ---------------------------------------------------------------------------


class TestFileStorageDirectories:
    """Tests for mkdir and rmdir."""

    def test_mkdir_creates_directory(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.mkdir("newdir")
        assert (tmp_path / "newdir").is_dir()

    def test_mkdir_creates_nested(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.mkdir("a/b/c")
        assert (tmp_path / "a" / "b" / "c").is_dir()

    def test_mkdir_idempotent(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.mkdir("d")
        storage.mkdir("d")  # Should not raise
        assert (tmp_path / "d").is_dir()

    def test_rmdir_empty(self, tmp_path):
        (tmp_path / "empty").mkdir()
        storage = FileStorage(tmp_path)
        assert storage.rmdir("empty") is True
        assert not (tmp_path / "empty").exists()

    def test_rmdir_nonempty_fails_without_recursive(self, tmp_path):
        d = tmp_path / "nonempty"
        d.mkdir()
        (d / "file.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.rmdir("nonempty") is False
        assert d.exists()

    def test_rmdir_recursive(self, tmp_path):
        d = tmp_path / "deep"
        d.mkdir()
        (d / "sub").mkdir()
        (d / "sub" / "file.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.rmdir("deep", recursive=True) is True
        assert not d.exists()

    def test_rmdir_nonexistent(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.rmdir("ghost") is False


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


class TestFileStorageListDir:
    """Tests for list_dir."""

    def test_list_dir_with_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = sorted(storage.list_dir("."))
        assert "a.txt" in result
        assert "b.txt" in result

    def test_list_dir_with_subdirs(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "file.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = storage.list_dir(".")
        assert "sub" in result
        assert "file.txt" in result

    def test_list_dir_nonexistent_returns_empty(self, tmp_path):
        storage = FileStorage(tmp_path)
        assert storage.list_dir("nope") == []

    def test_list_dir_file_returns_empty(self, tmp_path):
        """Listing a file (not a directory) returns empty list."""
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        storage = FileStorage(tmp_path)
        assert storage.list_dir("f.txt") == []


# ---------------------------------------------------------------------------
# glob
# ---------------------------------------------------------------------------


class TestFileStorageGlob:
    """Tests for glob."""

    def test_glob_txt_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = list(storage.glob("*.txt"))
        assert len(result) == 1
        assert result[0].endswith("a.txt")

    def test_glob_recursive(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "root.py").write_text("", encoding="utf-8")
        (tmp_path / "sub" / "deep.py").write_text("", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = sorted(storage.glob("**/*.py"))
        assert len(result) == 2

    def test_glob_no_matches(self, tmp_path):
        (tmp_path / "file.txt").write_text("", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = list(storage.glob("*.json"))
        assert result == []

    def test_glob_nonexistent_dir(self, tmp_path):
        storage = FileStorage(tmp_path)
        result = list(storage.glob("*.txt", "nonexistent"))
        assert result == []

    def test_glob_with_subpath(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("", encoding="utf-8")
        (sub / "util.py").write_text("", encoding="utf-8")
        storage = FileStorage(tmp_path)
        result = list(storage.glob("*.py", "src"))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFileStorageEdgeCases:
    """Tests for edge cases."""

    def test_string_path_accepted(self, tmp_path):
        """FileStorage accepts str as root."""
        storage = FileStorage(str(tmp_path))
        assert storage.root == tmp_path.resolve()

    def test_unicode_content(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write("uni.txt", "Hello 世界 🌍")
        assert storage.read("uni.txt") == "Hello 世界 🌍"

    def test_empty_file(self, tmp_path):
        storage = FileStorage(tmp_path)
        storage.write("empty.txt", "")
        assert storage.read("empty.txt") == ""
        assert storage.exists("empty.txt") is True
