---
name: skill-release
description: Guide for creating, versioning, and releasing skills in a ContextHarness skills registry repository. Use when adding new skills to a registry repo, releasing skill versions, updating existing skills with proper conventional commit messages, troubleshooting release-please automation, understanding the release lifecycle, or managing the skill lifecycle in an init-repo scaffolded repository.
---

# Skill Release

Operational guide for authoring, versioning, and releasing skills within a ContextHarness skills registry repository (created via `context-harness skill init-repo`).

## Golden Rules

These three rules prevent the most common issues:

1. **Never edit `version.txt` manually** - release-please manages it
2. **Never edit `skills.json` manually** - CI rebuilds it after every release
3. **Never add `version` to SKILL.md frontmatter** - the version lives only in `version.txt`

## How Versioning Works

This registry uses **release-please** with the `simple` release type. Version bumps are fully automated based on conventional commit messages. The system uses **path-based detection** to attribute commits to skills based on which files they touch.

**Common misconception**: Commit scopes like `feat(my-skill): ...` are cosmetic only. Release-please determines which skill a commit belongs to by checking which files under `skill/<name>/` were modified, NOT by parsing the commit scope.

## Workflow 1: Create a New Skill

### Step 1 - Create the directory and files

```bash
mkdir -p skill/<skill-name>
```

### Step 2 - Create SKILL.md with frontmatter

```markdown
---
name: <skill-name>
description: Brief description of what this skill does
author: your-name
tags:
  - category
---

# Skill Title

Your skill content here...
```

**Requirements**:
- `name` must match the directory name exactly
- `description` is required and should explain both what the skill does AND when to use it
- Do NOT include a `version` field

### Step 3 - Bootstrap version.txt

```bash
echo "0.1.0" > skill/<skill-name>/version.txt
```

### Step 4 - Register with release-please

Add to `release-please-config.json` under `"packages"`:

```json
"skill/<skill-name>": {
  "release-type": "simple",
  "component": "<skill-name>"
}
```

Add to `.release-please-manifest.json`:

```json
"skill/<skill-name>": "0.1.0"
```

### Step 5 - Commit with feat: prefix

```bash
git add skill/<skill-name>/ release-please-config.json .release-please-manifest.json
git commit -m "feat: add <skill-name>"
git push origin main
```

The `feat:` prefix is critical - it is a releasable commit type that triggers release-please to create the initial release PR.

## Workflow 2: Update an Existing Skill

1. Edit the skill's `SKILL.md` (or any file in `skill/<skill-name>/`)
2. Commit with the appropriate conventional commit prefix:
   - `fix: correct typo in examples` - patch bump (0.1.0 -> 0.1.1)
   - `feat: add error handling section` - minor bump (0.1.0 -> 0.2.0)
   - `feat!: restructure skill format` - major bump (0.1.0 -> 1.0.0)
3. Push and merge to main
4. release-please automatically creates a release PR

## Workflow 3: Release Lifecycle

After a releasable commit merges to main:

```
1. release.yml triggers -> release-please-action runs
2. Detects changed paths under skill/<name>/
3. Creates release PR: "chore(main): release <name> X.Y.Z"
   - Bumps skill/<name>/version.txt
   - Generates/updates skill/<name>/CHANGELOG.md
4. Maintainer merges the release PR
5. release-please creates:
   - Git tag: <name>@vX.Y.Z
   - GitHub Release with changelog
6. sync-registry.yml triggers on version.txt change
7. Rebuilds skills.json automatically
8. Users detect update: context-harness skill outdated
```

**Key**: Steps 1-5 and steps 6-7 are separate workflow triggers. The registry sync only runs after the release PR is merged (which bumps version.txt).

## Commit Convention Quick Reference

| Prefix | Version Bump | Use When |
|--------|-------------|----------|
| `fix:` | Patch (0.0.x) | Correcting errors, typos, broken examples |
| `feat:` | Minor (0.x.0) | Adding new content, sections, examples |
| `feat!:` | Major (x.0.0) | Restructuring, breaking format changes |
| `docs:` | No release | README, CONTRIBUTING changes (not skill content) |
| `chore:` | No release | Formatting, cleanup, CI config |
| `refactor:` | No release | Reorganizing without adding/fixing |

**For skill content changes, always use `feat:` or `fix:`**. Using `docs:` or `chore:` for SKILL.md edits will NOT trigger a release.

### Version Override

Force a specific version with the `Release-As` trailer:

```bash
git commit --allow-empty -m "chore: release 2.0.0" -m "Release-As: 2.0.0"
```

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Using `docs:` for skill edits | No release PR created | Use `feat:` or `fix:` for any SKILL.md change |
| Adding `version` to frontmatter | Validation failure on PR | Remove it; version lives in `version.txt` only |
| Forgetting release-please registration | No release PR for new skill | Add to both config and manifest JSON files |
| Editing `version.txt` manually | Version conflict with release-please | Revert; let release-please manage it |
| Editing `skills.json` manually | Overwritten on next release | Let sync-registry.yml rebuild it |
| `name` != directory name | Validation failure | Ensure frontmatter `name` matches exactly |
| Missing `version.txt` for new skill | release-please cannot bootstrap | Create with `echo "0.1.0" > skill/<name>/version.txt` |

## Multi-Skill Commits

If a single commit modifies files in multiple skill directories, release-please creates **separate release PRs** for each skill (due to `separate-pull-requests: true` in the config). Each skill is versioned independently.

## Troubleshooting

For detailed troubleshooting with diagnostic commands, see [references/troubleshooting.md](references/troubleshooting.md).

Quick checks:
- **No release PR appearing?** Verify commit used `feat:` or `fix:` prefix, and check Actions tab for release.yml runs
- **skills.json not updated?** Only updates after a release PR merge; check sync-registry.yml runs
- **Validation failing?** Run `python scripts/validate_skills.py` locally

## File Reference

These files in the registry repo are relevant to the release process:

| File | Owner | Purpose |
|------|-------|---------|
| `skill/<name>/SKILL.md` | Author | Skill content (no version field) |
| `skill/<name>/version.txt` | release-please | Current version (CI-managed) |
| `skill/<name>/CHANGELOG.md` | release-please | Generated changelog |
| `release-please-config.json` | Author (add only) | Per-skill release config |
| `.release-please-manifest.json` | release-please | Current versions (CI-managed after bootstrap) |
| `skills.json` | CI | Auto-rebuilt registry manifest |
| `CONTRIBUTING.md` | Reference | Full authoring guidelines |
| `QUICKSTART.md` | Reference | First-skill tutorial |
