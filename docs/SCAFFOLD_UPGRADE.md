# Scaffold Upgrade Maintenance Guide

This document describes the process for maintaining the `upgrade-repo` command when adding new scaffold files to `init-repo`.

## Overview

The `init-repo` command creates a complete skills registry scaffold. The `upgrade-repo` command allows existing registries to receive updates to this scaffold. When you add new files to the scaffold, you MUST also update the upgrade mechanism.

## Files to Update

When adding a new scaffold file, you must update **all three** of these locations:

### 1. `_write_registry_scaffold()` method
Add the call to your new writer method in `src/context_harness/services/skill_service.py`:

```python
def _write_registry_scaffold(self, repo_path: Path, repo_name: str) -> None:
    # ... existing code ...

    # Add your new writer call here
    self._write_scaffold_my_new_file(repo_path)
```

### 2. `_get_scaffold_files_to_update()` list
Add the file path to the appropriate list in `src/context_harness/services/skill_service.py`:

```python
def _get_scaffold_files_to_update(self, repo_path: Path, current_version: str, *, force: bool = False) -> list[str]:
    # Infrastructure files - safe to update (rarely user-modified)
    infrastructure_files = [
        # ... existing files ...
        "path/to/my_new_file.ext",  # Add here if infrastructure
    ]

    # OR for documentation (only updated if missing or with --force)
    documentation_files = [
        # ... existing files ...
        "MY_NEW_DOC.md",  # Add here if documentation
    ]
```

### 3. `_write_single_scaffold_file()` writers dictionary
Add the mapping in `src/context_harness/services/skill_service.py`:

```python
def _write_single_scaffold_file(self, repo_path: Path, file_path: str, repo_name: str) -> None:
    writers = {
        # ... existing mappings ...

        # If the writer doesn't need repo_name:
        "path/to/my_new_file.ext": self._write_scaffold_my_new_file,

        # If the writer needs repo_name:
        "path/to/my_new_file.ext": lambda p: self._write_scaffold_my_new_file(p, repo_name),
    }
```

## Current Scaffold Files

### Infrastructure Files (safe to overwrite)
| File | Writer Method | Notes |
|------|---------------|-------|
| `.github/workflows/release.yml` | `_write_scaffold_release_workflow` | Release automation |
| `.github/workflows/sync-registry.yml` | `_write_scaffold_sync_registry_workflow` | Post-release sync |
| `.github/workflows/validate-skills.yml` | `_write_scaffold_validate_skills_workflow` | Skill validation |
| `.github/workflows/auto-rebase.yml` | `_write_scaffold_auto_rebase_workflow` | Auto PR rebase |
| `.github/ISSUE_TEMPLATE/new-skill.md` | `_write_scaffold_issue_template` | Skill request template |
| `.github/PULL_REQUEST_TEMPLATE.md` | `_write_scaffold_pr_template` | PR template |
| `scripts/sync_registry.py` | `_write_scaffold_sync_registry_script` | Registry sync script |
| `scripts/validate_skills.py` | `_write_scaffold_validate_skills_script` | Validation script |
| `Dockerfile` | `_write_scaffold_dockerfile` | Container build |
| `docker-compose.yml` | `_write_scaffold_docker_compose` | Local deployment |
| `registry/nginx.conf` | `_write_scaffold_nginx_conf` | Nginx config with CORS |
| `registry/web/index.html` | `_write_scaffold_index_html` | Skill listing page |
| `registry/web/skill.html` | `_write_scaffold_skill_html` | Skill detail page |
| `.releaseplease.json` | `_write_scaffold_release_please_config` | Release config |
| `.release-please-manifest.json` | `_write_scaffold_release_please_manifest` | Version manifest |
| `.gitignore` | `_write_scaffold_gitignore` | Git ignore rules |

### Documentation Files (only if missing or with --force)
| File | Writer Method | Notes |
|------|---------------|-------|
| `README.md` | `_write_scaffold_readme` | Main documentation |
| `CONTRIBUTING.md` | `_write_scaffold_contributing` | Contribution guide |
| `QUICKSTART.md` | `_write_scaffold_quickstart` | Quick start guide |

### Special Files (not in upgrade list)
| File | Writer Method | Notes |
|------|---------------|-------|
| `.registry-version` | `_write_scaffold_registry_version` | Always updated |
| `skills.json` | `_write_scaffold_skills_json` | Version markers only |
| `marketplace.json` | `_write_scaffold_marketplace_json` | Version markers only |
| `skill/*` | Various | User-owned, never touched |

## Upgrade Behavior

### Normal Mode (no flags)
- Only adds **missing** scaffold files
- Preserves all existing files
- Updates version markers in skills.json and marketplace.json

### Force Mode (`--force`)
- Overwrites **all** scaffold files (infrastructure + documentation)
- Still preserves user skills and skills.json content
- Updates version markers

### Dry Run Mode (`--dry-run`)
- Shows what would be updated without making changes
- Returns list of files in `files_to_update`

### Check Mode (`--check`)
- Only checks if upgrade is available
- Returns `upgrade_available: true/false`

## Testing Checklist

When adding a new scaffold file, verify:

- [ ] File is created by `init-repo` (run `test_scaffold_writes_all_expected_files`)
- [ ] File is in `_get_scaffold_files_to_update` list
- [ ] File has a mapping in `_write_single_scaffold_file` writers
- [ ] `upgrade-repo --dry-run` shows the new file for legacy registries
- [ ] `upgrade-repo --force` overwrites the file
- [ ] `upgrade-repo` (no flags) doesn't overwrite existing file

## Future Improvements

Consider implementing these patterns from other tools:

1. **Manifest File** - Track scaffold files with checksums (like Cookiecutter)
2. **Three-Way Merge** - Intelligently merge user customizations (like Rails)
3. **File Classification** - Mark files as overwritable/mergeable/user-owned
4. **Interactive Prompts** - Ask user how to handle each modified file

## Related Files

- `src/context_harness/services/skill_service.py` - Main implementation
- `tests/unit/services/test_skill_service.py` - Test coverage
- `src/context_harness/interfaces/cli/skill_cmd.py` - CLI command
