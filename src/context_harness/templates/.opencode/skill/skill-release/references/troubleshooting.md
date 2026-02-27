# Troubleshooting Guide

Diagnostic procedures for common issues in the skills registry release pipeline.

## Decision Tree

### Release PR not created after merge

```
1. Was the commit prefix releasable? (feat: or fix:)
   NO  -> Recommit with feat: or fix: prefix
   YES -> Continue

2. Did the commit touch files under skill/<name>/?
   NO  -> release-please uses path-based detection, not commit scope
   YES -> Continue

3. Is the skill registered in release-please-config.json?
   NO  -> Add package entry and re-push
   YES -> Continue

4. Did the release.yml workflow run?
   Check: gh run list --workflow=release.yml --limit=5
   NO  -> Check workflow trigger (must be push to main)
   YES -> Check the run logs for errors
```

### skills.json not updated after release

```
1. Was the release PR actually merged (not just the feature PR)?
   NO  -> Merge the release PR first
   YES -> Continue

2. Did sync-registry.yml trigger?
   Check: gh run list --workflow=sync-registry.yml --limit=5
   NO  -> sync-registry triggers on skill/*/version.txt changes
         The release PR must bump version.txt
   YES -> Check logs for errors

3. Manual rebuild:
   python scripts/sync-registry.py
   git add skills.json
   git commit -m "chore: sync skills.json [skip ci]"
   git push
```

### Validation failing on PR

```
1. Check the validation report:
   python scripts/validate_skills.py

2. Common failures:
   - "missing SKILL.md" -> Create the file
   - "name does not match directory" -> Align frontmatter name with dir name
   - "remove 'version' from frontmatter" -> Delete version field from SKILL.md
   - "missing version.txt" -> echo "0.1.0" > skill/<name>/version.txt
   - "invalid frontmatter" -> Check YAML syntax in SKILL.md header
```

### Release created wrong version

```
1. Check which commits release-please included:
   gh pr view <release-pr-number> --json body

2. If version is wrong, use Release-As override:
   git commit --allow-empty -m "chore: release X.Y.Z" -m "Release-As: X.Y.Z"

3. If a release was already tagged incorrectly:
   - Delete the GitHub Release via UI or API
   - Delete the git tag: git push --delete origin <tag>
   - Update .release-please-manifest.json to correct version
   - Push a new releasable commit to trigger fresh release PR
```

## Diagnostic Commands

### Check release-please status

```bash
# Recent release workflow runs
gh run list --workflow=release.yml --limit=5

# Pending release PRs
gh pr list --label "autorelease: pending"

# Tagged releases
gh pr list --label "autorelease: tagged"

# View a specific workflow run's logs
gh run view <run-id> --log
```

### Check sync-registry status

```bash
# Recent sync workflow runs
gh run list --workflow=sync-registry.yml --limit=5

# View current skills.json
cat skills.json | python -m json.tool

# Manually rebuild and diff
python scripts/sync-registry.py
git diff skills.json
```

### Check skill commit history

```bash
# Commits touching a specific skill
git log --oneline -- skill/<skill-name>/

# Check which files a commit touched
git show --stat <commit-hash>

# Verify release-please manifest state
cat .release-please-manifest.json | python -m json.tool
```

### Validate locally before pushing

```bash
# Run validation script
python scripts/validate_skills.py

# Check frontmatter of a specific skill
python -c "
import frontmatter
post = frontmatter.load('skill/<name>/SKILL.md')
print(post.metadata)
"
```

## Known release-please Quirks

1. **`releases_created` output is unreliable in v4** - Use per-path outputs instead: `steps.release.outputs['skill/name--release_created']`

2. **Do not use `@` in skill names** - Known bug (#2661) causes tag parsing failures

3. **First release for new skill** - The initial `feat: add <name>` commit triggers the first release PR. This bumps from the bootstrapped 0.1.0 to the appropriate next version (0.2.0 for feat, 0.1.1 for fix).

4. **`python-frontmatter` pip name vs import** - Install with `pip install python-frontmatter`, but import as `import frontmatter`

5. **`[skip ci]` in sync-registry commits** - The sync-registry workflow uses `[skip ci]` to prevent infinite workflow loops when it commits the updated skills.json
