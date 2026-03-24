# HTTP Registry & Plugin Marketplace Support

**Session ID**: http-registry-marketplace
**Branch**: worktree-twinkling-spinning-ripple
**PR**: #102
**Issue**: #101
**Compaction Cycle**: 3
**Last Updated**: 2026-03-23

## Summary

Extended the HTTP registry support with plugin marketplace compatibility features for Claude Code and other AI coding assistants. Added scaffold files for hosting skills registries via HTTP with Docker/nginx. Includes collapsible sections for AI agent instructions and skill building guide. Added `upgrade-repo` command for upgrading legacy registries.

## Completed Features

### 1. Registry Version Tracking
- `.registry-version` file for scaffold version detection
- `registry_version` field in skills.json and marketplace.json
- Schema version bumped to 1.1
- Legacy registries (without version file) detected as version "0.0.0"

### 2. Upgrade-Repo Command
```bash
ch skill upgrade-repo [path]        # Interactive upgrade
ch skill upgrade-repo --check       # Only check for updates
ch skill upgrade-repo --dry-run     # Preview changes
ch skill upgrade-repo --force       # Overwrite without prompting
```

### 3. Marketplace.json
Standardized manifest for plugin marketplace discovery:
- Registry metadata (name, URL, compatibility)
- Skills list synced alongside skills.json
- Schema versioning for future format migrations

### 4. HTTP Registry Hosting (Docker/nginx)
- `Dockerfile` - nginx-based container for serving skills
- `docker-compose.yml` - easy local deployment
- `registry/nginx.conf` - CORS-enabled nginx configuration
- `registry/web/index.html` - skill listing with collapsible sections
- `registry/web/skill.html` - individual skill page with file explorer

### 5. Collapsible Sections (index.html)
- **"For AI Agents"** - Instructions for non-CLI users to point AI agents at the registry
- **"Build a Skill"** - Guide for creating and contributing skills
- CSS transitions for smooth expand/collapse animations
- `toggleSection()` JavaScript function for interactivity

### 6. Updated sync-registry.py
- Now regenerates both `skills.json` and `marketplace.json`
- Preserves existing marketplace metadata when updating

## Key Files Modified

| File | Changes |
|------|---------|
| `skill_service.py` | Added `upgrade_registry_repo()`, version tracking, HTTP registry scaffold |
| `skill_cmd.py` | Added `upgrade-repo` CLI command |
| `skills.py` | Added `upgrade_repo()` wrapper function |
| `primitives/skill.py` | Added `RegistryUpgradeStatus` enum |

## New Scaffold Methods

- `_write_scaffold_registry_version` - Creates .registry-version file
- `_write_scaffold_marketplace_json` - Creates marketplace.json
- `_write_scaffold_http_registry` - Orchestrates HTTP registry scaffold
- `_write_scaffold_dockerfile` - Docker nginx setup
- `_write_scaffold_docker_compose` - Docker Compose configuration
- `_write_scaffold_nginx_conf` - CORS-enabled nginx config
- `_write_scaffold_index_html` - Web frontend with collapsible sections
- `_write_scaffold_skill_html` - Web frontend for individual skill page

## Testing

```bash
uv run pytest tests/unit/services/test_skill_service.py -v
docker-compose build && docker-compose up -d
```

## Recent Commits

- `feat(skill): add registry version tracking for upgrade-repo command`
- `feat(scaffold): add collapsible sections for AI agents and skill building`

## Status

Ready for PR review and merge.
