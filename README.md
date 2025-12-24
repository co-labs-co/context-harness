# ContextHarness

> Context-aware agent framework for [OpenCode.ai](https://opencode.ai) that maintains session continuity.

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
# Run directly (recommended)
uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init

# Or install globally
uv tool install "git+https://github.com/co-labs-co/context-harness.git"
context-harness init
```

## CLI Commands

```bash
# Initialize ContextHarness in your project
context-harness init

# Add Context7 MCP for documentation lookup
context-harness mcp add context7

# List skills from the central repository
context-harness skill list

# List locally installed skills
context-harness skill list-local

# Install a skill from the repository
context-harness skill install <skill-name>

# Extract a local skill to share
context-harness skill extract <skill-name>
```

## Usage

**Start a session:**
```
/ctx login-feature
/ctx TICKET-1234
```

**Save context:**
```
/compact
```

**Switch sessions:**
```
/ctx other-feature
/contexts  # list all
```

## Commands

| Command | Description |
|---------|-------------|
| `/ctx {name}` | Switch to or create a session (creates git branch) |
| `/contexts` | List all sessions |
| `/compact` | Save context to SESSION.md |
| `/issue` | Create/manage GitHub issues |
| `/pr` | Create pull request |

## Requirements

- [OpenCode.ai](https://opencode.ai)
- [Context7 MCP](DOCS.md#context7-mcp-setup) (for research features)
- GitHub CLI `gh` (optional, for GitHub integration)

## Documentation

See [DOCS.md](DOCS.md) for architecture, customization, and advanced usage.

## Contributing

Contributions welcome! See [DOCS.md](DOCS.md) for details.

## License

[GNU AGPLv3](LICENSE)
