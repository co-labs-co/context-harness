# HTTP Registry Support

**Session ID**: http-registry-support
**Branch**: worktree-twinkling-spinning-ripple
**PR**: #102
**Issue**: #101
**Compaction Cycle**: 4
**Last Updated**: 2026-03-23

## Summary

Implemented multi-backend registry support for ContextHarness skills system with HTTP registry hosting, web frontend, CLI commands, and auto-rebase workflow for parallel skill extraction.

## Completed Features

### 1. Multi-Backend Registry Support
- HTTP registry backend for custom skill hosting
- GitHub registry backend (existing, enhanced)
- Configuration layering: env var > project config > user config > default

### 2. CLI Commands
```bash
ch skill use-registry <url>              # Configure registry (saves to config)
ch skill use-registry <url> --project    # Project-scoped
ch skill install <name> --registry <url> # One-off install from specific registry
```

### 3. Web Frontend (Docker/nginx)
- `index.html` - Skill listing with search
- `skill.html` - Individual skill page with file explorer
- Raw file viewer with copy functionality
- Docker/nginx setup for HTTP registry hosting

### 4. Auto-Rebase Workflow (`.github/workflows/auto-rebase.yml`)
Automatically rebases PRs when shared files change on main. Resolves JSON conflicts by:
1. Detecting conflicted files with `git diff --name-only --diff-filter=U`
2. Getting main's version: `git show :2:filepath` (stage 2 = ours = upstream)
3. Getting PR's version: `git show :3:filepath` (stage 3 = theirs = commit being replayed)
4. Deep merging both versions
5. Rebuilding `skills.json` via `sync-registry.py`
6. Continuing rebase with resolved conflicts

### 5. GitHub Actions Permissions Documentation
- README.md: Setup section at top
- QUICKSTART.md: Required settings section
- CLI output: Reminder after `init-repo` success

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Use `:3:filepath` not `HEAD:filepath` | During rebase, HEAD points to base branch, not PR's commit. Stage 3 = commit being replayed. |
| Deep merge JSON files | Both main and PR add entries to shared files; need to combine both |
| Run `sync-registry.py` after merge | Ensures `skills.json` reflects all skills on disk |
| Configure git identity in workflow | GitHub Actions runners have no default identity; `rebase --continue` fails without it |

## Key Files Modified

| File | Changes |
|------|---------|
| `skill_service.py` | Auto-rebase workflow, GitHub permissions docs |
| `skill_cmd.py` | Added `use-registry` command and `--registry` flag |
| `skills.py` | `dirs_exist_ok=True` for re-extraction, permissions reminder |

## Bug Fixes This Session

1. Test expecting empty `skills.json` → expect scaffolded skills
2. PR title: "Git/GitHub" → "git/github" (lowercase for commitlint)
3. jq parsing: JSON array → space-separated format (brackets in branch names broke parsing)
4. Git identity: Added `github-actions[bot]` config in workflow
5. **CRITICAL**: `HEAD:filepath` → `:3:filepath` for PR version during rebase

## Testing

```bash
uv run pytest tests/ -v
docker-compose build && docker-compose up -d
ch skill use-registry http://localhost:8080
```

## Next Steps

1. Create new test repo with updated CLI
2. Configure Actions permissions (Settings → Actions → General)
3. Extract two skills in parallel
4. Merge first PR, verify second PR auto-rebases
