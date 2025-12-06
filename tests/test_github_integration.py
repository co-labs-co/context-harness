"""Tests for the GitHub integration module."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_harness.github_integration import (
    GitHubContext,
    GitHubResult,
    IssueData,
    IssueResult,
    PRData,
    PRResult,
    add_issue_comment,
    check_github_context,
    create_branch,
    create_issue,
    create_pull_request,
    get_issue_info,
)


class TestCheckGitHubContext:
    """Tests for check_github_context function."""

    @patch("context_harness.github_integration._run_command")
    def test_not_a_git_repo(self, mock_run):
        """Test detection of non-git directory."""
        mock_run.return_value = (1, "", "not a git repository")

        ctx = check_github_context("/some/path")

        assert ctx.is_git_repo is False
        assert ctx.has_github_remote is False

    @patch("context_harness.github_integration._run_command")
    def test_git_repo_without_github_remote(self, mock_run):
        """Test git repo without GitHub remote."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "get-url" in args:
                return (0, "git@gitlab.com:user/repo.git", "")
            if "branch" in args:
                return (0, "main", "")
            if "--version" in args:
                return (0, "gh version 2.0.0", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        ctx = check_github_context()

        assert ctx.is_git_repo is True
        assert ctx.has_github_remote is False

    @patch("context_harness.github_integration._run_command")
    def test_git_repo_with_github_remote(self, mock_run):
        """Test git repo with GitHub remote."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "get-url" in args:
                return (0, "git@github.com:user/repo.git", "")
            if "branch" in args and "--show-current" in args:
                return (0, "main", "")
            if "--version" in args:
                return (0, "gh version 2.0.0", "")
            if "auth" in args:
                return (0, "", "")
            if "repo" in args and "view" in args:
                if "nameWithOwner" in args:
                    return (0, "user/repo", "")
                if "defaultBranchRef" in args:
                    return (0, "main", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        ctx = check_github_context()

        assert ctx.is_git_repo is True
        assert ctx.has_github_remote is True
        assert ctx.gh_cli_available is True
        assert ctx.gh_authenticated is True
        assert ctx.repo_name == "user/repo"
        assert ctx.default_branch == "main"

    @patch("context_harness.github_integration._run_command")
    def test_gh_cli_not_installed(self, mock_run):
        """Test when gh CLI is not installed."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "get-url" in args:
                return (0, "git@github.com:user/repo.git", "")
            if "branch" in args:
                return (0, "main", "")
            if "--version" in args:
                return (-1, "", "Command not found")
            return (1, "", "")

        mock_run.side_effect = mock_command

        ctx = check_github_context()

        assert ctx.is_git_repo is True
        assert ctx.has_github_remote is True
        assert ctx.gh_cli_available is False


class TestCreateBranch:
    """Tests for create_branch function."""

    @patch("context_harness.github_integration._run_command")
    def test_create_new_branch(self, mock_run):
        """Test creating a new branch."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "branch" in args and "--list" in args:
                return (0, "", "")  # Branch doesn't exist
            if "checkout" in args and "-b" in args:
                return (0, "", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        result, message = create_branch("my-feature")

        assert result == GitHubResult.SUCCESS
        assert message == "feature/my-feature"

    @patch("context_harness.github_integration._run_command")
    def test_branch_already_exists(self, mock_run):
        """Test switching to existing branch."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "branch" in args and "--list" in args:
                return (0, "feature/my-feature", "")  # Branch exists
            if "checkout" in args and "-b" not in args:
                return (0, "", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        result, message = create_branch("my-feature")

        assert result == GitHubResult.BRANCH_EXISTS
        assert message == "feature/my-feature"

    @patch("context_harness.github_integration._run_command")
    def test_create_branch_no_prefix(self, mock_run):
        """Test creating a branch without prefix."""

        def mock_command(args, **kwargs):
            if "rev-parse" in args:
                return (0, ".git", "")
            if "branch" in args and "--list" in args:
                return (0, "", "")
            if "checkout" in args and "-b" in args:
                return (0, "", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        result, message = create_branch("my-feature", prefix="")

        assert result == GitHubResult.SUCCESS
        assert message == "my-feature"

    @patch("context_harness.github_integration._run_command")
    def test_create_branch_not_git_repo(self, mock_run):
        """Test branch creation in non-git directory."""
        mock_run.return_value = (1, "", "not a git repository")

        result, message = create_branch("my-feature")

        assert result == GitHubResult.NO_GIT_REPO


class TestCreateIssue:
    """Tests for create_issue function."""

    @patch("context_harness.github_integration.check_github_context")
    @patch("context_harness.github_integration._run_command")
    def test_create_issue_success(self, mock_run, mock_context):
        """Test successful issue creation."""
        mock_context.return_value = GitHubContext(
            is_git_repo=True,
            has_github_remote=True,
            gh_cli_available=True,
            gh_authenticated=True,
        )
        mock_run.return_value = (
            0,
            "https://github.com/user/repo/issues/42",
            "",
        )

        issue_data = IssueData(
            title="Test Issue",
            body="Test body",
            labels=["enhancement"],
        )

        result, issue_result, message = create_issue(issue_data)

        assert result == GitHubResult.SUCCESS
        assert issue_result is not None
        assert issue_result.number == 42
        assert issue_result.url == "https://github.com/user/repo/issues/42"

    @patch("context_harness.github_integration.check_github_context")
    def test_create_issue_no_gh_cli(self, mock_context):
        """Test issue creation without gh CLI."""
        mock_context.return_value = GitHubContext(
            is_git_repo=True,
            has_github_remote=True,
            gh_cli_available=False,
        )

        issue_data = IssueData(title="Test", body="Test")
        result, issue_result, message = create_issue(issue_data)

        assert result == GitHubResult.NO_GH_CLI
        assert issue_result is None

    @patch("context_harness.github_integration.check_github_context")
    def test_create_issue_not_authenticated(self, mock_context):
        """Test issue creation when not authenticated."""
        mock_context.return_value = GitHubContext(
            is_git_repo=True,
            has_github_remote=True,
            gh_cli_available=True,
            gh_authenticated=False,
        )

        issue_data = IssueData(title="Test", body="Test")
        result, issue_result, message = create_issue(issue_data)

        assert result == GitHubResult.NOT_AUTHENTICATED
        assert issue_result is None


class TestAddIssueComment:
    """Tests for add_issue_comment function."""

    @patch("context_harness.github_integration.check_github_context")
    @patch("context_harness.github_integration._run_command")
    def test_add_comment_success(self, mock_run, mock_context):
        """Test successful comment addition."""
        mock_context.return_value = GitHubContext(
            gh_cli_available=True,
            gh_authenticated=True,
        )
        mock_run.return_value = (0, "Comment added", "")

        result, message = add_issue_comment(42, "Test comment")

        assert result == GitHubResult.SUCCESS


class TestCreatePullRequest:
    """Tests for create_pull_request function."""

    @patch("context_harness.github_integration.check_github_context")
    @patch("context_harness.github_integration._run_command")
    def test_create_pr_success(self, mock_run, mock_context):
        """Test successful PR creation."""
        mock_context.return_value = GitHubContext(
            is_git_repo=True,
            has_github_remote=True,
            gh_cli_available=True,
            gh_authenticated=True,
        )

        def mock_command(args, **kwargs):
            if "push" in args:
                return (0, "", "")
            if "pr" in args and "create" in args:
                return (0, "https://github.com/user/repo/pull/123", "")
            return (1, "", "")

        mock_run.side_effect = mock_command

        pr_data = PRData(title="Test PR", body="Test body")
        result, pr_result, message = create_pull_request(pr_data)

        assert result == GitHubResult.SUCCESS
        assert pr_result is not None
        assert pr_result.number == 123

    @patch("context_harness.github_integration.check_github_context")
    @patch("context_harness.github_integration._run_command")
    def test_create_pr_push_fails(self, mock_run, mock_context):
        """Test PR creation when push fails."""
        mock_context.return_value = GitHubContext(
            is_git_repo=True,
            has_github_remote=True,
            gh_cli_available=True,
            gh_authenticated=True,
        )
        mock_run.return_value = (1, "", "Permission denied")

        pr_data = PRData(title="Test PR", body="Test body")
        result, pr_result, message = create_pull_request(pr_data)

        assert result == GitHubResult.ERROR
        assert pr_result is None
        assert "push" in message.lower()


class TestGetIssueInfo:
    """Tests for get_issue_info function."""

    @patch("context_harness.github_integration.check_github_context")
    @patch("context_harness.github_integration._run_command")
    def test_get_issue_success(self, mock_run, mock_context):
        """Test successful issue retrieval."""
        mock_context.return_value = GitHubContext(
            gh_cli_available=True,
            gh_authenticated=True,
        )

        issue_data = {
            "title": "Test Issue",
            "body": "Test body",
            "url": "https://github.com/user/repo/issues/42",
            "state": "open",
            "labels": [],
        }
        mock_run.return_value = (0, json.dumps(issue_data), "")

        result, data, message = get_issue_info(42)

        assert result == GitHubResult.SUCCESS
        assert data["title"] == "Test Issue"
        assert data["state"] == "open"


class TestCommandFileIntegration:
    """Tests for command file templates."""

    def test_issue_command_file_exists(self, tmp_path):
        """Test that issue.md command file is properly formatted."""
        from context_harness.installer import get_templates_dir

        templates_dir = get_templates_dir()
        issue_md = templates_dir / ".opencode" / "command" / "issue.md"

        assert issue_md.exists(), "issue.md command file should exist"

        content = issue_md.read_text(encoding="utf-8")
        assert "description:" in content
        assert "agent: context-harness" in content

    def test_pr_command_file_exists(self, tmp_path):
        """Test that pr.md command file is properly formatted."""
        from context_harness.installer import get_templates_dir

        templates_dir = get_templates_dir()
        pr_md = templates_dir / ".opencode" / "command" / "pr.md"

        assert pr_md.exists(), "pr.md command file should exist"

        content = pr_md.read_text(encoding="utf-8")
        assert "description:" in content
        assert "agent: context-harness" in content
