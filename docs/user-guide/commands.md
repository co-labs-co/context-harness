# Commands Reference

ContextHarness provides slash commands for use within OpenCode and Claude Code.

!!! info "Same Commands, Both Tools"
    All ContextHarness commands work identically in both OpenCode and Claude Code. The commands are defined in tool-specific directories but provide the same functionality.

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
    Use `/compact` regularly during long sessions — especially after significant progress, key decisions, or before context gets too large.

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
| `/baseline` | Analyze project and generate PROJECT-CONTEXT.md + AGENTS.md | `/baseline` |
| `/baseline --path` | Analyze specific directory (monorepo support) | `/baseline --path apps/frontend` |
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
4. **Skill Extraction**: Identifies patterns for reusable skills
5. **Memory File Generation**: Creates AI agent instructions

**Output:**

=== "OpenCode"

    - `PROJECT-CONTEXT.md` — Comprehensive project context
    - `AGENTS.md` — AI agent instructions (OpenCode rules file)

=== "Claude Code"

    - `PROJECT-CONTEXT.md` — Comprehensive project context
    - `CLAUDE.md` — AI agent instructions (Claude Code memory file)

### `/baseline --path`

Analyzes a specific directory within a monorepo:

```
/baseline --path apps/frontend
```

**What it does:**

1. Scopes analysis to the target directory only
2. Generates outputs in the target directory:
   - `apps/frontend/PROJECT-CONTEXT.md`
   - `apps/frontend/AGENTS.md`
3. Creates self-contained AGENTS.md (no inheritance from root)

**Use cases:**

- Monorepos with multiple projects (apps, packages, services)
- Polyglot repos where different directories use different languages
- Large repos where full analysis is too slow

**Examples:**

```
/baseline --path apps/frontend      # Analyze frontend app
/baseline --path packages/shared    # Analyze shared package
/baseline --path services/api       # Analyze API service

# Combine with other flags
/baseline --path apps/web --skip-skills --verbose
/baseline --path packages/ui --agents-only
```

!!! note "AGENTS.md vs CLAUDE.md Precedence"
    Both OpenCode and Claude Code read the **nearest** memory file in the directory tree. Per the [AGENTS.md standard](https://agents.md/), nested files completely override root files (no merging). This is why `/baseline --path` generates self-contained memory files.

!!! info "Git Repository Recommended"
    The `--path` flag uses git to find the repository root for shared skill placement. Skills are written to `{repo_root}/.opencode/skill/` so they can be shared across all projects in a monorepo.
    
    **Without git**: Skills are placed in the target directory instead, and skill references may need manual adjustment.

### `/baseline --full`

Forces complete regeneration, ignoring existing context:

```
/baseline --full
```
