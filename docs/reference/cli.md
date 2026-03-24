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
          "args": ["-y", "@upstash/context7-mcp"]
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

Install a skill from the registry. Installs to all detected tool directories by default.

```bash
ch skill install           # Interactive picker
ch skill install <name>    # Install specific skill
```

**Options:**

| Flag | Description |
|------|-------------|
| `--tool-target` | Target tool: `both` (default), `opencode`, or `claude-code` |
| `--registry` | Install from HTTP registry URL instead of configured registry |

**Examples:**

```bash
# Install to both tools (default)
ch skill install react-forms

# Install to OpenCode only
ch skill install react-forms --tool-target opencode

# Install from HTTP registry
ch skill install react-forms --registry http://localhost:8080
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

### skill init-repo

Initialize a new skills registry repository on GitHub with fully automated CI/CD for per-skill semantic versioning. Creates 16 files including GitHub Actions workflows for release-please, PR validation, and registry sync.

**Prerequisite:** GitHub CLI (`gh`) must be installed and authenticated (`gh auth login`).

```bash
ch skill init-repo my-skills                          # Create private repo
ch skill init-repo my-org/team-skills --public        # Create under an org, public
ch skill init-repo my-skills --configure-user         # Create and set as user default
ch skill init-repo my-skills --configure-project      # Create and set as project default
ch skill init-repo my-org/skills -d "Team AI skills"  # With custom description
```

**What it creates:**

```
my-skills/
├── .github/
│   ├── workflows/
│   │   ├── release.yml              # release-please per-skill versioning
│   │   ├── sync-registry.yml        # Rebuilds skills.json after releases
│   │   └── validate-skills.yml      # PR validation + sticky comments
│   ├── ISSUE_TEMPLATE/
│   │   └── new-skill.md
│   └── PULL_REQUEST_TEMPLATE.md
├── scripts/
│   ├── sync-registry.py             # Frontmatter + version.txt → skills.json
│   └── validate_skills.py           # Pydantic-based validation
├── skill/
│   └── example-skill/
│       ├── SKILL.md
│       └── version.txt              # Bootstrapped at 0.1.0
├── skills.json
├── release-please-config.json
├── .release-please-manifest.json
├── .gitignore
├── README.md
├── CONTRIBUTING.md
└── QUICKSTART.md
```

For details on the CI/CD automation and versioning lifecycle, see [Automated Versioning](../user-guide/skills.md#automated-versioning).

**Options:**

| Flag | Description |
|------|-------------|
| `--private` / `--public` | Repository visibility (default: `--private`) |
| `-d`, `--description` | Repository description |
| `--configure-user` | Set as default `skills-repo` in user config — applies to all projects (`~/.context-harness/config.json`) |
| `--configure-project` | Set as default `skills-repo` in project config — applies to this project only (`opencode.json`) |

!!! tip "User vs Project Configuration"
    `--configure-user` writes to `~/.context-harness/config.json`, so every project on your machine uses this registry by default. `--configure-project` writes to `opencode.json` in the current directory, so only this project is affected. If neither flag is passed, the command prints `config set` instructions for both options.

**Name format:**

| Format | Example | Result |
|--------|---------|--------|
| `repo` | `my-skills` | Created under your personal GitHub account |
| `owner/repo` | `my-org/team-skills` | Created under the specified organization |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success, or repository already exists |
| 1 | Error (auth failure, create failure) |

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

### skill upgrade-repo

Upgrade a registry repository's scaffold files to the latest version. Run this in the root of your skills registry to get new features and fixes.

```bash
ch skill upgrade-repo              # Interactive upgrade
ch skill upgrade-repo --check      # Only check for updates
ch skill upgrade-repo --dry-run    # Preview changes without writing
ch skill upgrade-repo --force      # Overwrite all scaffold files
```

**Options:**

| Flag | Description |
|------|-------------|
| `--check` | Only check what would be updated, don't make changes |
| `--dry-run` | Show what would be updated without writing files |
| `--force` | Overwrite existing scaffold files (including documentation) |

**What gets updated:**

| Category | Files | Behavior |
|----------|-------|----------|
| Critical infrastructure | Dockerfile, docker-compose.yml, nginx.conf, index.html, skill.html, llms.txt | Always updated |
| Workflows | release.yml, sync-registry.yml, validate-skills.yml, auto-rebase.yml | Only if missing |
| Documentation | README.md, CONTRIBUTING.md, QUICKSTART.md | Only if missing |

!!! warning "Preserves Skills"
    Files in `skill/` directory are never modified. Your skill content is safe.

### skill use-registry

Configure the CLI to use an HTTP registry instead of GitHub.

```bash
ch skill use-registry http://localhost:8080
ch skill use-registry https://skills.example.com
```

This updates the project's configuration to fetch skills from the HTTP endpoint.

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
| 2 | Invalid arguments |
