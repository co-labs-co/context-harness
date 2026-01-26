# Installation

## Requirements

**Required:**

- [uv](https://docs.astral.sh/uv/) — Python package installer

**At least one of:**

- [OpenCode](https://opencode.ai) — Open-source AI coding assistant
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — Anthropic's VS Code extension or CLI

**Recommended:**

- [Git](https://git-scm.com/) — Version control (required for `/baseline --path` to properly locate repository root)

**Optional:**

- [GitHub CLI](https://cli.github.com/) `gh` — For `/issue`, `/pr`, `/ctx` branch creation
- [Context7 MCP](https://context7.com/) — For research features via `@research-subagent`

## Install with uv

The recommended way to install ContextHarness:

```bash
# Install globally
uv tool install "git+https://github.com/co-labs-co/context-harness.git"
```

Or run without installing:

```bash
uvx --from "git+https://github.com/co-labs-co/context-harness.git" ch init
```

## Initialize in Your Project

Navigate to your project directory and run:

```bash
ch init
```

### Tool Selection

By default, ContextHarness installs support for **both** OpenCode and Claude Code. You can choose a specific tool:

=== "Both Tools (Default)"

    ```bash
    ch init
    # or explicitly:
    ch init --tool both
    ```
    
    Creates configurations for both tools:
    
    - `.opencode/` — OpenCode agents and commands
    - `.claude/` — Claude Code agents and commands
    - `opencode.json` — OpenCode configuration
    - `.mcp.json` — Claude Code MCP configuration
    - `AGENTS.md` — OpenCode memory file
    - `CLAUDE.md` — Claude Code memory file

=== "OpenCode Only"

    ```bash
    ch init --tool opencode
    ```
    
    Creates:
    
    - `.opencode/agent/` — Agent definitions
    - `.opencode/command/` — Slash commands
    - `.opencode/skill/` — Installed skills
    - `opencode.json` — Configuration file
    - `AGENTS.md` — Memory file

=== "Claude Code Only"

    ```bash
    ch init --tool claude-code
    ```
    
    Creates:
    
    - `.claude/agents/` — Agent definitions
    - `.claude/commands/` — Slash commands
    - `.claude/skills/` — Installed skills
    - `.mcp.json` — MCP configuration
    - `CLAUDE.md` — Memory file

!!! note "Folder Naming Differences"
    OpenCode uses **singular** folder names (`agent/`, `command/`, `skill/`), while Claude Code uses **plural** names (`agents/`, `commands/`, `skills/`).

### Shared Session Storage

Regardless of which tool you use, sessions are stored in a shared location:

```
.context-harness/
├── sessions/                  # Named session directories
│   └── {session-name}/
│       └── SESSION.md
├── templates/
│   └── session-template.md
└── README.md
```

### Options

```bash
ch init --force          # Overwrite existing files (preserves sessions and skills)
ch init --target ./path  # Install in specific directory
ch init --tool opencode  # Install for OpenCode only
ch init --tool claude-code  # Install for Claude Code only
ch init --tool both      # Install for both tools (default)
```

## Verify Installation

```bash
# Check CLI is available
ch --version

# Verify GitHub CLI (optional)
gh auth status
```

> **Tip**: Both `ch` and `context-harness` commands work identically. Use `ch` for convenience.

## Next Steps

- [Quick Start](quickstart.md) — Start your first session
- [Context7 MCP Setup](../reference/architecture.md#context7-mcp-setup) — Enable research features
