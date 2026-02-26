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
ch init                       # Initialize for both tools (default)
ch init --force               # Overwrite existing files (preserves sessions/skills)
ch init --target ./path       # Install in specific directory
ch init --tool opencode       # Install for OpenCode only
ch init --tool claude-code    # Install for Claude Code only
ch init --tool both           # Install for both tools (explicit)
```

**What it creates:**

=== "Both Tools (Default)"

    ```
    your-project/
    ├── .contextignore            # Ignore patterns for context scanning
    ├── .context-harness/         # Session storage (shared)
    ├── .opencode/                # OpenCode configuration
    │   ├── agent/
    │   ├── command/
    │   └── skill/
    ├── .claude/                  # Claude Code configuration
    │   ├── agents/
    │   ├── commands/
    │   └── skills/
    ├── opencode.json             # OpenCode config + MCP
    ├── .mcp.json                 # Claude Code MCP config
    ├── AGENTS.md                 # OpenCode memory file
    └── CLAUDE.md                 # Claude Code memory file
    ```

=== "OpenCode Only"

    ```
    your-project/
    ├── .contextignore            # Ignore patterns for context scanning
    ├── .context-harness/         # Session storage
    ├── .opencode/
    │   ├── agent/
    │   ├── command/
    │   └── skill/
    ├── opencode.json
    └── AGENTS.md
    ```

=== "Claude Code Only"

    ```
    your-project/
    ├── .contextignore            # Ignore patterns for context scanning
    ├── .context-harness/         # Session storage
    ├── .claude/
    │   ├── agents/
    │   ├── commands/
    │   └── skills/
    ├── .mcp.json
    └── CLAUDE.md
    ```

For more on ignore patterns, see the [Ignore Patterns Guide](../user-guide/ignore-patterns.md).

## MCP Configuration

### mcp add

Add an MCP server. Writes to both `opencode.json` and `.mcp.json` when both tools are installed.

```bash
ch mcp add context7        # Add Context7 for docs lookup
ch mcp add context7 -k KEY # With API key for higher limits
```

**Configuration format by tool:**

=== "OpenCode (opencode.json)"

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

=== "Claude Code (.mcp.json)"

    ```json
    {
      "mcpServers": {
        "context7": {
          "command": "npx",
          "args": ["-y", "@anthropic-ai/mcp-server-context7"]
        }
      }
    }
    ```

### mcp list

List configured MCP servers from all detected configuration files.

```bash
ch mcp list
```

**Example output:**

```
📦 MCP Servers

From opencode.json:
  • context7 (remote)

From .mcp.json:
  • context7 (command: npx)
```

## Skill Management

### skill list

List available skills from the registry.

```bash
ch skill list              # List all skills
ch skill list --tags react # Filter by tag
```

### skill list-local

List skills installed in the current project. Searches both `.opencode/skill/` and `.claude/skills/` directories.

```bash
ch skill list-local
```

### skill info

Show details for a specific skill.

```bash
ch skill info <name>
```

### skill install

Install a skill from the registry. Installs to all detected tool directories.

```bash
ch skill install           # Interactive picker
ch skill install <name>    # Install specific skill
```

**Installation paths:**

=== "Both Tools"

    Skills are installed to both directories:
    
    - `.opencode/skill/<name>/SKILL.md`
    - `.claude/skills/<name>/SKILL.md`

=== "OpenCode Only"

    - `.opencode/skill/<name>/SKILL.md`

=== "Claude Code Only"

    - `.claude/skills/<name>/SKILL.md`

### skill extract

Export a local skill for sharing. Searches both tool directories.

```bash
ch skill extract           # Interactive picker
ch skill extract <name>    # Extract specific skill
```

### skill outdated

Check which installed skills have newer versions available in the registry.

```bash
ch skill outdated
```

**Example output:**

```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Skill           ┃ Installed     ┃ Latest        ┃ Status              ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ react-forms     │ 0.1.0         │ 0.2.0         │ upgrade available   │
│ fastapi-crud    │ 1.0.0         │ 1.0.0         │ up to date          │
│ django-auth     │ 0.3.0         │ 0.3.1         │ upgrade available   │
└─────────────────┴───────────────┴───────────────┴─────────────────────┘
```

If a skill requires a newer version of ContextHarness than is currently installed, it is shown with status `incompatible`.

### skill upgrade

Upgrade one or all installed skills to the latest registry version.

```bash
ch skill upgrade <name>        # Upgrade a specific skill
ch skill upgrade --all         # Upgrade all outdated skills
ch skill upgrade <name> --force  # Upgrade even if version is incompatible
```

**Options:**

| Flag | Description |
|------|-------------|
| `--all` | Upgrade every installed skill that has a newer version |
| `--force` | Skip the `min_context_harness_version` compatibility check |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success (or already up to date) |
| 1 | Error (skill not found, network failure, incompatible version) |

!!! tip "Incompatible Skills"
    If a skill requires a newer version of ContextHarness, the upgrade is blocked and a message is shown. Run `pipx upgrade context-harness` (or `uv tool upgrade context-harness`) first, or use `--force` to override.

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

=== "OpenCode"

    ```bash
    # Project-level (in opencode.json)
    ch config set skills-repo <repo>
    
    # User-level (in ~/.context-harness/config.json)
    ch config set skills-repo <repo> --user
    ```

=== "Claude Code"

    ```bash
    # Project-level (in .claude/settings.json)
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
| 2 | Invalid arguments or incompatible version |
