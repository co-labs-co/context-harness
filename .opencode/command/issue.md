---
description: Create or update a GitHub issue for the current session
agent: context-harness
---

GitHub issue command: $ARGUMENTS

## Instructions

### Parse Command

Parse $ARGUMENTS to determine the action:
- `/issue` or `/issue create` - Create a new issue for current session
- `/issue update` - Add current context as a comment to existing issue
- `/issue view` - Display current issue information

### `/issue` or `/issue create` - Create Issue

1. **Check prerequisites**:
   - Must have an active session (SESSION.md exists)
   - Must be in a git repo with GitHub remote
   - Must have `gh` CLI installed and authenticated

2. **Gather context for issue body**:
   - Current task description from SESSION.md
   - Key files being modified
   - Recent decisions made
   - Documentation references found
   - Any blockers identified

3. **Create the issue** using `gh issue create`:
   ```bash
   gh issue create --title "[title from session]" --body "[structured body]"
   ```

4. **Update SESSION.md** with issue link:
   ```markdown
   ## GitHub Integration
   
   **Branch**: [branch name]
   **Issue**: #[number] - [url]
   **PR**: (none yet)
   ```

5. **Confirm to user**:
   ```
   ✅ GitHub Issue #[N] created: [title]
      [url]
   
   The issue includes:
   - Task description
   - Key files: [list]
   - Decisions made: [count]
   - Documentation links: [count]
   ```

### `/issue update` - Update Existing Issue

1. **Check prerequisites**:
   - Must have an active session with linked issue
   - Read issue number from SESSION.md GitHub Integration section

2. **Gather new context since last update**:
   - New files modified
   - New decisions made
   - New documentation found
   - Progress updates
   - Blockers encountered or resolved

3. **Add comment to issue** using `gh issue comment`:
   ```bash
   gh issue comment [number] --body "[update content]"
   ```

4. **Confirm to user**:
   ```
   ✅ Added update to Issue #[N]
   
   Update includes:
   - [summary of what was added]
   ```

### `/issue view` - View Issue

1. **Read issue number from SESSION.md**

2. **Fetch issue details** using `gh issue view`:
   ```bash
   gh issue view [number] --json title,body,state,comments
   ```

3. **Display to user**:
   ```
   📋 Issue #[N]: [title]
      Status: [open/closed]
      URL: [url]
      
      [body summary]
      
      Recent comments: [count]
   ```

## Error Handling

- **No active session**: "No active session. Use `/ctx [name]` to start a session first."
- **No GitHub remote**: "This repository doesn't have a GitHub remote. Issue tracking unavailable."
- **No gh CLI**: "GitHub CLI (gh) is not installed. Install it from https://cli.github.com"
- **Not authenticated**: "GitHub CLI is not authenticated. Run `gh auth login` first."
- **No linked issue**: "No issue linked to this session. Use `/issue create` first."
