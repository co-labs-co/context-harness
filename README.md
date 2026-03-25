# ContextHarness

A CLI framework for AI-assisted development with context preservation.

ContextHarness helps you maintain session continuity with AI coding agents through user-driven compaction cycles, so your agent remembers what matters across long conversations.

## Install

```bash
# Using uv (recommended)
uv tool install context-harness

# Using pip
pip install context-harness

# Using pipx
pipx install context-harness
```

## Quick Start

```bash
# Initialize in your project
context-harness init

# Start a session
/ctx my-feature

# Work normally with your AI agent...

# Compact when context gets full
/compact
```

## What It Does

ContextHarness creates a structured workflow for AI-assisted development:

1. **Sessions** - Isolated work contexts for features, bugs, or experiments
2. **Compaction** - Preserve key context when conversations get long
3. **Skills** - Reusable prompts and workflows for common tasks
4. **Worktrees** - Git worktree management for parallel development

## CLI Commands

```
context-harness init          # Initialize framework in project
context-harness config        # Manage configuration
context-harness skill         # Install and manage skills
context-harness worktree      # Create isolated worktrees
context-harness mcp           # Configure MCP servers
```

### Init

```bash
# Initialize for both OpenCode and Claude Code
context-harness init

# Initialize for a specific tool
context-harness init --tool opencode
context-harness init --tool claude-code
```

### Skills

```bash
# List available skills
context-harness skill list

# Install a skill
context-harness skill install <skill-name>

# Set your skills registry
context-harness config set skills-repo owner/repo
```

### Worktrees

```bash
# Create an isolated worktree
context-harness worktree create feature-branch

# List worktrees
context-harness worktree list
```

### MCP Servers

```bash
# Add an MCP server
context-harness mcp add context7
context-harness mcp add atlassian

# Authenticate with OAuth
context-harness mcp auth atlassian

# List configured servers
context-harness mcp list
```

## Directory Structure

After running `context-harness init`, your project will have:

```
your-project/
├── .context-harness/     # Session data and project context
│   └── sessions/         # Session files (SESSION.md)
├── .opencode/            # OpenCode configuration
│   ├── agents/           # Custom agents
│   ├── commands/         # Slash commands
│   └── skills/           # Installed skills
├── .claude/              # Claude Code configuration
│   ├── agents/           # Custom agents
│   ├── commands/         # Slash commands
│   └── skills/           # Installed skills
└── opencode.json         # Project configuration
```

## Skills Registry

ContextHarness can install skills from any GitHub repository. The default registry is `co-labs-co/context-harness-skills` (the official skills registry: https://github.com/co-labs-co/context-harness-skills).

To use a different registry:

```bash
# Project-level
context-harness config set skills-repo your-org/your-skills

# User-level (applies to all projects)
context-harness config set skills-repo your-org/your-skills --user
```

## Documentation

- [Getting Started](docs/getting-started/) - Step-by-step guides
- [User Guide](docs/user-guide/) - Detailed usage documentation
- [Reference](docs/reference/) - API and command reference
- [Architecture](ARCHITECTURE.md) - System design

## Development

```bash
# Clone the repo
git clone https://github.com/co-labs-co/context-harness.git
cd context-harness

# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Build docs
uv run mkdocs serve
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

AGPL-3.0-or-later
