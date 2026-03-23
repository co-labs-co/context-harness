# HTTP Registry Support

**Session ID**: http-registry-support
**Branch**: worktree-twinkling-spinning-ripple
**PR**: #102
**Issue**: #101
**Compaction Cycle**: 2
**Last Updated**: 2026-03-22

## Summary

Implemented multi-backend registry support for ContextHarness skills system with HTTP registry hosting, web frontend, and CLI commands.

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
- Getting Started section with CLI commands
- Docker/nginx setup for HTTP registry hosting

### 4. Skill Extraction Improvements
- Creates `version.txt` for version tracking
- Updates release-please configs automatically
- Generates `.listing.json` for file tree discovery

## Key Files Modified

| File | Changes |
|------|---------|
| `skill_service.py` | Frontend scaffolding (index.html, skill.html, Docker/nginx, sync-registry.py) |
| `skill_cmd.py` | Added `use-registry` command and `--registry` flag |
| `skills.py` | extract_skill creates version.txt, updates release-please, generates .listing.json |

## Bug Fixes Applied

1. `response` → `res` typo in frontend JavaScript
2. Dockerfile missing `skill.html`
3. Markdown rendering removed (raw view only)
4. `extract_skill` now creates version.txt
5. `.listing.json` string format handling in frontend
6. `${f.dir}` → `${f.path}` in file tree onclick

## In Progress

- Reorganizing frontend files into `web/` folder (Dockerfile updated)

## Testing Commands

```bash
# Run tests
uv run pytest tests/test_skills.py -v

# Build and run Docker registry
docker-compose build && docker-compose up -d

# Configure and use HTTP registry
ch skill use-registry http://localhost:8080
ch skill list
```
