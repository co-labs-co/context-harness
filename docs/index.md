# ContextHarness

Context-aware agent framework for [OpenCode](https://opencode.ai) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that maintains session continuity.

## What is ContextHarness?

ContextHarness solves a fundamental problem with AI coding assistants: **context loss**. When you're working on a feature across multiple sessions, you lose all the context from previous conversations—the decisions made, files modified, documentation referenced, and progress achieved.

ContextHarness maintains a `SESSION.md` file for each feature/task you work on. When you run `/compact`, your current work context is saved. When you switch sessions with `/ctx`, the previous context is preserved and the new session's context is loaded.

## Supported Tools

ContextHarness works with both major AI coding assistants:

| Tool | Description |
|------|-------------|
| **[OpenCode](https://opencode.ai)** | Open-source AI coding assistant |
| **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** | Anthropic's VS Code extension and CLI |

By default, ContextHarness installs support for **both tools** simultaneously, allowing you to use whichever fits your workflow.

## Quick Start

```bash
# Install (one-time)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Initialize in your project
ch init                    # or: context-harness init
```

=== "OpenCode"

    ```bash
    # Open OpenCode and start working
    /baseline              # Analyze project (first time)
    /ctx my-feature        # Create session + branch
    # ... do your work ...
    /compact               # Save context
    /pr                    # Create pull request
    ```

=== "Claude Code"

    ```bash
    # Open Claude Code and start working
    /baseline              # Analyze project (first time)
    /ctx my-feature        # Create session + branch
    # ... do your work ...
    /compact               # Save context
    /pr                    # Create pull request
    ```

That's it. Your context persists across sessions.

## Key Features

- **Session Management**: Named sessions (feature branches, ticket IDs) with persistent context
- **Automatic Compaction**: Context is saved every 2nd user interaction
- **GitHub Integration**: Automatic branch creation, issue tracking, PR creation
- **Subagent System**: Research and documentation lookup via Context7 MCP
- **Skill System**: Install pre-built patterns and workflows

## How It Differs from Other Approaches

| Approach | Limitation | ContextHarness Solution |
|----------|------------|-------------------------|
| Single long conversation | Context window overflow | Incremental compaction to SESSION.md |
| Starting fresh each time | Lose all context | Named sessions persist across conversations |
| Manual note-taking | Easy to forget, inconsistent | Structured SESSION.md with guided compaction |
| Multiple agents executing | Conflicts, confusion | Single executor with advisory subagents |

## Next Steps

- [Installation](getting-started/installation.md) — Get ContextHarness set up
- [Quick Start](getting-started/quickstart.md) — Start your first session
- [Commands Reference](user-guide/commands.md) — All available commands
