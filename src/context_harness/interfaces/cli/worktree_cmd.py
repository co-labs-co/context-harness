"""Worktree commands for ContextHarness CLI.

Handles the `context-harness worktree` command group for git worktree management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from context_harness.primitives import (
    Failure,
    Success,
)
from context_harness.services import WorktreeService
from context_harness.interfaces.cli.formatters import (
    console,
    print_header,
    print_warning,
    print_error,
    print_success,
    print_info,
)


@click.group("worktree")
def worktree_group() -> None:
    """Manage git worktrees for parallel development sessions.

    Worktrees allow you to work on multiple branches simultaneously,
    each with its own session context.
    """
    pass


@worktree_group.command("list")
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(exists=True),
    help="Target directory within the repository (default: current directory).",
)
def worktree_list(target: str) -> None:
    """List all worktrees for the current repository.

    Shows all worktrees including the main worktree and any linked worktrees.
    Each entry shows the path, branch, and whether it's the main worktree.

    Examples:

        context-harness worktree list

        context-harness worktree list --target ./my-project
    """
    print_header("Git Worktrees")

    service = WorktreeService()
    result = service.list_all(Path(target))

    if isinstance(result, Failure):
        print_error(result.error)
        raise SystemExit(1)

    wt_list = result.value

    if not wt_list.worktrees:
        print_warning("No worktrees found.")
        return

    # Display worktrees
    console.print()
    for wt in wt_list.worktrees:
        # Format branch name
        if wt.is_detached:
            branch_display = f"[yellow](detached at {wt.head[:7]})[/yellow]"
        elif wt.branch_name:
            branch_display = f"[cyan]{wt.branch_name}[/cyan]"
        else:
            branch_display = "[dim]unknown[/dim]"

        # Format worktree type
        if wt.is_main:
            type_display = "[green](main)[/green]"
        else:
            type_display = "[blue](linked)[/blue]"

        console.print(f"  {type_display} {wt.path}")
        console.print(f"       Branch: {branch_display}")
        console.print()

    console.print(f"[dim]Total: {len(wt_list.worktrees)} worktree(s)[/dim]")


@worktree_group.command("current")
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(exists=True),
    help="Target directory within the worktree (default: current directory).",
)
def worktree_current(target: str) -> None:
    """Show information about the current worktree.

    Displays details about the worktree you're currently in, including
    whether it's the main worktree or a linked worktree.

    Examples:

        context-harness worktree current

        context-harness worktree current --target ./my-project
    """
    service = WorktreeService()
    result = service.get_current(Path(target))

    if isinstance(result, Failure):
        print_error(result.error)
        raise SystemExit(1)

    wt = result.value

    print_header("Current Worktree")
    console.print()

    # Worktree type
    if wt.is_main:
        console.print("  Type:   [green]Main worktree[/green]")
    else:
        console.print("  Type:   [blue]Linked worktree[/blue]")

    # Path
    console.print(f"  Path:   {wt.path}")

    # Branch
    if wt.is_detached:
        console.print(f"  Branch: [yellow](detached at {wt.head[:7]})[/yellow]")
    elif wt.branch_name:
        console.print(f"  Branch: [cyan]{wt.branch_name}[/cyan]")
    else:
        console.print("  Branch: [dim]unknown[/dim]")

    # HEAD
    console.print(f"  HEAD:   [dim]{wt.head[:12]}[/dim]")

    console.print()


@worktree_group.command("add")
@click.argument("path", type=click.Path())
@click.option(
    "--branch",
    "-b",
    default=None,
    help="Existing branch to checkout in the new worktree.",
)
@click.option(
    "--new-branch",
    "-B",
    default=None,
    help="Create and checkout a new branch in the new worktree.",
)
@click.option(
    "--base",
    default=None,
    help="Base commit/branch for the new branch (default: HEAD).",
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(exists=True),
    help="Target directory within the repository (default: current directory).",
)
def worktree_add(
    path: str,
    branch: Optional[str],
    new_branch: Optional[str],
    base: Optional[str],
    target: str,
) -> None:
    """Create a new worktree.

    Creates a new worktree at the specified path. You can either:
    - Checkout an existing branch with --branch
    - Create a new branch with --new-branch
    - Let git use the directory name as the branch

    Examples:

        # Create worktree for existing branch
        context-harness worktree add ../feature-auth --branch feature-auth

        # Create worktree with new branch
        context-harness worktree add ../hotfix-123 --new-branch hotfix-123

        # Create worktree with new branch from specific base
        context-harness worktree add ../feature-x --new-branch feature-x --base main
    """
    print_header("Create Worktree")

    if branch and new_branch:
        print_error("Cannot specify both --branch and --new-branch")
        raise SystemExit(1)

    service = WorktreeService()
    result = service.create(
        path=Path(path),
        branch=branch,
        new_branch=new_branch,
        base=base,
        from_path=Path(target),
    )

    if isinstance(result, Failure):
        print_error(result.error)
        raise SystemExit(1)

    wt = result.value
    print_success(f"Worktree created at {wt.path}")

    if wt.branch_name:
        console.print(f"  Branch: [cyan]{wt.branch_name}[/cyan]")

    console.print()
    print_info("Next steps:")
    console.print(f"  1. [cyan]cd {wt.path}[/cyan]")
    console.print(f"  2. Open in your editor and start OpenCode")
    console.print(f"  3. Start a session in OpenCode: [cyan]/ctx my-session[/cyan]")
    console.print()


@worktree_group.command("remove")
@click.argument("path", type=click.Path())
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force removal even if worktree has uncommitted changes.",
)
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(exists=True),
    help="Target directory within the repository (default: current directory).",
)
def worktree_remove(path: str, force: bool, target: str) -> None:
    """Remove a worktree.

    Removes the specified worktree. By default, fails if the worktree has
    uncommitted changes. Use --force to remove anyway.

    Examples:

        context-harness worktree remove ../feature-auth

        context-harness worktree remove ../feature-auth --force
    """
    print_header("Remove Worktree")

    service = WorktreeService()
    result = service.remove(
        path=Path(path),
        force=force,
        from_path=Path(target),
    )

    if isinstance(result, Failure):
        print_error(result.error)
        if "uncommitted changes" in result.error.lower():
            print_info("Use --force to remove anyway")
        raise SystemExit(1)

    print_success(f"Worktree removed: {path}")


@worktree_group.command("prune")
@click.option(
    "--target",
    "-t",
    default=".",
    type=click.Path(exists=True),
    help="Target directory within the repository (default: current directory).",
)
def worktree_prune(target: str) -> None:
    """Clean up stale worktree references.

    Removes worktree entries for directories that no longer exist.
    Run this after manually deleting worktree directories.

    Examples:

        context-harness worktree prune
    """
    print_header("Prune Worktrees")

    service = WorktreeService()
    result = service.prune(from_path=Path(target))

    if isinstance(result, Failure):
        print_error(result.error)
        raise SystemExit(1)

    print_success("Stale worktree references cleaned up")
