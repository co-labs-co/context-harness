"""Worktree primitives for ContextHarness.

Provides dataclasses for git worktree detection and management,
enabling parallel work sessions across multiple branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class WorktreeInfo:
    """Information about a git worktree.

    Represents the state of a single git worktree, whether it's
    the main worktree or a linked worktree.

    Attributes:
        path: Absolute path to the worktree directory
        head: Current HEAD commit SHA
        branch: Branch name (None if detached HEAD)
        is_main: True if this is the main worktree (original clone)
        is_bare: True if the repository is bare
        is_detached: True if HEAD is detached (not on a branch)
        name: Worktree name (directory name, used for session namespacing)
    """

    path: Path
    head: str
    branch: Optional[str]
    is_main: bool
    is_bare: bool
    is_detached: bool

    @property
    def name(self) -> str:
        """Get the worktree name (directory name).

        Returns:
            The name of the worktree directory
        """
        return self.path.name

    @property
    def branch_name(self) -> Optional[str]:
        """Get the short branch name without refs/heads/ prefix.

        Returns:
            Short branch name or None if detached
        """
        if self.branch is None:
            return None
        # Remove refs/heads/ prefix if present
        if self.branch.startswith("refs/heads/"):
            return self.branch[11:]
        return self.branch


@dataclass(frozen=True)
class WorktreeList:
    """List of all worktrees for a repository.

    Contains the main worktree and any linked worktrees.

    Attributes:
        worktrees: List of all worktrees
        git_common_dir: Path to the shared .git directory
    """

    worktrees: List[WorktreeInfo]
    git_common_dir: Path

    @property
    def main_worktree(self) -> Optional[WorktreeInfo]:
        """Get the main worktree.

        Returns:
            The main worktree or None if bare repo
        """
        for wt in self.worktrees:
            if wt.is_main:
                return wt
        return None

    @property
    def linked_worktrees(self) -> List[WorktreeInfo]:
        """Get all linked (non-main) worktrees.

        Returns:
            List of linked worktrees
        """
        return [wt for wt in self.worktrees if not wt.is_main]

    def find_by_path(self, path: Path) -> Optional[WorktreeInfo]:
        """Find a worktree by path.

        Args:
            path: Absolute path to search for

        Returns:
            WorktreeInfo if found, None otherwise
        """
        resolved = path.resolve()
        for wt in self.worktrees:
            if wt.path.resolve() == resolved:
                return wt
        return None

    def find_by_branch(self, branch: str) -> Optional[WorktreeInfo]:
        """Find a worktree by branch name.

        Args:
            branch: Branch name (with or without refs/heads/ prefix)

        Returns:
            WorktreeInfo if found, None otherwise
        """
        # Normalize branch name
        if branch.startswith("refs/heads/"):
            full_branch = branch
            short_branch = branch[11:]
        else:
            full_branch = f"refs/heads/{branch}"
            short_branch = branch

        for wt in self.worktrees:
            if wt.branch == full_branch or wt.branch == short_branch:
                return wt
        return None


@dataclass(frozen=True)
class WorktreeSessionId:
    """A session identifier that includes worktree context.

    Enables unique session naming across worktrees using the pattern:
    {worktree_name}--{session_name}

    Attributes:
        worktree_name: Name of the worktree (directory name)
        session_name: Name of the session within the worktree
    """

    worktree_name: str
    session_name: str

    @property
    def full_id(self) -> str:
        """Get the full session ID with worktree prefix.

        Returns:
            Full session ID in format: worktree--session
        """
        return f"{self.worktree_name}--{self.session_name}"

    @classmethod
    def from_full_id(cls, full_id: str) -> "WorktreeSessionId":
        """Parse a full session ID into components.

        Args:
            full_id: Full session ID (e.g., "main--login-feature")

        Returns:
            WorktreeSessionId instance

        Raises:
            ValueError: If the ID format is invalid
        """
        if "--" not in full_id:
            # No worktree prefix, assume "main"
            return cls(worktree_name="main", session_name=full_id)

        parts = full_id.split("--", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid session ID format: {full_id}")

        return cls(worktree_name=parts[0], session_name=parts[1])

    @classmethod
    def create(cls, worktree: WorktreeInfo, session_name: str) -> "WorktreeSessionId":
        """Create a session ID from a worktree and session name.

        Args:
            worktree: The worktree context
            session_name: The session name

        Returns:
            WorktreeSessionId instance
        """
        return cls(worktree_name=worktree.name, session_name=session_name)

    def __str__(self) -> str:
        """String representation is the full ID."""
        return self.full_id
