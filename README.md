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

### Install

Requires [uv](https://docs.astral.sh/uv/). Run this in your project directory:

```bash
uvx --from "git+https://github.com/cmtzco/context-harness.git#subdirectory=scripts/context-harness-cli" context-harness init
```

This creates the `.context-harness/` and `.opencode/agent/` directories with all framework files.

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
    @research-subagent                  @compaction-guide
    @docs-subagent                             │
             │                                  │
             ▼                                  ▼
┌──────────────────────────┐      ┌─────────────────────────┐
│ Grounded Research        │      │ Compaction Guide        │
│ & Docs Subagents         │      │ Subagent                │
│                          │      │                         │
│ - Context7 MCP access    │      │ - Analyze session       │
│ - Web search verification│      │ - Recommend what to     │
│ - Provide guidance       │      │   preserve              │
│ - Return recommendations │      │ - NO execution          │
│ - NO execution           │      │                         │
└──────────────────────────┘      └─────────────────────────┘
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
Provides grounded research guidance using Context7 MCP and web search for accurate, up-to-date API documentation, best practices, and implementation approaches. **Advisory only—does not execute.**

**Enhanced Capabilities**:
- **Context7 MCP Integration**: Access to up-to-date documentation for popular libraries and frameworks
- **Web Search Verification**: Real-time information lookup and fact verification
- **Grounded Responses**: All research is cross-referenced and sourced
- **Version Awareness**: Tracks library versions and compatibility

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
- **Context7 MCP** (required for grounded research capabilities)

### Context7 MCP Setup

The research and documentation subagents require [Context7 MCP](https://github.com/upstash/context7) for accurate, up-to-date library documentation. Add the following to your `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

**With API key** (optional, for higher rate limits):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      },
      "enabled": true
    }
  }
}
```

Sign up for a free Context7 API key at [context7.com](https://context7.com) for increased rate limits.

## Installation

The easiest way to install ContextHarness is with the CLI:

```bash
uvx --from "git+https://github.com/cmtzco/context-harness.git#subdirectory=scripts/context-harness-cli" context-harness init
```

This will create all necessary directories and files in your project.

### Manual Installation

Alternatively, you can:
1. Clone this repository
2. Copy `.context-harness/` and `.opencode/agent/` to your project
3. Add Context7 MCP to your `opencode.json` (see above)
4. Invoke `@context-harness` to start working

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
