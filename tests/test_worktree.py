"""Tests for worktree primitives and service."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Success,
    WorktreeInfo,
    WorktreeList,
    WorktreeSessionId,
)
from context_harness.services.worktree_service import (
    GitRunner,
    WorktreeService,
)


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_name_returns_directory_name(self):
        """Test that name property returns the directory name."""
        info = WorktreeInfo(
            path=Path("/home/user/projects/my-project"),
            head="abc123",
            branch="refs/heads/main",
            is_main=True,
            is_bare=False,
            is_detached=False,
        )
        assert info.name == "my-project"

    def test_branch_name_strips_refs_heads(self):
        """Test that branch_name strips refs/heads/ prefix."""
        info = WorktreeInfo(
            path=Path("/project"),
            head="abc123",
            branch="refs/heads/feature-login",
            is_main=True,
            is_bare=False,
            is_detached=False,
        )
        assert info.branch_name == "feature-login"

    def test_branch_name_returns_none_when_detached(self):
        """Test that branch_name returns None for detached HEAD."""
        info = WorktreeInfo(
            path=Path("/project"),
            head="abc123",
            branch=None,
            is_main=True,
            is_bare=False,
            is_detached=True,
        )
        assert info.branch_name is None

    def test_branch_name_handles_short_branch(self):
        """Test that branch_name handles branches without prefix."""
        info = WorktreeInfo(
            path=Path("/project"),
            head="abc123",
            branch="main",
            is_main=True,
            is_bare=False,
            is_detached=False,
        )
        assert info.branch_name == "main"


class TestWorktreeList:
    """Tests for WorktreeList dataclass."""

    @pytest.fixture
    def sample_worktrees(self) -> List[WorktreeInfo]:
        """Create sample worktree list."""
        return [
            WorktreeInfo(
                path=Path("/project"),
                head="abc123",
                branch="refs/heads/main",
                is_main=True,
                is_bare=False,
                is_detached=False,
            ),
            WorktreeInfo(
                path=Path("/project-feature"),
                head="def456",
                branch="refs/heads/feature",
                is_main=False,
                is_bare=False,
                is_detached=False,
            ),
        ]

    def test_main_worktree_returns_main(self, sample_worktrees):
        """Test that main_worktree returns the main worktree."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        assert wt_list.main_worktree is not None
        assert wt_list.main_worktree.is_main is True
        assert wt_list.main_worktree.path == Path("/project")

    def test_linked_worktrees_excludes_main(self, sample_worktrees):
        """Test that linked_worktrees excludes the main worktree."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        linked = wt_list.linked_worktrees
        assert len(linked) == 1
        assert linked[0].path == Path("/project-feature")

    def test_find_by_path(self, sample_worktrees):
        """Test finding worktree by path."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        found = wt_list.find_by_path(Path("/project-feature"))
        assert found is not None
        assert found.branch == "refs/heads/feature"

    def test_find_by_path_not_found(self, sample_worktrees):
        """Test finding worktree by path when not found."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        found = wt_list.find_by_path(Path("/nonexistent"))
        assert found is None

    def test_find_by_branch_full_ref(self, sample_worktrees):
        """Test finding worktree by full branch ref."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        found = wt_list.find_by_branch("refs/heads/feature")
        assert found is not None
        assert found.path == Path("/project-feature")

    def test_find_by_branch_short_name(self, sample_worktrees):
        """Test finding worktree by short branch name."""
        wt_list = WorktreeList(
            worktrees=sample_worktrees,
            git_common_dir=Path("/project/.git"),
        )
        found = wt_list.find_by_branch("main")
        assert found is not None
        assert found.is_main is True


class TestWorktreeSessionId:
    """Tests for WorktreeSessionId."""

    def test_full_id_format(self):
        """Test full_id returns correct format."""
        session_id = WorktreeSessionId(
            worktree_name="main",
            session_name="login-feature",
        )
        assert session_id.full_id == "main--login-feature"

    def test_from_full_id_parses_correctly(self):
        """Test parsing full ID into components."""
        session_id = WorktreeSessionId.from_full_id("feature-auth--oauth-debug")
        assert session_id.worktree_name == "feature-auth"
        assert session_id.session_name == "oauth-debug"

    def test_from_full_id_without_prefix(self):
        """Test parsing ID without worktree prefix assumes main."""
        session_id = WorktreeSessionId.from_full_id("my-session")
        assert session_id.worktree_name == "main"
        assert session_id.session_name == "my-session"

    def test_from_full_id_multiple_dashes(self):
        """Test parsing ID with multiple -- in session name."""
        session_id = WorktreeSessionId.from_full_id("wt--session--with--dashes")
        assert session_id.worktree_name == "wt"
        assert session_id.session_name == "session--with--dashes"

    def test_str_returns_full_id(self):
        """Test __str__ returns full ID."""
        session_id = WorktreeSessionId(
            worktree_name="main",
            session_name="test",
        )
        assert str(session_id) == "main--test"

    def test_create_from_worktree(self):
        """Test creating session ID from WorktreeInfo."""
        worktree = WorktreeInfo(
            path=Path("/project-feature"),
            head="abc123",
            branch="refs/heads/feature",
            is_main=False,
            is_bare=False,
            is_detached=False,
        )
        session_id = WorktreeSessionId.create(worktree, "my-session")
        assert session_id.worktree_name == "project-feature"
        assert session_id.session_name == "my-session"
        assert session_id.full_id == "project-feature--my-session"


class MockGitRunner:
    """Mock git runner for testing."""

    def __init__(self):
        """Initialize mock runner with configurable responses."""
        self.responses: dict = {}
        self.calls: List[tuple] = []

    def set_response(
        self,
        args_prefix: tuple,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ):
        """Set response for a git command.

        Args:
            args_prefix: Tuple of args to match (e.g., ("rev-parse", "--git-dir"))
            stdout: Standard output to return
            stderr: Standard error to return
            returncode: Return code (non-zero raises CalledProcessError if check=True)
        """
        self.responses[args_prefix] = {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
        }

    def run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Mock run implementation."""
        self.calls.append((tuple(args), cwd, check))

        # Find matching response
        for prefix, response in self.responses.items():
            if tuple(args[: len(prefix)]) == prefix:
                if check and response["returncode"] != 0:
                    raise subprocess.CalledProcessError(
                        response["returncode"],
                        ["git"] + args,
                        response["stdout"],
                        response["stderr"],
                    )
                return subprocess.CompletedProcess(
                    ["git"] + args,
                    response["returncode"],
                    response["stdout"],
                    response["stderr"],
                )

        # Default: command not found
        if check:
            raise subprocess.CalledProcessError(
                1, ["git"] + args, "", "command not found"
            )
        return subprocess.CompletedProcess(["git"] + args, 1, "", "command not found")


class TestWorktreeService:
    """Tests for WorktreeService."""

    @pytest.fixture
    def mock_runner(self) -> MockGitRunner:
        """Create a mock git runner."""
        return MockGitRunner()

    @pytest.fixture
    def service(self, mock_runner) -> WorktreeService:
        """Create service with mock runner."""
        return WorktreeService(git_runner=mock_runner)

    def test_is_git_repo_returns_true(self, service, mock_runner):
        """Test is_git_repo returns True for valid repo."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        assert service.is_git_repo() is True

    def test_is_git_repo_returns_false(self, service, mock_runner):
        """Test is_git_repo returns False for non-repo."""
        mock_runner.set_response(
            ("rev-parse", "--git-dir"),
            returncode=128,
            stderr="fatal: not a git repository",
        )
        assert service.is_git_repo() is False

    def test_get_current_main_worktree(self, service, mock_runner):
        """Test getting current worktree info for main worktree."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("rev-parse", "--show-toplevel"), stdout="/project\n")
        mock_runner.set_response(("rev-parse", "--git-common-dir"), stdout=".git\n")
        mock_runner.set_response(("rev-parse", "HEAD"), stdout="abc123\n")
        mock_runner.set_response(("symbolic-ref", "HEAD"), stdout="refs/heads/main\n")
        mock_runner.set_response(
            ("rev-parse", "--is-bare-repository"), stdout="false\n"
        )

        result = service.get_current()

        assert isinstance(result, Success)
        info = result.value
        assert info.path == Path("/project")
        assert info.head == "abc123"
        assert info.branch == "refs/heads/main"
        assert info.is_main is True
        assert info.is_bare is False
        assert info.is_detached is False

    def test_get_current_linked_worktree(self, service, mock_runner):
        """Test getting current worktree info for linked worktree."""
        mock_runner.set_response(
            ("rev-parse", "--git-dir"), stdout="/project/.git/worktrees/feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--show-toplevel"), stdout="/project-feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(("rev-parse", "HEAD"), stdout="def456\n")
        mock_runner.set_response(
            ("symbolic-ref", "HEAD"), stdout="refs/heads/feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--is-bare-repository"), stdout="false\n"
        )

        result = service.get_current()

        assert isinstance(result, Success)
        info = result.value
        assert info.path == Path("/project-feature")
        assert info.is_main is False

    def test_get_current_detached_head(self, service, mock_runner):
        """Test getting current worktree info with detached HEAD."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("rev-parse", "--show-toplevel"), stdout="/project\n")
        mock_runner.set_response(("rev-parse", "--git-common-dir"), stdout=".git\n")
        mock_runner.set_response(("rev-parse", "HEAD"), stdout="abc123\n")
        mock_runner.set_response(
            ("symbolic-ref", "HEAD"),
            returncode=128,
            stderr="fatal: ref HEAD is not a symbolic ref",
        )
        mock_runner.set_response(
            ("rev-parse", "--is-bare-repository"), stdout="false\n"
        )

        result = service.get_current()

        assert isinstance(result, Success)
        info = result.value
        assert info.branch is None
        assert info.is_detached is True

    def test_get_current_not_git_repo(self, service, mock_runner):
        """Test get_current fails for non-git directory."""
        mock_runner.set_response(
            ("rev-parse", "--git-dir"),
            returncode=128,
            stderr="fatal: not a git repository",
        )

        result = service.get_current()

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.NOT_A_GIT_REPO

    def test_list_all_parses_porcelain_output(self, service, mock_runner):
        """Test listing all worktrees parses porcelain output."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123def456
branch refs/heads/main

worktree /project-feature
HEAD def456abc123
branch refs/heads/feature

""",
        )

        result = service.list_all()

        assert isinstance(result, Success)
        wt_list = result.value
        assert len(wt_list.worktrees) == 2
        assert wt_list.worktrees[0].path == Path("/project")
        assert wt_list.worktrees[0].branch == "refs/heads/main"
        assert wt_list.worktrees[1].path == Path("/project-feature")
        assert wt_list.worktrees[1].branch == "refs/heads/feature"

    def test_list_all_handles_detached(self, service, mock_runner):
        """Test listing worktrees with detached HEAD."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123
detached

""",
        )

        result = service.list_all()

        assert isinstance(result, Success)
        assert result.value.worktrees[0].is_detached is True
        assert result.value.worktrees[0].branch is None

    def test_create_worktree_existing_branch(self, service, mock_runner):
        """Test creating worktree from existing branch."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("worktree", "add"), stdout="")
        # Responses for get_current after creation
        mock_runner.set_response(
            ("rev-parse", "--show-toplevel"), stdout="/project-feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(("rev-parse", "HEAD"), stdout="def456\n")
        mock_runner.set_response(
            ("symbolic-ref", "HEAD"), stdout="refs/heads/feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--is-bare-repository"), stdout="false\n"
        )

        result = service.create(
            path=Path("/project-feature"),
            branch="feature",
        )

        assert isinstance(result, Success)
        # Check the worktree add command was called correctly
        calls = [c for c in mock_runner.calls if c[0][0] == "worktree"]
        assert len(calls) >= 1
        assert "add" in calls[0][0]

    def test_create_worktree_new_branch(self, service, mock_runner):
        """Test creating worktree with new branch."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("worktree", "add"), stdout="")
        mock_runner.set_response(
            ("rev-parse", "--show-toplevel"), stdout="/project-new\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(("rev-parse", "HEAD"), stdout="abc123\n")
        mock_runner.set_response(
            ("symbolic-ref", "HEAD"), stdout="refs/heads/new-feature\n"
        )
        mock_runner.set_response(
            ("rev-parse", "--is-bare-repository"), stdout="false\n"
        )

        result = service.create(
            path=Path("/project-new"),
            new_branch="new-feature",
        )

        assert isinstance(result, Success)

    def test_create_worktree_branch_in_use(self, service, mock_runner):
        """Test creating worktree fails when branch is already checked out."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("worktree", "add"),
            returncode=128,
            stderr="fatal: 'feature' is already checked out at '/other'",
        )

        result = service.create(
            path=Path("/project-feature"),
            branch="feature",
        )

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.WORKTREE_BRANCH_IN_USE

    def test_remove_worktree(self, service, mock_runner):
        """Test removing a worktree."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("worktree", "remove"), stdout="")

        result = service.remove(Path("/project-feature"))

        assert isinstance(result, Success)

    def test_remove_worktree_dirty(self, service, mock_runner):
        """Test removing dirty worktree fails without force."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("worktree", "remove"),
            returncode=128,
            stderr="fatal: '/project-feature' contains modified or untracked files",
        )

        result = service.remove(Path("/project-feature"))

        assert isinstance(result, Failure)
        assert result.code == ErrorCode.WORKTREE_DIRTY

    def test_remove_worktree_force(self, service, mock_runner):
        """Test force removing dirty worktree."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("worktree", "remove"), stdout="")

        result = service.remove(Path("/project-feature"), force=True)

        assert isinstance(result, Success)
        # Check --force was included
        calls = [c for c in mock_runner.calls if c[0][0] == "worktree"]
        assert "--force" in calls[0][0]

    def test_prune_worktrees(self, service, mock_runner):
        """Test pruning stale worktree references."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(("worktree", "prune"), stdout="")

        result = service.prune()

        assert isinstance(result, Success)

    def test_get_internal_worktrees_finds_nested(self, service, mock_runner):
        """Test finding worktrees that are inside the main repo."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        # Main worktree at /project, linked worktree inside at /project/feature-wt
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123
branch refs/heads/main

worktree /project/feature-wt
HEAD def456
branch refs/heads/feature

worktree /other/external-wt
HEAD ghi789
branch refs/heads/other

""",
        )

        result = service.get_internal_worktrees()

        assert isinstance(result, Success)
        # Only the nested worktree should be included
        assert len(result.value) == 1
        assert result.value[0] == Path("feature-wt")

    def test_get_internal_worktrees_none_nested(self, service, mock_runner):
        """Test when no worktrees are inside the main repo."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123
branch refs/heads/main

worktree /other/feature-wt
HEAD def456
branch refs/heads/feature

""",
        )

        result = service.get_internal_worktrees()

        assert isinstance(result, Success)
        assert len(result.value) == 0

    def test_get_internal_worktrees_multiple_nested(self, service, mock_runner):
        """Test finding multiple nested worktrees."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123
branch refs/heads/main

worktree /project/wt-feature-a
HEAD def456
branch refs/heads/feature-a

worktree /project/worktrees/feature-b
HEAD ghi789
branch refs/heads/feature-b

worktree /external/other
HEAD jkl012
branch refs/heads/other

""",
        )

        result = service.get_internal_worktrees()

        assert isinstance(result, Success)
        assert len(result.value) == 2
        assert Path("wt-feature-a") in result.value
        assert Path("worktrees/feature-b") in result.value

    def test_get_exclusion_patterns(self, service, mock_runner):
        """Test getting exclusion patterns for internal worktrees."""
        mock_runner.set_response(("rev-parse", "--git-dir"), stdout=".git\n")
        mock_runner.set_response(
            ("rev-parse", "--git-common-dir"), stdout="/project/.git\n"
        )
        mock_runner.set_response(
            ("worktree", "list", "--porcelain"),
            stdout="""worktree /project
HEAD abc123
branch refs/heads/main

worktree /project/76-worktree
HEAD def456
branch refs/heads/76-worktree

""",
        )

        result = service.get_exclusion_patterns()

        assert isinstance(result, Success)
        assert "76-worktree" in result.value


class TestWorktreeStaticMethods:
    """Tests for WorktreeService static methods."""

    def test_is_worktree_root_with_git_file(self, tmp_path):
        """Test detecting worktree root by .git file."""
        # Create a fake worktree with .git file
        worktree_dir = tmp_path / "feature-wt"
        worktree_dir.mkdir()
        git_file = worktree_dir / ".git"
        git_file.write_text("gitdir: /project/.git/worktrees/feature-wt")

        assert WorktreeService.is_worktree_root(worktree_dir) is True

    def test_is_worktree_root_with_git_directory(self, tmp_path):
        """Test that main repo with .git directory is not detected as worktree."""
        # Create a fake main repo with .git directory
        main_repo = tmp_path / "project"
        main_repo.mkdir()
        git_dir = main_repo / ".git"
        git_dir.mkdir()

        assert WorktreeService.is_worktree_root(main_repo) is False

    def test_is_worktree_root_no_git(self, tmp_path):
        """Test directory without .git is not a worktree."""
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()

        assert WorktreeService.is_worktree_root(plain_dir) is False

    def test_should_skip_directory_worktree(self, tmp_path):
        """Test that worktree directories are skipped."""
        # Create a fake worktree
        worktree_dir = tmp_path / "feature-wt"
        worktree_dir.mkdir()
        git_file = worktree_dir / ".git"
        git_file.write_text("gitdir: /project/.git/worktrees/feature-wt")

        assert WorktreeService.should_skip_directory(worktree_dir) is True

    def test_should_skip_directory_node_modules(self, tmp_path):
        """Test that node_modules is skipped."""
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()

        assert WorktreeService.should_skip_directory(node_modules) is True

    def test_should_skip_directory_venv(self, tmp_path):
        """Test that .venv is skipped."""
        venv = tmp_path / ".venv"
        venv.mkdir()

        assert WorktreeService.should_skip_directory(venv) is True

    def test_should_skip_directory_normal(self, tmp_path):
        """Test that normal directories are not skipped."""
        src = tmp_path / "src"
        src.mkdir()

        assert WorktreeService.should_skip_directory(src) is False
