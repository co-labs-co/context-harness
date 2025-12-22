# ContextHarness Documentation

Advanced documentation for ContextHarness. For quick start, see [README.md](README.md).

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
        ├── ctx.md                 # /ctx command - switch/create sessions + branch
        ├── compact.md             # /compact command - save context
        ├── contexts.md            # /contexts command - list sessions
        ├── issue.md               # /issue command - GitHub issue management
        └── pr.md                  # /pr command - pull request creation
```

## SESSION.md Sections

| Section | Purpose |
|---------|---------|
| **Active Work** | Current task, status, blockers |
| **Key Files** | Files being modified with purposes |
| **Decisions Made** | Important decisions with rationale |
| **Documentation References** | Relevant docs with links |
| **Next Steps** | Prioritized action items |
| **Completed This Session** | Archived completed work |

## Subagents

### @contexts-subagent
Handles session discovery and listing. When you run `/contexts`, this subagent scans all sessions, extracts metadata, and returns a formatted summary. **Read-only—does not execute.**

### @research-subagent
Provides grounded research guidance using Context7 MCP and web search for accurate, up-to-date API documentation, best practices, and implementation approaches. **Advisory only—does not execute.**

- **Context7 MCP Integration**: Access to up-to-date documentation for popular libraries and frameworks
- **Web Search Verification**: Real-time information lookup and fact verification
- **Grounded Responses**: All research is cross-referenced and sourced
- **Version Awareness**: Tracks library versions and compatibility

### @docs-subagent
Provides documentation summaries, framework guides, and API references. **Advisory only—does not execute.**

### @compaction-guide
Analyzes current work and recommends what to preserve during compaction. **Advisory only—does not execute.**

## GitHub Integration

ContextHarness integrates with GitHub for a seamless development workflow:

1. **Automatic branch creation**: `/ctx login-feature` creates a `feature/login-feature` branch
2. **Issue tracking**: `/issue` creates a GitHub issue with gathered context
3. **Issue updates**: `/issue update` adds progress comments to the linked issue
4. **PR creation**: `/pr` creates a pull request linked to the issue

**Requirements**: GitHub CLI (`gh`) installed and authenticated

**Graceful degradation**: If `gh` is not available, GitHub features are skipped and sessions work locally only.

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

All agents will inherit this model unless overridden.

### Per-Agent Model Configuration

For advanced users who want different models for different agents (e.g., a more capable model for the primary agent, a lighter model for simple subagents):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-20250514",
  "agent": {
    "context-harness": {
      "model": "anthropic/claude-opus-4"
    },
    "research-subagent": {
      "model": "anthropic/claude-opus-4"
    },
    "compaction-guide": {
      "model": "anthropic/claude-haiku-4-20250514"
    }
  }
}
```

### Model Loading Priority

OpenCode determines which model to use in this order:

1. **Command-line flag** (`--model` or `-m`) - Highest priority
2. **Agent-specific config** (`agent.{name}.model` in JSON)
3. **Default model** (`model` key in `opencode.json`)
4. **Last used model** (from previous session)
5. **Internal priority** (first available model)

### Recommended Models

For optimal ContextHarness performance, we recommend models with strong reasoning capabilities:

- **Primary agent**: Claude Opus, Claude Sonnet, GPT-4o, or similar high-capability models
- **Subagents**: Claude Sonnet, Claude Haiku, or similar for routine advisory tasks

## Context7 MCP Setup

The research and documentation subagents require [Context7 MCP](https://github.com/upstash/context7) for accurate, up-to-date library documentation. Add to your `opencode.json`:

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

## Customization

All agent behaviors are defined in markdown files. Customize them to fit your workflow:

| Agent | Source File | Purpose |
|-------|-------------|---------|
| Primary Agent | [`context-harness.md`](src/context_harness/templates/.opencode/agent/context-harness.md) | Main executor, session management, compaction triggers |
| Contexts Subagent | [`contexts-subagent.md`](src/context_harness/templates/.opencode/agent/contexts-subagent.md) | Session discovery and listing |
| Research Subagent | [`research-subagent.md`](src/context_harness/templates/.opencode/agent/research-subagent.md) | API lookups, best practices, grounded research |
| Docs Subagent | [`docs-subagent.md`](src/context_harness/templates/.opencode/agent/docs-subagent.md) | Documentation summaries, framework guides |
| Compaction Guide | [`compaction-guide.md`](src/context_harness/templates/.opencode/agent/compaction-guide.md) | Context preservation recommendations |

**Other customizable files:**
- [`session-template.md`](src/context_harness/templates/.context-harness/templates/session-template.md) - Template for new SESSION.md files
- [`.context-harness/README.md`](src/context_harness/templates/.context-harness/README.md) - Framework documentation installed with each project

**Command files** (`.opencode/command/`):
- [`ctx.md`](src/context_harness/templates/.opencode/command/ctx.md) - Session switching command with GitHub branch creation
- [`compact.md`](src/context_harness/templates/.opencode/command/compact.md) - Manual compaction command
- [`contexts.md`](src/context_harness/templates/.opencode/command/contexts.md) - List sessions command
- [`issue.md`](src/context_harness/templates/.opencode/command/issue.md) - GitHub issue management command
- [`pr.md`](src/context_harness/templates/.opencode/command/pr.md) - Pull request creation command

## Manual Installation

Alternatively to the CLI:
1. Clone this repository
2. Copy the template directories from `src/context_harness/templates/` to your project:
   - `.context-harness/` - Framework configuration and session templates
   - `.opencode/agent/` - Agent definitions
   - `.opencode/command/` - Slash commands
3. Add Context7 MCP to your `opencode.json` (see above)
4. Invoke `@context-harness` to start working

## How It Differs from Other Approaches

| Approach | Limitation | ContextHarness Solution |
|----------|------------|-------------------------|
| Single long conversation | Context window overflow | Incremental compaction to SESSION.md |
| Starting fresh each time | Lose all context | Named sessions persist across conversations |
| Manual note-taking | Easy to forget, inconsistent | Structured SESSION.md with guided compaction |
| Multiple agents executing | Conflicts, confusion | Single executor with advisory subagents |
