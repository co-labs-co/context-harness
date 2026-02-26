# Branch Management

## Automatic Branch Cleanup

This repository is configured to automatically clean up stale and merged branches to keep the repository organized.

### Repository Settings

- **Auto-delete on PR merge**: ✅ Enabled
  - When a pull request is merged, the source branch is automatically deleted
  - This only applies to branches merged through GitHub PRs

### Automated Workflows

#### 1. Immediate Cleanup (`.github/workflows/cleanup-branches.yml`)
- **Trigger**: When a PR is closed (merged)
- **Action**: Deletes the merged branch immediately after PR merge
- **Permissions**: Requires `contents: write` permission

#### 2. Weekly Stale Branch Cleanup
- **Schedule**: Every Sunday at midnight UTC
- **Action**: 
  - Scans all remote branches (except `main`, `gh-pages`)
  - Identifies branches fully merged into `main`
  - Deletes merged branches automatically
- **Manual trigger**: Can be run manually via GitHub Actions UI

### Protected Branches

The following branches are protected and will never be auto-deleted:
- `main` - Primary branch
- `gh-pages` - Documentation deployment

### Manual Cleanup

To manually clean up stale branches:

```bash
# Clean up local branches tracking deleted remotes
git fetch --prune

# Delete local branches that no longer have remotes
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -D

# Run the cleanup workflow manually
gh workflow run cleanup-branches.yml
```

### Finding Merged Branches

To see which branches are fully merged into main:

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
4. **Check before creating** - Use descriptive branch names that indicate their purpose
5. **Review stale PRs** - Close or update PRs that have been open for more than 2 weeks

### Cleanup Summary (Last Run)

**Date**: February 26, 2026

**Deleted Branches**:
- `opencode/issue19-20251205204553` (merged)
- `opencode/issue3-20251204210459` (merged)
- `docs/baseline-session-update` (merged, 3 months old)
- `docs/project-context-baseline` (merged, 3 months old)
- `feat/agents-md-generation` (merged, 7 weeks old)
- `feat/mcp-config` (merged, 3 months old)
- `feature/baseline-skill-extraction` (merged, 9 weeks old)
- `feature/configurable-skills-registry` (merged, 7 weeks old)
- `feature/license` (merged, 3 months old)
- `feature/skills` (merged, 9 weeks old)
- `fix/baseline-skill-creator-standard` (merged, 7 weeks old)
- `fix/context7-mcp-tool-config` (merged, 3 months old)
- `fix/dynamic-version` (merged, 3 months old)
- `fix/preserve-user-skills-on-init` (merged, 9 weeks old)
- `fix/semantic-release-github-api` (merged, 3 months old)

**Total**: 15 stale branches cleaned up
