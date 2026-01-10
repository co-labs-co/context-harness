# Architecture

ContextHarness uses a single-executor model with advisory subagents.

## System Overview

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

## Key Principles

1. **Single Executor**: Only the primary agent writes code, modifies files, and runs commands
2. **Advisory Subagents**: Subagents provide guidance but never execute
3. **Persistent Context**: SESSION.md maintains state across conversations
4. **Incremental Compaction**: Context is saved every 2nd user interaction

## Directory Structure

After installation:

```
your-project/
├── .context-harness/
│   ├── sessions/                  # Named session directories
│   │   └── {session-name}/
│   │       └── SESSION.md
│   ├── templates/
│   │   └── session-template.md    # Template for new sessions
│   └── README.md                  # Framework documentation
└── .opencode/
    ├── agent/
    │   ├── context-harness.md     # Primary executor agent
    │   ├── compaction-guide.md    # Compaction advisory subagent
    │   ├── contexts-subagent.md   # Session listing subagent
    │   ├── docs-subagent.md       # Documentation advisory subagent
    │   └── research-subagent.md   # Research advisory subagent
    └── command/
        ├── ctx.md                 # /ctx command
        ├── compact.md             # /compact command
        ├── contexts.md            # /contexts command
        ├── issue.md               # /issue command
        └── pr.md                  # /pr command
```

## Subagents

### @contexts-subagent

Handles session discovery and listing. When you run `/contexts`, this subagent scans all sessions, extracts metadata, and returns a formatted summary. **Read-only—does not execute.**

### @research-subagent

Provides grounded research guidance using Context7 MCP and web search for accurate, up-to-date API documentation, best practices, and implementation approaches. **Advisory only—does not execute.**

- **Context7 MCP Integration**: Access to up-to-date documentation for popular libraries
- **Web Search Verification**: Real-time information lookup
- **Grounded Responses**: All research is cross-referenced and sourced
- **Version Awareness**: Tracks library versions and compatibility

### @docs-subagent

Provides documentation summaries, framework guides, and API references. **Advisory only—does not execute.**

### @compaction-guide

Analyzes current work and recommends what to preserve during compaction. **Advisory only—does not execute.**

## Model Configuration

ContextHarness agents are **model-agnostic**. They do not specify a model, allowing you to use any provider and model supported by OpenCode.

### Default Model

Set your default model in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-20250514"
}
```

### Per-Agent Configuration

For different models per agent:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-20250514",
  "agent": {
    "context-harness": {
      "model": "anthropic/claude-opus-4-20250514"
    },
    "compaction-guide": {
      "model": "anthropic/claude-haiku-4-20250514"
    }
  }
}
```

### Model Loading Priority

1. **Command-line flag** (`--model` or `-m`) - Highest priority
2. **Agent-specific config** (`agent.{name}.model` in JSON)
3. **Default model** (`model` key in `opencode.json`)
4. **Last used model** (from previous session)
5. **Internal priority** (first available model)

## Context7 MCP Setup

The research and documentation subagents require [Context7 MCP](https://github.com/upstash/context7) for accurate documentation lookup.

### Basic Setup

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

### With API Key

For higher rate limits:

```json
{
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

Sign up for a free API key at [context7.com](https://context7.com).

## Customization

All agent behaviors are defined in markdown files:

| Agent | Source File | Purpose |
|-------|-------------|---------|
| Primary Agent | `context-harness.md` | Main executor, session management |
| Contexts Subagent | `contexts-subagent.md` | Session discovery and listing |
| Research Subagent | `research-subagent.md` | API lookups, best practices |
| Docs Subagent | `docs-subagent.md` | Documentation summaries |
| Compaction Guide | `compaction-guide.md` | Context preservation |

**Command files** (`.opencode/command/`):

- `ctx.md` — Session switching with branch creation
- `compact.md` — Manual compaction
- `contexts.md` — List sessions
- `issue.md` — GitHub issue management
- `pr.md` — Pull request creation
