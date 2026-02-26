---
description: Create, update, or view GitHub issues linked to the current session
allowed-tools: Read, Write, Bash, Glob
argument-hint: [create|update|view]
---

Manage GitHub issues for current session.

## Instructions

### `/issue` or `/issue create` - Create Issue

1. Check prerequisites:
   - Active session exists
   - In git repo with GitHub remote
   - `gh` CLI installed and authenticated

2. Gather context from SESSION.md:
   - Current task description
   - Key files being modified
   - Recent decisions
   - Documentation references

3. Create issue: `gh issue create --title "[title]" --body "[body]"`

4. Update SESSION.md with issue link

### `/issue update` - Update Existing Issue

1. Read issue number from SESSION.md
2. Gather new context since last update
3. Add comment: `gh issue comment [number] --body "[update]"`

### `/issue view` - View Issue

1. Read issue number from SESSION.md
2. Fetch details: `gh issue view [number]`
3. Display summary to user

## Error Handling

- No active session: "Use `/ctx [name]` first"
- No GitHub remote: "Issue tracking unavailable"
- No gh CLI: "Install from https://cli.github.com"
