# CLI Reference

Complete reference for the `context-harness` command-line interface.

## Installation

```bash
# Install globally (recommended)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Or run without installing
uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init
```

## Core Commands

### init

Initialize ContextHarness in a project.

```bash
context-harness init                    # Initialize in current project
context-harness init --force            # Overwrite existing files
context-harness init --target ./path    # Install in specific directory
```

**What it creates:**

- `.context-harness/` — Session storage and templates
- `.opencode/agent/` — Agent definitions
- `.opencode/command/` — Slash commands

## MCP Configuration

### mcp add

Add an MCP server to `opencode.json`.

```bash
context-harness mcp add context7        # Add Context7 for docs lookup
context-harness mcp add context7 -k KEY # With API key for higher limits
```

### mcp list

List configured MCP servers.

```bash
context-harness mcp list
```

## Skill Management

### skill list

List available skills from the registry.

```bash
context-harness skill list              # List all skills
context-harness skill list --tags react # Filter by tag
```

### skill list-local

List skills installed in the current project.

```bash
context-harness skill list-local
```

### skill info

Show details for a specific skill.

```bash
context-harness skill info <name>
```

### skill install

Install a skill from the registry.

```bash
context-harness skill install           # Interactive picker
context-harness skill install <name>    # Install specific skill
```

### skill extract

Export a local skill for sharing.

```bash
context-harness skill extract           # Interactive picker
context-harness skill extract <name>    # Extract specific skill
```

## Configuration Management

### config list

Show all configuration.

```bash
context-harness config list
```

### config get

Get a specific configuration value.

```bash
context-harness config get skills-repo
```

### config set

Set a configuration value.

```bash
# Project-level (in opencode.json)
context-harness config set skills-repo <repo>

# User-level (in ~/.context-harness/config.json)
context-harness config set skills-repo <repo> --user
```

### config unset

Remove a configuration value.

```bash
context-harness config unset skills-repo
```

## Shell Completion

### Bash

Add to `~/.bashrc`:

```bash
eval "$(_CONTEXT_HARNESS_COMPLETE=bash_source context-harness)"
```

### Zsh

Add to `~/.zshrc` (after `compinit`):

```zsh
autoload -Uz compinit && compinit
eval "$(_CONTEXT_HARNESS_COMPLETE=zsh_source context-harness)"
```

### Fish

Add to `~/.config/fish/completions/context-harness.fish`:

```fish
_CONTEXT_HARNESS_COMPLETE=fish_source context-harness | source
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
