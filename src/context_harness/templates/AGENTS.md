# Project Memory

This file is read by OpenCode agents to understand project context and conventions.

## ContextHarness Framework

This project uses the ContextHarness framework for AI-assisted development with context preservation.

### Available Commands

| Command | Description |
|---------|-------------|
| `/ctx <name>` | Switch to or create a session |
| `/contexts` | List all available sessions |
| `/compact` | Save context to SESSION.md |
| `/baseline` | Generate PROJECT-CONTEXT.md |
| `/issue` | GitHub issue management |
| `/pr` | Create pull request |

### Session Management

Sessions are stored in `.context-harness/sessions/<name>/SESSION.md`.

Use `/compact` regularly during long sessions to preserve context before it's lost to context window limits.

### Subagents

The framework uses specialized subagents for research and guidance:
- `@research-subagent` - API lookups, best practices
- `@docs-subagent` - Documentation research
- `@compaction-guide` - Context preservation advice
- `@baseline-*` - Project analysis phases

### Key Directories

- `.context-harness/` - Session data and project context
- `.opencode/` - OpenCode configuration (agent, command, skill)

---

_Add project-specific notes below this line_
