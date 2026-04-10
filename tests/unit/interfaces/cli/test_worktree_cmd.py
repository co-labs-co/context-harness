"""Integration tests for worktree CLI commands.

Tests the 5 worktree CLI commands (list, current, add, remove, prune) using
Click's CliRunner with mocked WorktreeService to avoid git dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Success,
    WorktreeInfo,
    WorktreeList,
)
from context_harness.interfaces.cli.worktree_cmd import (
    worktree_group,
)


@pytest.fixture
def runner():
    return CliRunner()


def _make_worktree(
    path: str = "/project",
    head: str = "abc123",
    branch: str = "refs/heads/main",
    is_main: bool = True,
    is_detached: bool = False,
) -> WorktreeInfo:
    """Helper to create a WorktreeInfo for tests."""
    return WorktreeInfo(
        path=Path(path),
        head=head,
        branch=branch if not is_detached else None,
        is_main=is_main,
        is_bare=False,
        is_detached=is_detached,
    )


# ---------------------------------------------------------------------------
# worktree list
# ---------------------------------------------------------------------------


class TestWorktreeListCmd:
    """Tests for `worktree list` command."""

    def test_list_shows_worktrees(self, runner):
        mock_service = MagicMock()
        mock_service.list_all.return_value = Success(
            WorktreeList(
                worktrees=[
                    _make_worktree("/project", branch="refs/heads/main", is_main=True),
                    _make_worktree(
                        "/project-feature",
                        head="def456",
                        branch="refs/heads/feature",
                        is_main=False,
                    ),
                ],
                git_common_dir=Path("/project/.git"),
            )
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["list"])

        assert result.exit_code == 0
        assert "main" in result.output
        assert "feature" in result.output
        assert "2 worktree(s)" in result.output

    def test_list_empty(self, runner):
        mock_service = MagicMock()
        mock_service.list_all.return_value = Success(
            WorktreeList(worktrees=[], git_common_dir=Path("/project/.git"))
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["list"])

        assert result.exit_code == 0
        assert "No worktrees found" in result.output

    def test_list_failure(self, runner):
        mock_service = MagicMock()
        mock_service.list_all.return_value = Failure(
            error="Not a git repository", code=ErrorCode.NOT_A_GIT_REPO
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["list"])

        assert result.exit_code == 1

    def test_list_detached_head(self, runner):
        mock_service = MagicMock()
        mock_service.list_all.return_value = Success(
            WorktreeList(
                worktrees=[
                    _make_worktree(
                        "/project", head="abc1234", is_main=True, is_detached=True
                    ),
                ],
                git_common_dir=Path("/project/.git"),
            )
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["list"])

        assert result.exit_code == 0
        assert "detached" in result.output


# ---------------------------------------------------------------------------
# worktree current
# ---------------------------------------------------------------------------


class TestWorktreeCurrentCmd:
    """Tests for `worktree current` command."""

    def test_current_main_worktree(self, runner):
        mock_service = MagicMock()
        mock_service.get_current.return_value = Success(
            _make_worktree("/project", branch="refs/heads/main", is_main=True)
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["current"])

        assert result.exit_code == 0
        assert "Main worktree" in result.output
        assert "main" in result.output

    def test_current_linked_worktree(self, runner):
        mock_service = MagicMock()
        mock_service.get_current.return_value = Success(
            _make_worktree(
                "/project-feature",
                branch="refs/heads/feature",
                is_main=False,
            )
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["current"])

        assert result.exit_code == 0
        assert "Linked worktree" in result.output

    def test_current_detached(self, runner):
        mock_service = MagicMock()
        mock_service.get_current.return_value = Success(
            _make_worktree("/project", head="abc1234567890", is_detached=True)
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["current"])

        assert result.exit_code == 0
        assert "detached" in result.output

    def test_current_failure(self, runner):
        mock_service = MagicMock()
        mock_service.get_current.return_value = Failure(
            error="Not a git repository", code=ErrorCode.NOT_A_GIT_REPO
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["current"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# worktree add
# ---------------------------------------------------------------------------


class TestWorktreeAddCmd:
    """Tests for `worktree add` command."""

    def test_add_with_existing_branch(self, runner, tmp_path):
        mock_service = MagicMock()
        wt = _make_worktree(
            str(tmp_path / "feature"),
            branch="refs/heads/feature",
            is_main=False,
        )
        mock_service.create.return_value = Success(wt)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group,
                ["add", str(tmp_path / "feature"), "--branch", "feature"],
            )

        assert result.exit_code == 0
        assert "created" in result.output.lower()
        mock_service.create.assert_called_once()

    def test_add_with_new_branch(self, runner, tmp_path):
        mock_service = MagicMock()
        wt = _make_worktree(
            str(tmp_path / "new-feat"),
            branch="refs/heads/new-feat",
            is_main=False,
        )
        mock_service.create.return_value = Success(wt)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group,
                ["add", str(tmp_path / "new-feat"), "--new-branch", "new-feat"],
            )

        assert result.exit_code == 0

    def test_add_fails_with_both_branch_flags(self, runner, tmp_path):
        """Cannot specify both --branch and --new-branch."""
        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=MagicMock(),
        ):
            result = runner.invoke(
                worktree_group,
                [
                    "add",
                    str(tmp_path / "x"),
                    "--branch",
                    "a",
                    "--new-branch",
                    "b",
                ],
            )

        assert result.exit_code == 1

    def test_add_failure(self, runner, tmp_path):
        mock_service = MagicMock()
        mock_service.create.return_value = Failure(
            error="Branch already checked out",
            code=ErrorCode.WORKTREE_BRANCH_IN_USE,
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group,
                ["add", str(tmp_path / "feat"), "--branch", "feature"],
            )

        assert result.exit_code == 1

    def test_add_shows_next_steps(self, runner, tmp_path):
        mock_service = MagicMock()
        wt = _make_worktree(
            str(tmp_path / "feat"),
            branch="refs/heads/feat",
            is_main=False,
        )
        mock_service.create.return_value = Success(wt)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group,
                ["add", str(tmp_path / "feat"), "--branch", "feat"],
            )

        assert result.exit_code == 0
        assert "Next steps" in result.output


# ---------------------------------------------------------------------------
# worktree remove
# ---------------------------------------------------------------------------


class TestWorktreeRemoveCmd:
    """Tests for `worktree remove` command."""

    def test_remove_success(self, runner, tmp_path):
        mock_service = MagicMock()
        mock_service.remove.return_value = Success(None)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group, ["remove", str(tmp_path / "feature")]
            )

        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    def test_remove_dirty_fails(self, runner, tmp_path):
        mock_service = MagicMock()
        mock_service.remove.return_value = Failure(
            error="contains uncommitted changes",
            code=ErrorCode.WORKTREE_DIRTY,
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group, ["remove", str(tmp_path / "feature")]
            )

        assert result.exit_code == 1
        assert "--force" in result.output

    def test_remove_force_flag(self, runner, tmp_path):
        mock_service = MagicMock()
        mock_service.remove.return_value = Success(None)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(
                worktree_group, ["remove", str(tmp_path / "feature"), "--force"]
            )

        assert result.exit_code == 0
        mock_service.remove.assert_called_once()
        call_kwargs = mock_service.remove.call_args
        assert call_kwargs[1].get("force") is True or (
            len(call_kwargs[0]) >= 2 and call_kwargs[0][1] is True
        )


# ---------------------------------------------------------------------------
# worktree prune
# ---------------------------------------------------------------------------


class TestWorktreePruneCmd:
    """Tests for `worktree prune` command."""

    def test_prune_success(self, runner):
        mock_service = MagicMock()
        mock_service.prune.return_value = Success(None)

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["prune"])

        assert result.exit_code == 0
        assert "cleaned up" in result.output.lower()

    def test_prune_failure(self, runner):
        mock_service = MagicMock()
        mock_service.prune.return_value = Failure(
            error="Not a git repository", code=ErrorCode.NOT_A_GIT_REPO
        )

        with patch(
            "context_harness.interfaces.cli.worktree_cmd.WorktreeService",
            return_value=mock_service,
        ):
            result = runner.invoke(worktree_group, ["prune"])

        assert result.exit_code == 1
