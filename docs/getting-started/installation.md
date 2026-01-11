# Installation

## Requirements

**Required:**

- [OpenCode.ai](https://opencode.ai) — AI coding assistant (ContextHarness is a framework for this)
- [uv](https://docs.astral.sh/uv/) — Python package installer

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

This creates:

- `.context-harness/` — Session storage and templates
- `.opencode/agent/` — Agent definitions
- `.opencode/command/` — Slash commands

### Options

```bash
ch init --force          # Overwrite existing files
ch init --target ./path  # Install in specific directory
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
