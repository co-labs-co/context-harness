# ContextHarness

> Context-aware agent framework for [OpenCode.ai](https://opencode.ai) that maintains session continuity.

## Quickstart

```bash
# Install (one-time)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Initialize in your project
context-harness init

# Open OpenCode and start working
/baseline              # Analyze project (first time)
/ctx my-feature        # Create session + branch
# ... do your work ...
/compact               # Save context
/pr                    # Create pull request
```

That's it. Your context persists across sessions.

---

## Commands Reference

### Session Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/ctx {name}` | Create or switch to a session (creates git branch) | `/ctx login-feature` |
| `/contexts` | List all sessions with status | `/contexts` |
| `/compact` | Save current context to SESSION.md | `/compact` |

### GitHub Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/issue` | Create GitHub issue from current context | `/issue` |
| `/issue update` | Add progress comment to linked issue | `/issue update` |
| `/pr` | Create pull request for current branch | `/pr` |

### Analysis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/baseline` | Analyze project and generate PROJECT-CONTEXT.md | `/baseline` |
| `/baseline --full` | Force full regeneration | `/baseline --full` |

---

## CLI Reference

### Installation

```bash
# Install globally (recommended)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Or run without installing
uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init
```

### Core Commands

```bash
context-harness init                    # Initialize in current project
context-harness init --force            # Overwrite existing files
context-harness init --target ./path    # Install in specific directory
```

### MCP Configuration

```bash
context-harness mcp add context7        # Add Context7 for docs lookup
context-harness mcp add context7 -k KEY # With API key for higher limits
context-harness mcp list                # List configured MCP servers
```

### Skill Management

```bash
context-harness skill list              # List available skills
context-harness skill list --tags react # Filter by tag
context-harness skill list-local        # List installed skills
context-harness skill info <name>       # Show skill details
context-harness skill install <name>    # Install a skill
context-harness skill extract <name>    # Share a local skill
```

---

## How It Works

ContextHarness maintains a `SESSION.md` file for each feature/task you work on:

```
.context-harness/sessions/
├── login-feature/
│   └── SESSION.md          # Your context for this feature
├── TICKET-1234/
│   └── SESSION.md
└── api-refactor/
    └── SESSION.md
```

When you run `/compact`, your current work context is saved. When you switch sessions with `/ctx`, the previous context is preserved and the new session's context is loaded.

### Typical Workflow

```
/ctx login-feature          # Start new session, creates feature/login-feature branch
# ... work on login ...
/compact                    # Save progress
# ... more work ...
/issue                      # Create GitHub issue from context
# ... finish feature ...
/pr                         # Create pull request
```

### GitHub Integration

When `gh` CLI is available and authenticated:

- `/ctx {name}` creates a `feature/{name}` branch
- `/issue` creates a GitHub issue with full context
- `/issue update` posts progress comments
- `/pr` creates a PR linked to the issue

Graceful fallback: works locally without GitHub.

---

## Requirements

- [OpenCode.ai](https://opencode.ai)
- [uv](https://docs.astral.sh/uv/) (for installation)
- [GitHub CLI](https://cli.github.com/) `gh` (optional, for GitHub features)
- [Context7 MCP](DOCS.md#context7-mcp-setup) (optional, for research features)

---

## Documentation

See [DOCS.md](DOCS.md) for:

- Architecture and design
- SESSION.md structure
- Subagent reference
- Model configuration
- Customization guide
- Manual installation

---

## Contributing

Contributions welcome! See [DOCS.md](DOCS.md) for development details.

---

## License

[GNU AGPLv3](LICENSE)
