# Commands Reference

ContextHarness provides slash commands for use within OpenCode.

## Session Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/ctx {name}` | Create or switch to a session (creates git branch) | `/ctx login-feature` |
| `/contexts` | List all sessions with status | `/contexts` |
| `/compact` | Save current context to SESSION.md | `/compact` |

### `/ctx {name}`

Creates or switches to a named session:

```
/ctx login-feature
```

**What it does:**

1. Creates `.context-harness/sessions/login-feature/SESSION.md` (if new)
2. Creates `feature/login-feature` branch (if `gh` available)
3. Loads existing context if session exists
4. Updates SESSION.md with GitHub Integration section

### `/contexts`

Lists all available sessions with metadata:

```
/contexts
```

**Output:**

```
📁 Available Sessions:
- login-feature (Last: 2025-12-04, Status: In Progress)
- TICKET-1234 (Last: 2025-12-03, Status: Completed)
- api-rate-limiting (Last: 2025-12-02, Status: Blocked)
```

### `/compact`

Manually saves current context:

```
/compact
```

**What it does:**

1. Invokes `@compaction-guide` for recommendations
2. Updates SESSION.md with current state
3. Preserves decisions, file changes, documentation

!!! note
    Automatic compaction happens every 2nd user interaction, so manual `/compact` is usually not needed.

## GitHub Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/issue` | Create GitHub issue from current context | `/issue` |
| `/issue update` | Add progress comment to linked issue | `/issue update` |
| `/pr` | Create pull request for current branch | `/pr` |

### `/issue`

Creates a GitHub issue from session context:

```
/issue
```

**What it does:**

1. Gathers context from SESSION.md
2. Creates issue with `gh issue create`
3. Updates SESSION.md with issue link

### `/issue update`

Adds a progress comment to the linked issue:

```
/issue update
```

### `/pr`

Creates a pull request:

```
/pr
```

**What it does:**

1. Pushes current branch to origin
2. Creates PR with `gh pr create`
3. Links to related issue (if exists)
4. Updates SESSION.md with PR link

**Options:**

```
/pr --draft              # Create as draft PR
/pr --title "Custom"     # Use custom title
/pr --base develop       # Target different base branch
```

## Analysis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/baseline` | Analyze project and generate PROJECT-CONTEXT.md | `/baseline` |
| `/baseline --full` | Force full regeneration | `/baseline --full` |

### `/baseline`

Analyzes your project structure:

```
/baseline
```

**What it does:**

1. **Discovery**: Analyzes directory structure, language, tools
2. **Question Generation**: Creates 30-50 questions about the project
3. **Answer Generation**: Answers questions using codebase analysis

**Output:** `.context-harness/PROJECT-CONTEXT.md`

### `/baseline --full`

Forces complete regeneration, ignoring existing context:

```
/baseline --full
```
