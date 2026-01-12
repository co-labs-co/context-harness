"""Worktree service for ContextHarness.

Provides git worktree detection and management operations.
Uses Protocol-based dependency injection for testability.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Protocol

from context_harness.primitives import (
    ErrorCode,
    Failure,
    Result,
    Success,
    WorktreeInfo,
    WorktreeList,
)


class GitRunner(Protocol):
    """Protocol for running git commands.

    Enables dependency injection for testing without real git operations.
    """

    def run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command.

        Args:
            args: Git command arguments (without 'git' prefix)
            cwd: Working directory for the command
            check: Whether to raise on non-zero exit

        Returns:
            CompletedProcess with stdout/stderr

        Raises:
            subprocess.CalledProcessError: If check=True and command fails
        """
        ...


class SubprocessGitRunner:
    """Default git runner using subprocess."""

    def run(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command using subprocess.

        Args:
            args: Git command arguments (without 'git' prefix)
            cwd: Working directory for the command
            check: Whether to raise on non-zero exit

        Returns:
            CompletedProcess with stdout/stderr
        """
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )


class WorktreeService:
    """Service for git worktree operations.

    Provides methods to:
    - Detect if currently in a worktree
    - List all worktrees for a repository
    - Create new worktrees
    - Remove worktrees

    Example:
        service = WorktreeService()
        result = service.get_current()
        if isinstance(result, Success):
            print(f"Current worktree: {result.value.name}")
    """

    def __init__(self, git_runner: Optional[GitRunner] = None):
        """Initialize the worktree service.

        Args:
            git_runner: Git command runner. Uses SubprocessGitRunner if None.
        """
        self._git = git_runner or SubprocessGitRunner()

    def is_git_repo(self, path: Optional[Path] = None) -> bool:
        """Check if path is inside a git repository.

        Args:
            path: Path to check. Uses CWD if None.

        Returns:
            True if inside a git repository
        """
        try:
            self._git.run(
                ["rev-parse", "--git-dir"],
                cwd=path,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_current(self, path: Optional[Path] = None) -> Result[WorktreeInfo]:
        """Get information about the current worktree.

        Args:
            path: Path within the worktree. Uses CWD if None.

        Returns:
            Result containing WorktreeInfo or Failure
        """
        cwd = path or Path.cwd()

        # Check if we're in a git repo
        if not self.is_git_repo(cwd):
            return Failure(
                error=f"Not a git repository: {cwd}",
                code=ErrorCode.NOT_A_GIT_REPO,
                details={"path": str(cwd)},
            )

        try:
            # Get worktree root
            toplevel = self._git.run(
                ["rev-parse", "--show-toplevel"],
                cwd=cwd,
            ).stdout.strip()

            # Get git directory
            git_dir = self._git.run(
                ["rev-parse", "--git-dir"],
                cwd=cwd,
            ).stdout.strip()

            # Get common git directory (shared .git for linked worktrees)
            common_dir = self._git.run(
                ["rev-parse", "--git-common-dir"],
                cwd=cwd,
            ).stdout.strip()

            # Get current HEAD
            head = self._git.run(
                ["rev-parse", "HEAD"],
                cwd=cwd,
            ).stdout.strip()

            # Get current branch (may fail if detached)
            try:
                branch_result = self._git.run(
                    ["symbolic-ref", "HEAD"],
                    cwd=cwd,
                )
                branch: Optional[str] = branch_result.stdout.strip()
                is_detached = False
            except subprocess.CalledProcessError:
                branch = None
                is_detached = True

            # Determine if this is the main worktree
            # In main worktree: git-dir is ".git" or absolute path to .git
            # In linked worktree: git-dir points to .git/worktrees/<name>
            git_dir_path = Path(git_dir)
            common_dir_path = Path(common_dir)

            # Resolve to absolute paths for comparison
            if not git_dir_path.is_absolute():
                git_dir_path = (cwd / git_dir_path).resolve()
            if not common_dir_path.is_absolute():
                common_dir_path = (cwd / common_dir_path).resolve()

            is_main = git_dir_path == common_dir_path

            # Check if bare repo
            is_bare_result = self._git.run(
                ["rev-parse", "--is-bare-repository"],
                cwd=cwd,
            )
            is_bare = is_bare_result.stdout.strip().lower() == "true"

            return Success(
                value=WorktreeInfo(
                    path=Path(toplevel),
                    head=head,
                    branch=branch,
                    is_main=is_main,
                    is_bare=is_bare,
                    is_detached=is_detached,
                )
            )

        except subprocess.CalledProcessError as e:
            return Failure(
                error=f"Git command failed: {e.stderr or e.stdout}",
                code=ErrorCode.GIT_COMMAND_FAILED,
                details={"command": e.cmd, "returncode": e.returncode},
            )

    def list_all(self, path: Optional[Path] = None) -> Result[WorktreeList]:
        """List all worktrees for the repository.

        Args:
            path: Path within any worktree of the repo. Uses CWD if None.

        Returns:
            Result containing WorktreeList or Failure
        """
        cwd = path or Path.cwd()

        if not self.is_git_repo(cwd):
            return Failure(
                error=f"Not a git repository: {cwd}",
                code=ErrorCode.NOT_A_GIT_REPO,
                details={"path": str(cwd)},
            )

        try:
            # Get common git directory
            common_dir = self._git.run(
                ["rev-parse", "--git-common-dir"],
                cwd=cwd,
            ).stdout.strip()

            common_dir_path = Path(common_dir)
            if not common_dir_path.is_absolute():
                common_dir_path = (cwd / common_dir_path).resolve()

            # Get worktree list in porcelain format
            result = self._git.run(
                ["worktree", "list", "--porcelain"],
                cwd=cwd,
            )

            worktrees = self._parse_worktree_list(result.stdout, common_dir_path)

            return Success(
                value=WorktreeList(
                    worktrees=worktrees,
                    git_common_dir=common_dir_path,
                )
            )

        except subprocess.CalledProcessError as e:
            return Failure(
                error=f"Git command failed: {e.stderr or e.stdout}",
                code=ErrorCode.GIT_COMMAND_FAILED,
                details={"command": e.cmd, "returncode": e.returncode},
            )

    def _parse_worktree_list(self, output: str, common_dir: Path) -> List[WorktreeInfo]:
        """Parse git worktree list --porcelain output.

        Format:
            worktree /path/to/worktree
            HEAD abc123...
            branch refs/heads/main

            worktree /path/to/linked
            HEAD def456...
            branch refs/heads/feature

        Args:
            output: Porcelain format output from git worktree list
            common_dir: Path to the common git directory

        Returns:
            List of WorktreeInfo objects
        """
        worktrees: List[WorktreeInfo] = []
        current: dict = {}

        for line in output.split("\n"):
            line = line.strip()

            if not line:
                # Empty line means end of current worktree entry
                if current:
                    worktrees.append(self._build_worktree_info(current, common_dir))
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True

        # Don't forget last entry
        if current:
            worktrees.append(self._build_worktree_info(current, common_dir))

        return worktrees

    def _build_worktree_info(self, data: dict, common_dir: Path) -> WorktreeInfo:
        """Build WorktreeInfo from parsed data.

        Args:
            data: Parsed worktree data dict
            common_dir: Path to common git directory

        Returns:
            WorktreeInfo instance
        """
        path = Path(data["path"])
        is_bare = data.get("bare", False)

        # Determine if main worktree
        # Main worktree's .git is at common_dir or common_dir's parent
        if is_bare:
            is_main = True
        else:
            # For main worktree, common_dir is inside the worktree's .git
            # e.g., /project/.git vs /project/.git/worktrees/feature
            worktree_git = path / ".git"
            is_main = (
                (
                    worktree_git.exists()
                    and worktree_git.is_dir()
                    and common_dir.resolve() == worktree_git.resolve()
                )
                or (
                    # Handle case where worktree_git is a file pointing elsewhere
                    worktree_git.exists()
                    and worktree_git.is_file()
                    and False  # Linked worktrees have .git as file
                )
                or (
                    # Main worktree when common_dir is the .git folder
                    common_dir.parent == path
                )
            )

        return WorktreeInfo(
            path=path,
            head=data.get("head", ""),
            branch=data.get("branch"),
            is_main=is_main,
            is_bare=is_bare,
            is_detached=data.get("detached", False),
        )

    def create(
        self,
        path: Path,
        branch: Optional[str] = None,
        new_branch: Optional[str] = None,
        base: Optional[str] = None,
        from_path: Optional[Path] = None,
    ) -> Result[WorktreeInfo]:
        """Create a new worktree.

        Args:
            path: Path for the new worktree
            branch: Existing branch to checkout (mutually exclusive with new_branch)
            new_branch: Create and checkout a new branch
            base: Base commit/branch for new branch (default: HEAD)
            from_path: Path within existing repo. Uses CWD if None.

        Returns:
            Result containing new WorktreeInfo or Failure
        """
        cwd = from_path or Path.cwd()

        if not self.is_git_repo(cwd):
            return Failure(
                error=f"Not a git repository: {cwd}",
                code=ErrorCode.NOT_A_GIT_REPO,
                details={"path": str(cwd)},
            )

        if branch and new_branch:
            return Failure(
                error="Cannot specify both branch and new_branch",
                code=ErrorCode.VALIDATION_ERROR,
                details={"branch": branch, "new_branch": new_branch},
            )

        try:
            args = ["worktree", "add"]

            if new_branch:
                args.extend(["-b", new_branch])
                args.append(str(path))
                if base:
                    args.append(base)
            elif branch:
                args.append(str(path))
                args.append(branch)
            else:
                # No branch specified, git will use directory name
                args.append(str(path))

            self._git.run(args, cwd=cwd)

            # Return info about the new worktree
            return self.get_current(path)

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or e.stdout or "Unknown error"

            # Check for common errors
            if "already checked out" in error_msg.lower():
                return Failure(
                    error=f"Branch is already checked out in another worktree",
                    code=ErrorCode.WORKTREE_BRANCH_IN_USE,
                    details={"branch": branch or new_branch, "error": error_msg},
                )

            return Failure(
                error=f"Failed to create worktree: {error_msg}",
                code=ErrorCode.GIT_COMMAND_FAILED,
                details={"path": str(path), "error": error_msg},
            )

    def remove(
        self,
        path: Path,
        force: bool = False,
        from_path: Optional[Path] = None,
    ) -> Result[None]:
        """Remove a worktree.

        Args:
            path: Path to the worktree to remove
            force: Force removal even if worktree has uncommitted changes
            from_path: Path within existing repo. Uses CWD if None.

        Returns:
            Result containing None on success or Failure
        """
        cwd = from_path or Path.cwd()

        if not self.is_git_repo(cwd):
            return Failure(
                error=f"Not a git repository: {cwd}",
                code=ErrorCode.NOT_A_GIT_REPO,
                details={"path": str(cwd)},
            )

        try:
            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(str(path))

            self._git.run(args, cwd=cwd)

            return Success(value=None, message=f"Worktree removed: {path}")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or e.stdout or "Unknown error"

            # Check for common errors
            if "contains modified or untracked files" in error_msg.lower():
                return Failure(
                    error="Worktree has uncommitted changes. Use force=True to remove anyway.",
                    code=ErrorCode.WORKTREE_DIRTY,
                    details={"path": str(path), "error": error_msg},
                )

            if "is not a working tree" in error_msg.lower():
                return Failure(
                    error=f"Not a valid worktree: {path}",
                    code=ErrorCode.WORKTREE_NOT_FOUND,
                    details={"path": str(path), "error": error_msg},
                )

            return Failure(
                error=f"Failed to remove worktree: {error_msg}",
                code=ErrorCode.GIT_COMMAND_FAILED,
                details={"path": str(path), "error": error_msg},
            )

    def prune(self, from_path: Optional[Path] = None) -> Result[None]:
        """Prune stale worktree references.

        Removes worktree entries for directories that no longer exist.

        Args:
            from_path: Path within existing repo. Uses CWD if None.

        Returns:
            Result containing None on success or Failure
        """
        cwd = from_path or Path.cwd()

        if not self.is_git_repo(cwd):
            return Failure(
                error=f"Not a git repository: {cwd}",
                code=ErrorCode.NOT_A_GIT_REPO,
                details={"path": str(cwd)},
            )

        try:
            self._git.run(["worktree", "prune"], cwd=cwd)
            return Success(value=None, message="Stale worktree references pruned")

        except subprocess.CalledProcessError as e:
            return Failure(
                error=f"Failed to prune worktrees: {e.stderr or e.stdout}",
                code=ErrorCode.GIT_COMMAND_FAILED,
                details={"error": e.stderr or e.stdout},
            )

    def get_internal_worktrees(
        self, from_path: Optional[Path] = None
    ) -> Result[List[Path]]:
        """Get linked worktrees that are inside the main worktree.

        These worktrees should be excluded from scans to avoid duplicate content.
        For example, if main repo is at /project and a worktree is at
        /project/feature-branch, that worktree path should be excluded.

        Args:
            from_path: Path within existing repo. Uses CWD if None.

        Returns:
            Result containing list of relative paths to internal worktrees

        Example:
            >>> service = WorktreeService()
            >>> result = service.get_internal_worktrees()
            >>> if isinstance(result, Success):
            ...     for path in result.value:
            ...         print(f"Exclude: {path}")
            Exclude: 76-worktree
            Exclude: feature-branch-wt
        """
        result = self.list_all(from_path)
        if isinstance(result, Failure):
            return result

        worktree_list = result.value
        main_worktree = worktree_list.main_worktree

        if main_worktree is None:
            return Success(value=[])

        main_path = main_worktree.path.resolve()
        internal_worktrees: List[Path] = []

        for wt in worktree_list.linked_worktrees:
            wt_path = wt.path.resolve()

            # Check if this worktree is inside the main worktree
            try:
                relative = wt_path.relative_to(main_path)
                internal_worktrees.append(relative)
            except ValueError:
                # Worktree is outside main repo, no exclusion needed
                pass

        return Success(value=internal_worktrees)

    def get_exclusion_patterns(
        self, from_path: Optional[Path] = None
    ) -> Result[List[str]]:
        """Get glob exclusion patterns for internal worktrees.

        Returns patterns suitable for excluding worktrees from file scans.
        Can be used with glob, grep, or find commands.

        Args:
            from_path: Path within existing repo. Uses CWD if None.

        Returns:
            Result containing list of exclusion patterns

        Example:
            >>> service = WorktreeService()
            >>> result = service.get_exclusion_patterns()
            >>> if isinstance(result, Success):
            ...     for pattern in result.value:
            ...         print(f"--exclude={pattern}")
            --exclude=76-worktree
            --exclude=feature-branch-wt
        """
        result = self.get_internal_worktrees(from_path)
        if isinstance(result, Failure):
            return result

        # Convert paths to string patterns
        patterns = [str(p) for p in result.value]
        return Success(value=patterns)

    @staticmethod
    def is_worktree_root(path: Path) -> bool:
        """Check if a path is a git worktree root (not the main repo).

        Linked worktrees have a `.git` FILE (not directory) that points
        to the main repo's .git/worktrees/<name> directory.
        The main repo has a `.git` DIRECTORY.

        This is useful for detecting worktrees without running git commands,
        e.g., during directory traversal.

        Args:
            path: Path to check

        Returns:
            True if path is a linked worktree root (has .git file)

        Example:
            >>> WorktreeService.is_worktree_root(Path("/project"))
            False  # Main repo, .git is a directory
            >>> WorktreeService.is_worktree_root(Path("/project/feature-wt"))
            True   # Linked worktree, .git is a file
        """
        git_path = path / ".git"
        return git_path.exists() and git_path.is_file()

    @staticmethod
    def should_skip_directory(path: Path) -> bool:
        """Check if a directory should be skipped during traversal.

        Combines worktree detection with common skip patterns.
        Use this during directory walks to avoid scanning into
        worktrees, which would cause duplicate file discovery.

        Args:
            path: Directory path to check

        Returns:
            True if directory should be skipped

        Example:
            >>> for item in root.iterdir():
            ...     if item.is_dir() and WorktreeService.should_skip_directory(item):
            ...         continue  # Skip this directory
            ...     # Process item
        """
        # Skip if it's a linked worktree root
        if WorktreeService.is_worktree_root(path):
            return True

        # Common directories that should always be skipped
        skip_names = {
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            ".next",
            ".nuxt",
            "target",  # Rust/Java build output
        }

        return path.name in skip_names
