# Architecture

ContextHarness uses a single-executor model with advisory subagents. It supports both OpenCode and Claude Code with tool-specific configurations.

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    CONTEXT-HARNESS AGENT                     │
│                                                              │
│  • Executes ALL work (code, files, commands)                 │
│  • Manages named sessions                                    │
│  • Reads/writes SESSION.md                                   │
│  • Invokes subagents for guidance only                       │
└───────────────┬────────────────────────────────┬─────────────┘
                │                                │
                │                                │
                ▼                                ▼
┌───────────────────────────────┐  ┌───────────────────────────┐
│  Research & Docs Subagents    │  │   Compaction Guide        │
│                               │  │   Subagent                │
│  @research-subagent           │  │                           │
│  @docs-subagent               │  │  • Analyze session        │
│                               │  │  • Recommend what to      │
│  • Context7 MCP access        │  │    preserve               │
│  • Web search verification    │  │  • NO execution           │
│  • Provide guidance           │  │                           │
│  • Return recommendations     │  │                           │
│  • NO execution               │  │                           │
└───────────────────────────────┘  └───────────────────────────┘
```

## Key Principles

1. **Single Executor**: Only the primary agent writes code, modifies files, and runs commands
2. **Advisory Subagents**: Subagents provide guidance but never execute
3. **Persistent Context**: SESSION.md maintains state across conversations
4. **Compaction**: Use `/compact` to preserve context before it's lost to context window limits
5. **Dual-Tool Support**: Works with both OpenCode and Claude Code simultaneously

## Directory Structure

After installation, your project will have tool-specific directories:

=== "Both Tools"

    ```
    your-project/
    ├── .context-harness/              # Shared session storage
    │   ├── sessions/
    │   │   └── {session-name}/
    │   │       └── SESSION.md
    │   ├── templates/
    │   │   └── session-template.md
    │   └── README.md
    ├── .opencode/                     # OpenCode configuration
    │   ├── agent/
    │   │   ├── context-harness.md
    │   │   ├── compaction-guide.md
    │   │   ├── contexts-subagent.md
    │   │   ├── docs-subagent.md
    │   │   └── research-subagent.md
    │   ├── command/
    │   │   ├── ctx.md
    │   │   ├── compact.md
    │   │   ├── contexts.md
    │   │   ├── issue.md
    │   │   └── pr.md
    │   └── skill/
    ├── .claude/                       # Claude Code configuration
    │   ├── agents/
    │   │   ├── context-harness.md
    │   │   ├── compaction-guide.md
    │   │   ├── contexts-subagent.md
    │   │   ├── docs-subagent.md
    │   │   └── research-subagent.md
    │   ├── commands/
    │   │   ├── ctx.md
    │   │   ├── compact.md
    │   │   ├── contexts.md
    │   │   ├── issue.md
    │   │   └── pr.md
    │   └── skills/
    ├── opencode.json                  # OpenCode config + MCP
    ├── .mcp.json                      # Claude Code MCP config
    ├── AGENTS.md                      # OpenCode memory file
    └── CLAUDE.md                      # Claude Code memory file
    ```

=== "OpenCode Only"

    ```
    your-project/
    ├── .context-harness/
    │   ├── sessions/
    │   │   └── {session-name}/
    │   │       └── SESSION.md
    │   ├── templates/
    │   │   └── session-template.md
    │   └── README.md
    ├── .opencode/
    │   ├── agent/
    │   │   ├── context-harness.md
    │   │   ├── compaction-guide.md
    │   │   ├── contexts-subagent.md
    │   │   ├── docs-subagent.md
    │   │   └── research-subagent.md
    │   ├── command/
    │   │   ├── ctx.md
    │   │   ├── compact.md
    │   │   ├── contexts.md
    │   │   ├── issue.md
    │   │   └── pr.md
    │   └── skill/
    ├── opencode.json
    └── AGENTS.md
    ```

=== "Claude Code Only"

    ```
    your-project/
    ├── .context-harness/
    │   ├── sessions/
    │   │   └── {session-name}/
    │   │       └── SESSION.md
    │   ├── templates/
    │   │   └── session-template.md
    │   └── README.md
    ├── .claude/
    │   ├── agents/
    │   │   ├── context-harness.md
    │   │   ├── compaction-guide.md
    │   │   ├── contexts-subagent.md
    │   │   ├── docs-subagent.md
    │   │   └── research-subagent.md
    │   ├── commands/
    │   │   ├── ctx.md
    │   │   ├── compact.md
    │   │   ├── contexts.md
    │   │   ├── issue.md
    │   │   └── pr.md
    │   └── skills/
    ├── .mcp.json
    └── CLAUDE.md
    ```

!!! note "Key Differences"
    | Aspect | OpenCode | Claude Code |
    |--------|----------|-------------|
    | Config folder | `.opencode/` | `.claude/` |
    | Folder naming | singular (`agent/`, `command/`, `skill/`) | plural (`agents/`, `commands/`, `skills/`) |
    | Memory file | `AGENTS.md` | `CLAUDE.md` |
    | MCP config | `opencode.json` | `.mcp.json` |

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

ContextHarness agents are **model-agnostic**. They do not specify a model, allowing you to use any provider and model supported by your tool.

### Default Model

=== "OpenCode"

    Set your default model in `opencode.json`:
    
    ```json
    {
      "$schema": "https://opencode.ai/config.json",
      "model": "anthropic/claude-sonnet-4-20250514"
    }
    ```

=== "Claude Code"

    Claude Code uses your Anthropic API configuration or Claude Pro subscription. Model selection is handled through Claude Code's settings.

### Per-Agent Configuration

=== "OpenCode"

    For different models per agent in `opencode.json`:
    
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

=== "Claude Code"

    Claude Code does not support per-agent model configuration. All agents use the same model.

### Model Loading Priority (OpenCode)

1. **Command-line flag** (`--model` or `-m`) - Highest priority
2. **Agent-specific config** (`agent.{name}.model` in JSON)
3. **Default model** (`model` key in `opencode.json`)
4. **Last used model** (from previous session)
5. **Internal priority** (first available model)

## MCP Server Setup

ContextHarness supports multiple MCP servers that extend agent capabilities. The research and documentation subagents use these servers for documentation lookup, web search, and security scanning.

For detailed configuration of all supported servers, see the [MCP Servers Reference](mcp-servers.md).

### Quick Setup

```bash
ch mcp add context7          # Documentation lookup (used by @research-subagent)
ch mcp add exa               # AI-powered web search
ch mcp add snyk              # Security scanning (code, dependencies, IaC)
ch mcp add atlassian         # Jira/Confluence integration (requires OAuth)
```

### Context7 (Recommended)

The research and documentation subagents require [Context7 MCP](https://github.com/upstash/context7) for accurate documentation lookup.

=== "OpenCode"

    Add to `opencode.json`:
    
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

=== "Claude Code"

    Add to `.mcp.json`:
    
    ```json
    {
      "mcpServers": {
        "context7": {
          "command": "npx",
          "args": ["-y", "@upstash/context7-mcp"]
        }
      }
    }
    ```

For API key setup and higher rate limits, see [Context7 details](mcp-servers.md#context7).

### Snyk (Security Scanning)

[Snyk MCP](https://docs.snyk.io/integrations/snyk-studio-agentic-integrations/getting-started-with-snyk-studio) provides security scanning for code, open-source dependencies, containers, and IaC. It runs as a local MCP server via `npx`.

=== "OpenCode"

    ```json
    {
      "mcp": {
        "snyk": {
          "type": "local",
          "command": "npx",
          "args": ["-y", "snyk@latest", "mcp", "-t", "stdio"]
        }
      }
    }
    ```

=== "Claude Code"

    ```json
    {
      "mcpServers": {
        "snyk": {
          "command": "npx",
          "args": ["-y", "snyk@latest", "mcp", "-t", "stdio"]
        }
      }
    }
    ```

!!! note "Snyk Authentication"
    Snyk requires separate authentication. Run `npx snyk auth` to authenticate before using the MCP server. See [Snyk details](mcp-servers.md#snyk) for tool profiles and available scanning tools.

## Customization

All agent behaviors are defined in markdown files:

| Agent | Purpose |
|-------|---------|
| Primary Agent (`context-harness.md`) | Main executor, session management |
| Contexts Subagent (`contexts-subagent.md`) | Session discovery and listing |
| Research Subagent (`research-subagent.md`) | API lookups, best practices |
| Docs Subagent (`docs-subagent.md`) | Documentation summaries |
| Compaction Guide (`compaction-guide.md`) | Context preservation |

## Code Architecture

### Three-Layer Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                      Interfaces Layer                       │
│                                                             │
│  CLI commands (Click)          SDK clients (future)         │
│  skill_cmd.py, config_cmd.py  Handle user I/O only         │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Services Layer                         │
│                                                             │
│  skill_service.py              config_service.py            │
│  Business logic, orchestration                              │
│  Returns Result[T] = Success[T] | Failure                   │
│  Uses Protocol-based dependency injection                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ operates on
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Primitives Layer                         │
│                                                             │
│  Pure dataclasses: Skill, VersionComparison, RegistryRepo   │
│  Enums: SkillSource, VersionStatus, RepoVisibility          │
│  Result types: Success[T], Failure, ErrorCode               │
│  No business logic — just data                              │
└─────────────────────────────────────────────────────────────┘
```

### Skills Registry Architecture

The skills system uses a distributed registry model where repositories host skills and a CLI fetches them:

```
┌──────────────────────┐     ┌──────────────────────────────────────┐
│   CLI (ch skill ...)  │────▶│  GitHub Repository (skills registry) │
│                      │     │                                      │
│  • skill list        │     │  skills.json ◀── sync-registry.yml   │
│  • skill install     │     │  skill/*/SKILL.md                    │
│  • skill outdated    │     │  skill/*/version.txt ◀── release.yml │
│  • skill upgrade     │     │                                      │
└──────────────────────┘     └──────────────────────────────────────┘
```

Repositories scaffolded by `ch skill init-repo` include CI/CD automation:

- **release-please** manages per-skill `version.txt` and `CHANGELOG.md` via conventional commits
- **sync-registry** rebuilds `skills.json` from frontmatter + `version.txt` after each release
- **validate-skills** checks PR changes for schema compliance

See [Skills Guide](../user-guide/skills.md#automated-versioning) for the full versioning lifecycle.

### Agentic Workflows

ContextHarness uses [GitHub Agentic Workflows](https://github.github.com/gh-aw/) for continuous documentation. An AI agent runs on every PR to keep docs in sync with code changes.

```
┌───────────────┐     ┌───────────────────────────────────────────────┐
│  PR opened /  │────▶│  update-docs.md  (Agentic Workflow)          │
│  synchronized │     │                                               │
└───────────────┘     │  1. Analyze code diff                         │
                      │  2. Check docs for gaps                       │
                      │  3. Update affected pages                     │
                      │  4. Commit changes back to PR                 │
                      └───────────────────────────────────────────────┘
```

The workflow file lives at `.github/workflows/update-docs.md` with a compiled `.github/workflows/update-docs.lock.yml`. See the [Agentic Workflows guide](../user-guide/agentic-workflows.md) for setup and customization.

**Agent file locations:**

=== "OpenCode"

    ```
    .opencode/agent/
    ├── context-harness.md
    ├── compaction-guide.md
    ├── contexts-subagent.md
    ├── docs-subagent.md
    └── research-subagent.md
    ```

=== "Claude Code"

    ```
    .claude/agents/
    ├── context-harness.md
    ├── compaction-guide.md
    ├── contexts-subagent.md
    ├── docs-subagent.md
    └── research-subagent.md
    ```

**Command file locations:**

=== "OpenCode"

    ```
    .opencode/command/
    ├── ctx.md          # Session switching with branch creation
    ├── compact.md      # Manual compaction
    ├── contexts.md     # List sessions
    ├── issue.md        # GitHub issue management
    └── pr.md           # Pull request creation
    ```

=== "Claude Code"

    ```
    .claude/commands/
    ├── ctx.md          # Session switching with branch creation
    ├── compact.md      # Manual compaction
    ├── contexts.md     # List sessions
    ├── issue.md        # GitHub issue management
    └── pr.md           # Pull request creation
    ```
