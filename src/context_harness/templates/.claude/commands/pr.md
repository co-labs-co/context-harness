---
description: Create a pull request for the current session's branch with context from SESSION.md
allowed-tools: Read, Write, Bash, Glob
argument-hint: [--draft] [--title "title"] [--base branch]
---

Create pull request for current session.

## Instructions

1. Check prerequisites:
   - Active session with commits
   - On feature branch (not main/master)
   - GitHub remote configured
   - `gh` CLI authenticated

2. Gather PR content from SESSION.md:
   - Title from session name or current task
   - Summary from Active Work section
   - Key changes from Key Files
   - Decisions and rationale
   - Link to related issue

3. Push branch if needed: `git push -u origin HEAD`

4. Create PR: `gh pr create --title "[title]" --body "[body]"`

5. Update SESSION.md with PR link

## Flags

- `--draft`: Create as draft PR
- `--title "Custom title"`: Use custom title
- `--base branch`: Target different base branch

## PR Body Template

```markdown
## Summary
[Description from SESSION.md]

## Changes
[Key files and what changed]

## Decisions Made
[Important decisions and rationale]

## Related
- Closes #[issue] (if linked)

---
_Created via ContextHarness session: [name]_
```
