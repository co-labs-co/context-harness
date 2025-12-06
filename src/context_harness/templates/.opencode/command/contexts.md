---
description: List all ContextHarness sessions
agent: context-harness
---

List all available sessions in `.context-harness/sessions/`.

## Instructions

1. **Scan sessions directory**: List all directories in `.context-harness/sessions/`

2. **For each session**, read the SESSION.md and extract:
   - Session name (directory name)
   - Last Updated timestamp
   - Current Status (from Active Work section)
   - Current Task (from Active Work section)

3. **Display formatted list**:
   ```
   📁 Available Sessions
   
   | Session | Status | Last Updated | Current Task |
   |---------|--------|--------------|--------------|
   | {name1} | {status} | {date} | {task} |
   | {name2} | {status} | {date} | {task} |
   ...
   
   ---
   
   Switch to a session: `/ctx {session-name}`
   Create a new session: `/ctx {new-name}`
   ```

4. **If no sessions exist**:
   ```
   📁 No sessions found
   
   Create your first session with:
   /ctx {session-name}
   
   Examples:
   - /ctx login-feature
   - /ctx TICKET-1234
   - /ctx api-refactor
   ```

5. **If current session is active**, mark it in the list:
   ```
   | **{name}** ← current | {status} | {date} | {task} |
   ```
