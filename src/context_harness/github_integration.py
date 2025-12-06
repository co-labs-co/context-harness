"""GitHub integration for ContextHarness sessions."""

import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


class GitHubResult(Enum):
    """Result codes for GitHub operations."""

    SUCCESS = "success"
    NO_GIT_REPO = "no_git_repo"
    NO_GITHUB_REMOTE = "no_github_remote"
    NO_GH_CLI = "no_gh_cli"
    NOT_AUTHENTICATED = "not_authenticated"
    BRANCH_EXISTS = "branch_exists"
    ERROR = "error"


@dataclass
class GitHubContext:
    """Context about the current GitHub repository."""

    is_git_repo: bool = False
    has_github_remote: bool = False
    gh_cli_available: bool = False
    gh_authenticated: bool = False
    repo_name: Optional[str] = None
    current_branch: Optional[str] = None
    default_branch: Optional[str] = None


def _run_command(args: list[str], capture_output: bool = True) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            args,
            capture_output=capture_output,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "Command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_github_context(target: str = ".") -> GitHubContext:
    """Check the current GitHub/git context.

    Returns a GitHubContext object with information about:
    - Whether we're in a git repo
    - Whether there's a GitHub remote
    - Whether gh CLI is available and authenticated
    - Repository name and branch information
    """
    ctx = GitHubContext()
    target_path = Path(target).resolve()

    # Check if git repo
    code, stdout, _ = _run_command(
        ["git", "-C", str(target_path), "rev-parse", "--git-dir"]
    )
    ctx.is_git_repo = code == 0

    if not ctx.is_git_repo:
        return ctx

    # Check for GitHub remote
    code, stdout, _ = _run_command(
        ["git", "-C", str(target_path), "remote", "get-url", "origin"]
    )
    if code == 0 and ("github.com" in stdout or "github:" in stdout):
        ctx.has_github_remote = True

    # Get current branch
    code, stdout, _ = _run_command(
        ["git", "-C", str(target_path), "branch", "--show-current"]
    )
    if code == 0:
        ctx.current_branch = stdout

    # Check gh CLI availability
    code, _, _ = _run_command(["gh", "--version"])
    ctx.gh_cli_available = code == 0

    if not ctx.gh_cli_available:
        return ctx

    # Check gh authentication
    code, _, _ = _run_command(["gh", "auth", "status"])
    ctx.gh_authenticated = code == 0

    if not ctx.gh_authenticated:
        return ctx

    # Get repo name
    code, stdout, _ = _run_command(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    )
    if code == 0:
        ctx.repo_name = stdout

    # Get default branch
    code, stdout, _ = _run_command(
        [
            "gh",
            "repo",
            "view",
            "--json",
            "defaultBranchRef",
            "-q",
            ".defaultBranchRef.name",
        ]
    )
    if code == 0:
        ctx.default_branch = stdout

    return ctx


def create_branch(
    branch_name: str, prefix: str = "feature/", target: str = "."
) -> tuple[GitHubResult, str]:
    """Create a new git branch for the session.

    Args:
        branch_name: The session/feature name
        prefix: Branch name prefix (e.g., "feature/", "fix/", or "")
        target: Target directory

    Returns:
        Tuple of (result code, message/branch name)
    """
    target_path = Path(target).resolve()

    # Check if git repo
    code, _, _ = _run_command(["git", "-C", str(target_path), "rev-parse", "--git-dir"])
    if code != 0:
        return GitHubResult.NO_GIT_REPO, "Not a git repository"

    # Construct full branch name
    full_branch_name = f"{prefix}{branch_name}" if prefix else branch_name

    # Check if branch already exists
    code, stdout, _ = _run_command(
        ["git", "-C", str(target_path), "branch", "--list", full_branch_name]
    )
    if code == 0 and stdout:
        # Branch exists, just switch to it
        code, _, stderr = _run_command(
            ["git", "-C", str(target_path), "checkout", full_branch_name]
        )
        if code == 0:
            return GitHubResult.BRANCH_EXISTS, full_branch_name
        return GitHubResult.ERROR, f"Failed to switch to branch: {stderr}"

    # Create and switch to new branch
    code, _, stderr = _run_command(
        ["git", "-C", str(target_path), "checkout", "-b", full_branch_name]
    )
    if code == 0:
        return GitHubResult.SUCCESS, full_branch_name
    return GitHubResult.ERROR, f"Failed to create branch: {stderr}"


@dataclass
class IssueData:
    """Data for a GitHub issue."""

    title: str
    body: str
    labels: list[str] | None = None


@dataclass
class IssueResult:
    """Result of issue creation."""

    number: int
    url: str


def create_issue(
    issue_data: IssueData, target: str = "."
) -> tuple[GitHubResult, Optional[IssueResult], str]:
    """Create a GitHub issue for the session.

    Args:
        issue_data: The issue title, body, and optional labels
        target: Target directory

    Returns:
        Tuple of (result code, issue result or None, message)
    """
    ctx = check_github_context(target)

    if not ctx.is_git_repo:
        return GitHubResult.NO_GIT_REPO, None, "Not a git repository"
    if not ctx.has_github_remote:
        return GitHubResult.NO_GITHUB_REMOTE, None, "No GitHub remote found"
    if not ctx.gh_cli_available:
        return GitHubResult.NO_GH_CLI, None, "GitHub CLI (gh) not installed"
    if not ctx.gh_authenticated:
        return GitHubResult.NOT_AUTHENTICATED, None, "GitHub CLI not authenticated"

    # Build command
    cmd = [
        "gh",
        "issue",
        "create",
        "--title",
        issue_data.title,
        "--body",
        issue_data.body,
    ]
    if issue_data.labels:
        for label in issue_data.labels:
            cmd.extend(["--label", label])

    code, stdout, stderr = _run_command(cmd)
    if code != 0:
        return GitHubResult.ERROR, None, f"Failed to create issue: {stderr}"

    # Parse the URL from output (gh issue create returns the URL)
    url = stdout.strip()
    try:
        # Extract issue number from URL (e.g., https://github.com/user/repo/issues/123)
        number = int(url.split("/")[-1])
        return (
            GitHubResult.SUCCESS,
            IssueResult(number=number, url=url),
            "Issue created",
        )
    except (ValueError, IndexError):
        return GitHubResult.ERROR, None, f"Failed to parse issue URL: {stdout}"


def add_issue_comment(
    issue_number: int, comment: str, target: str = "."
) -> tuple[GitHubResult, str]:
    """Add a comment to an existing GitHub issue.

    Args:
        issue_number: The issue number
        comment: The comment body
        target: Target directory

    Returns:
        Tuple of (result code, message)
    """
    ctx = check_github_context(target)

    if not ctx.gh_cli_available:
        return GitHubResult.NO_GH_CLI, "GitHub CLI (gh) not installed"
    if not ctx.gh_authenticated:
        return GitHubResult.NOT_AUTHENTICATED, "GitHub CLI not authenticated"

    code, stdout, stderr = _run_command(
        ["gh", "issue", "comment", str(issue_number), "--body", comment]
    )
    if code != 0:
        return GitHubResult.ERROR, f"Failed to add comment: {stderr}"

    return GitHubResult.SUCCESS, stdout


@dataclass
class PRData:
    """Data for a pull request."""

    title: str
    body: str
    base: Optional[str] = None  # Default to repo's default branch
    draft: bool = False


@dataclass
class PRResult:
    """Result of PR creation."""

    number: int
    url: str


def create_pull_request(
    pr_data: PRData, target: str = "."
) -> tuple[GitHubResult, Optional[PRResult], str]:
    """Create a pull request for the current branch.

    Args:
        pr_data: The PR title, body, base branch, and draft status
        target: Target directory

    Returns:
        Tuple of (result code, PR result or None, message)
    """
    ctx = check_github_context(target)

    if not ctx.is_git_repo:
        return GitHubResult.NO_GIT_REPO, None, "Not a git repository"
    if not ctx.has_github_remote:
        return GitHubResult.NO_GITHUB_REMOTE, None, "No GitHub remote found"
    if not ctx.gh_cli_available:
        return GitHubResult.NO_GH_CLI, None, "GitHub CLI (gh) not installed"
    if not ctx.gh_authenticated:
        return GitHubResult.NOT_AUTHENTICATED, None, "GitHub CLI not authenticated"

    # Push current branch first
    code, _, stderr = _run_command(["git", "push", "-u", "origin", "HEAD"])
    if code != 0:
        return GitHubResult.ERROR, None, f"Failed to push branch: {stderr}"

    # Build command
    cmd = ["gh", "pr", "create", "--title", pr_data.title, "--body", pr_data.body]
    if pr_data.base:
        cmd.extend(["--base", pr_data.base])
    if pr_data.draft:
        cmd.append("--draft")

    code, stdout, stderr = _run_command(cmd)
    if code != 0:
        return GitHubResult.ERROR, None, f"Failed to create PR: {stderr}"

    # Parse the URL from output
    url = stdout.strip()
    try:
        number = int(url.split("/")[-1])
        return GitHubResult.SUCCESS, PRResult(number=number, url=url), "PR created"
    except (ValueError, IndexError):
        return GitHubResult.ERROR, None, f"Failed to parse PR URL: {stdout}"


def get_issue_info(
    issue_number: int, target: str = "."
) -> tuple[GitHubResult, dict, str]:
    """Get information about a GitHub issue.

    Args:
        issue_number: The issue number
        target: Target directory

    Returns:
        Tuple of (result code, issue data dict, message)
    """
    ctx = check_github_context(target)

    if not ctx.gh_cli_available:
        return GitHubResult.NO_GH_CLI, {}, "GitHub CLI (gh) not installed"
    if not ctx.gh_authenticated:
        return GitHubResult.NOT_AUTHENTICATED, {}, "GitHub CLI not authenticated"

    code, stdout, stderr = _run_command(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "title,body,url,state,labels",
        ]
    )
    if code != 0:
        return GitHubResult.ERROR, {}, f"Failed to get issue: {stderr}"

    try:
        data = json.loads(stdout)
        return GitHubResult.SUCCESS, data, "Issue retrieved"
    except json.JSONDecodeError:
        return GitHubResult.ERROR, {}, f"Failed to parse issue data: {stdout}"
