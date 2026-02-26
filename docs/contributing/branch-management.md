# Branch Management

## Automatic Branch Cleanup

This repository is configured to automatically delete branches when pull requests are merged.

### Repository Setting

- **Auto-delete on PR merge**: ✅ Enabled
  - When a pull request is merged through GitHub, the source branch is automatically deleted
  - This is a built-in GitHub repository setting
  - No additional automation or workflows required

### Protected Branches

The following branches are protected and will never be auto-deleted:
- `main` - Primary branch
- `gh-pages` - Documentation deployment

### Manual Cleanup

#### Clean up local branches

After branches are deleted remotely, clean up your local references:

```bash
# Fetch and prune deleted remote branches
git fetch --prune

# Delete local branches that no longer have remotes
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -D
```

#### Manually delete a remote branch

If you need to manually delete a branch:

```bash
# Delete remote branch
git push origin --delete branch-name

# Or use GitHub CLI
gh api repos/co-labs-co/context-harness/git/refs/heads/branch-name -X DELETE
```

### Finding Merged Branches

To identify which branches have been fully merged into main:

```bash
for branch in $(git branch -r | grep -v "main\|HEAD\|gh-pages" | sed 's/origin\///'); do
  merged=$(git cherry "origin/main" "origin/$branch" | grep -c "^+")
  if [ "$merged" -eq 0 ]; then
    last_commit=$(git log -1 --format="%ar" "origin/$branch")
    echo "MERGED: $branch (last: $last_commit)"
  fi
done
```

### Branch Naming Conventions

To help with organization, we use these prefixes:
- `feat/` or `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `chore/` - Maintenance tasks
- `refactor/` - Code refactoring
- `test/` - Test improvements

### Best Practices

1. **Create PRs promptly** - Don't let branches sit without PRs for long
2. **Merge regularly** - Keep branches short-lived and merge frequently
3. **Delete local branches** - Run `git fetch --prune` regularly to clean up local references
4. **Use descriptive names** - Branch names should clearly indicate their purpose
5. **Review stale PRs** - Close or update PRs that have been open for more than 2 weeks

### Recent Cleanup

**Date**: February 26, 2026

Cleaned up **15 stale merged branches** to improve repository organization:
- `opencode/issue19-20251205204553`, `opencode/issue3-20251204210459`
- `docs/baseline-session-update`, `docs/project-context-baseline`
- `feat/agents-md-generation`, `feat/mcp-config`
- `feature/baseline-skill-extraction`, `feature/configurable-skills-registry`
- `feature/license`, `feature/skills`
- `fix/baseline-skill-creator-standard`, `fix/context7-mcp-tool-config`
- `fix/dynamic-version`, `fix/preserve-user-skills-on-init`
- `fix/semantic-release-github-api`
