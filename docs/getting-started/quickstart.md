# Quick Start

This guide walks you through your first ContextHarness session.

## 1. Analyze Your Project (First Time Only)

=== "OpenCode"

    Open OpenCode in your project directory and run:
    
    ```
    /baseline
    ```

=== "Claude Code"

    Open Claude Code in your project directory and run:
    
    ```
    /baseline
    ```

This analyzes your codebase and generates:

=== "OpenCode"

    - `PROJECT-CONTEXT.md` — Information about your project's structure, patterns, and conventions
    - `AGENTS.md` — AI agent instructions for working with your codebase

=== "Claude Code"

    - `PROJECT-CONTEXT.md` — Information about your project's structure, patterns, and conventions
    - `CLAUDE.md` — AI agent instructions for working with your codebase

!!! tip "Working in a Monorepo?"
    Use `--path` to analyze specific projects:
    ```
    /baseline --path apps/frontend
    ```
    This generates `apps/frontend/PROJECT-CONTEXT.md` and the appropriate memory file for that specific project.

## 2. Start a Session

```
/ctx login-feature
```

This:

- Creates a new session at `.context-harness/sessions/login-feature/`
- Creates a git branch `feature/login-feature` (if `gh` is available)
- Initializes `SESSION.md` for tracking your work

## 3. Do Your Work

Work on your feature as usual. The agent will:

- Track modified files
- Record important decisions
- Save documentation references

## 4. Save Your Context

Manually save your progress:

```
/compact
```

!!! tip "Automatic Compaction"
    ContextHarness automatically compacts every 2nd user interaction, so you don't always need to run this manually.

## 5. Create a Pull Request

When you're done:

```
/pr
```

This creates a GitHub PR with:

- Summary from your session context
- List of changes
- Link to related issue (if created with `/issue`)

## Typical Workflow

=== "OpenCode"

    ```
    /ctx login-feature          # Start session + branch
    # ... work on login ...
    /compact                    # Save progress (optional)
    # ... more work ...
    /issue                      # Create GitHub issue from context
    # ... finish feature ...
    /pr                         # Create pull request
    ```

=== "Claude Code"

    ```
    /ctx login-feature          # Start session + branch
    # ... work on login ...
    /compact                    # Save progress (optional)
    # ... more work ...
    /issue                      # Create GitHub issue from context
    # ... finish feature ...
    /pr                         # Create pull request
    ```

!!! info "Same Commands, Same Workflow"
    ContextHarness commands work identically in both OpenCode and Claude Code. The only differences are the folder structure and configuration files.

## Switching Sessions

You can work on multiple features:

```
/ctx login-feature          # Work on login
/ctx api-refactor           # Switch to API work (login context saved)
/contexts                   # List all sessions
/ctx login-feature          # Return to login (context restored)
```

## Next Steps

- [Commands Reference](../user-guide/commands.md) — All available commands
- [Sessions](../user-guide/sessions.md) — Deep dive into session management
