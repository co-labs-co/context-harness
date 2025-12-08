# ContextHarness

> Context-aware agent framework for [OpenCode.ai](https://opencode.ai) that maintains session continuity.

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
uvx --from "git+https://github.com/cmtzco/context-harness.git" context-harness init
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
