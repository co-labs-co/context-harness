# ContextHarness

> A context-aware agent framework for OpenCode.ai that maintains session continuity through user-driven compaction cycles.

## Problem

Long development sessions with AI assistants suffer from context loss. As conversations grow, important decisions, file changes, and work progress get pushed out of the context window. Starting fresh means losing valuable continuity.

## Solution

ContextHarness solves this by:

1. **Named Sessions**: Work on multiple features/tickets simultaneously, each with its own persistent context
2. **User-Driven Compaction**: Save context when you need it with `/compact` or choose it from options
3. **SESSION.md**: A living document that preserves decisions, file changes, and next steps
4. **Single Executor Pattern**: One primary agent executes all work; specialized subagents provide guidance only

## Quick Start

### 1. Start a Session

```
@context-harness /session login-feature
@context-harness /session TICKET-1234
```

### 2. Work Normally

The primary agent handles all execution—writing code, modifying files, running commands.

### 3. Compact When Ready

Save your context at any time:
```
/compact
```

Or select the compaction option from "What's Next?" suggestions.

### 4. Switch Sessions

```
/session api-rate-limiting
/sessions  # List all sessions
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  CONTEXT-HARNESS AGENT                  │
│  - Executes ALL work (code, files, commands)            │
│  - Manages named sessions                               │
│  - Reads/writes SESSION.md                              │
│  - Invokes subagents for guidance only                  │
└────────────┬──────────────────────────────────┬─────────┘
             │                                  │
      @research-subagent               @compaction-guide
      @docs-subagent                          │
             │                                  │
             ▼                                  ▼
┌─────────────────────────┐       ┌────────────────────────┐
│ Research & Docs         │       │ Compaction Guide       │
│ Subagents               │       │ Subagent               │
│ - Provide guidance      │       │ - Analyze session      │
│ - Return recommendations│       │ - Recommend what to    │
│ - NO execution          │       │   preserve             │
└─────────────────────────┘       └────────────────────────┘
```

## Directory Structure

```
context-harness/
├── .context-harness/
│   ├── sessions/                  # Named session directories
│   │   ├── login-feature/
│   │   │   └── SESSION.md
│   │   ├── TICKET-1234/
│   │   │   └── SESSION.md
│   │   └── api-rate-limiting/
│   │       └── SESSION.md
│   ├── templates/
│   │   └── session-template.md    # Template for new sessions
│   └── README.md                  # Framework documentation
├── .opencode/
│   └── agent/
│       ├── context-harness.md     # Primary executor agent
│       ├── compaction-guide.md    # Compaction advisory subagent
│       ├── docs-subagent.md       # Documentation advisory subagent
│       └── research-subagent.md   # Research advisory subagent
└── README.md                      # This file
```

## Commands

| Command | Description |
|---------|-------------|
| `/session {name}` | Switch to or create a named session |
| `/sessions` | List all available sessions |
| `/compact` | Save current context to SESSION.md |

## Session Naming

Use meaningful names that match your workflow:

- **Feature names**: `login-feature`, `oauth-integration`, `dashboard-redesign`
- **Ticket IDs**: `TICKET-1234`, `JIRA-567`, `GH-89`
- **Story IDs**: `STORY-456`, `US-789`

## How SESSION.md Works

Each session maintains a `SESSION.md` file with:

| Section | Purpose |
|---------|---------|
| **Active Work** | Current task, status, blockers |
| **Key Files** | Files being modified with purposes |
| **Decisions Made** | Important decisions with rationale |
| **Documentation References** | Relevant docs with links |
| **Next Steps** | Prioritized action items |
| **Completed This Session** | Archived completed work |

## Subagents

### @research-subagent
Provides research guidance on best practices, API documentation, and implementation approaches. **Advisory only—does not execute.**

### @docs-subagent
Provides documentation summaries, framework guides, and API references. **Advisory only—does not execute.**

### @compaction-guide
Analyzes current work and recommends what to preserve during compaction. **Advisory only—does not execute.**

## Best Practices

1. **Use meaningful session names** - Makes it easy to find and resume work
2. **Compact regularly** - Before breaks, after completing tasks, when conversations get long
3. **Trust the primary agent** - It's the sole executor; subagents only advise
4. **Check Next Steps** - Resume work exactly where you left off
5. **Don't delete SESSION.md** - It's your context lifeline

## Requirements

- [OpenCode.ai](https://opencode.ai) with agent support
- GitHub CLI (`gh`) for repository operations (optional)

## Installation

1. Clone this repository into your project or use it as a template
2. The `.opencode/agent/` directory contains the agent definitions
3. Invoke `@context-harness` to start working

## How It Differs from Other Approaches

| Approach | Limitation | ContextHarness Solution |
|----------|------------|-------------------------|
| Single long conversation | Context window overflow | Incremental compaction to SESSION.md |
| Starting fresh each time | Lose all context | Named sessions persist across conversations |
| Manual note-taking | Easy to forget, inconsistent | Structured SESSION.md with guided compaction |
| Multiple agents executing | Conflicts, confusion | Single executor with advisory subagents |

## Contributing

Contributions welcome! Key areas:

- Additional subagent types
- SESSION.md section improvements
- Compaction strategy refinements
- Documentation

## License

MIT

---

**ContextHarness** - Harness your context, maintain your flow.
