---
description: Create a pull request for the current session's branch
agent: context-harness
---

Create pull request: $ARGUMENTS

## Instructions

### Prerequisites Check

1. **Must have an active session** with SESSION.md
2. **Must be on a feature branch** (not main/master)
3. **Must have GitHub remote** and `gh` CLI authenticated
4. **Should have commits** to include in PR

### Parse Arguments

- `/pr` - Create PR with auto-generated title and body
- `/pr --draft` - Create as draft PR
- `/pr --title "Custom title"` - Use custom title
- `/pr --base develop` - Target a different base branch (default: repo's default branch)

### Create Pull Request

1. **Gather PR content from SESSION.md**:
   - **Title**: Derive from session name or Current Task
   - **Body**: 
     - Summary from Active Work section
     - Key changes from Key Files section
     - Decisions made and rationale
     - Link to related issue (if exists)
     - Documentation references

2. **Push current branch** (if not already pushed):
   ```bash
   git push -u origin HEAD
   ```

3. **Create PR** using `gh pr create`:
   ```bash
   gh pr create --title "[title]" --body "[body]" [--draft] [--base branch]
   ```

4. **Link to issue** (if session has linked issue):
   - Include "Closes #[issue]" or "Fixes #[issue]" in body
   - Or use `--body` with issue reference

5. **Update SESSION.md** with PR link:
   ```markdown
   ## GitHub Integration
   
   **Branch**: feature/[session-name]
   **Issue**: #[N] - [url]
   **PR**: #[N] - [url]
   ```

6. **Confirm to user**:
   ```
   ✅ Pull Request #[N] created: [title]
      [url]
   
   - Base: [target branch]
   - Status: [ready/draft]
   - Linked to: Issue #[N] (if applicable)
   
   The PR includes:
   - [X] commits from feature/[session-name]
   - Summary of changes
   - Context from session
   ```

### PR Body Template

```markdown
## Summary

[Description from SESSION.md Active Work]

## Changes

[List of key files and what was changed]

## Decisions Made

[Important decisions and rationale from session]

## Related

- Closes #[issue number] (if linked)

## Documentation

[Links referenced during development]

---

_Created via ContextHarness session: [session-name]_
```

## Error Handling

- **No active session**: "No active session. Use `/ctx [name]` to start a session first."
- **On default branch**: "You're on the default branch. Create a feature branch first with `/ctx [name]`."
- **No commits**: "No commits to create PR from. Make some changes and commit first."
- **Push failed**: "Failed to push branch. Check your permissions and try again."
- **PR already exists**: "A PR already exists for this branch: [url]"
