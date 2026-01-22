---
description: List all available ContextHarness sessions with their status and metadata
allowed-tools: Read, Glob
---

List all available sessions.

## Instructions

1. Scan `.context-harness/sessions/` for all session directories
2. For each session, read SESSION.md and extract:
   - Session name
   - Status (In Progress/Completed/Blocked)
   - Last updated timestamp
   - Current task summary
3. Display formatted table of sessions

## Output Format

```
Available Sessions:

| Session | Status | Last Updated | Current Task |
|---------|--------|--------------|--------------|
| [name]  | [status] | [date]     | [task]       |
```
