# CLI Reference

Complete reference for the ContextHarness command-line interface.

> **Note**: Both `ch` and `context-harness` commands work identically. Use `ch` for convenience.

## Installation

```bash
# Install globally (recommended)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Or run without installing
uvx --from "git+https://github.com/co-labs-co/context-harness.git" ch init
```

## Core Commands

### init

Initialize ContextHarness in a project.

```bash
ch init                    # Initialize in current project
ch init --force            # Overwrite existing files
ch init --target ./path    # Install in specific directory
```

**What it creates:**

- `.context-harness/` — Session storage and templates
- `.opencode/agent/` — Agent definitions
- `.opencode/command/` — Slash commands

## MCP Configuration

### mcp add

Add an MCP server to `opencode.json`.

```bash
ch mcp add context7        # Add Context7 for docs lookup
ch mcp add context7 -k KEY # With API key for higher limits
```

### mcp list

List configured MCP servers.

```bash
ch mcp list
```

## Skill Management

### skill list

List available skills from the registry.

```bash
ch skill list              # List all skills
ch skill list --tags react # Filter by tag
```

### skill list-local

List skills installed in the current project.

```bash
ch skill list-local
```

### skill info

Show details for a specific skill.

```bash
ch skill info <name>
```

### skill install

Install a skill from the registry.

```bash
ch skill install           # Interactive picker
ch skill install <name>    # Install specific skill
```

### skill extract

Export a local skill for sharing.

```bash
ch skill extract           # Interactive picker
ch skill extract <name>    # Extract specific skill
```

## Configuration Management

### config list

Show all configuration.

```bash
ch config list
```

### config get

Get a specific configuration value.

```bash
ch config get skills-repo
```

### config set

Set a configuration value.

```bash
# Project-level (in opencode.json)
ch config set skills-repo <repo>

# User-level (in ~/.context-harness/config.json)
ch config set skills-repo <repo> --user
```

### config unset

Remove a configuration value.

```bash
ch config unset skills-repo
```

## Shell Completion

### Bash

Add to `~/.bashrc`:

```bash
eval "$(_CH_COMPLETE=bash_source ch)"
```

### Zsh

Add to `~/.zshrc` (after `compinit`):

```zsh
autoload -Uz compinit && compinit
eval "$(_CH_COMPLETE=zsh_source ch)"
```

### Fish

Add to `~/.config/fish/completions/ch.fish`:

```fish
_CH_COMPLETE=fish_source ch | source
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
