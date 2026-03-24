# Quick Start

Get up and running with ContextHarness in under 5 minutes.

## Install

```bash
# Using uv (recommended)
uv tool install context-harness

# Using pip
pip install context-harness
```

## Initialize Your Project

```bash
cd your-project
context-harness init
```

This creates:
- `.context-harness/` - Session data and project context
- `.opencode/` - OpenCode configuration
- `.claude/` - Claude Code configuration

## Start a Session

In your AI coding tool (OpenCode or Claude Code):

```
/ctx my-feature
```

This creates an isolated session context for your work.

## Work Normally

Your AI agent now has access to:
- Session context in `.context-harness/sessions/my-feature/SESSION.md`
- Custom commands and skills
- Project configuration

## Compact When Needed

When your conversation gets long, preserve what matters:

```
/compact
```

This saves key context to SESSION.md so your agent can pick up where you left off.

## Next Steps

- [Install skills](docs/user-guide/skills.md) to add specialized capabilities
- [Configure MCP servers](docs/user-guide/mcp.md) for external integrations
- [Create worktrees](docs/user-guide/worktrees.md) for parallel development

## CLI Reference

```bash
context-harness --help

Commands:
  init       Initialize ContextHarness in your project
  config     Manage configuration settings
  skill      Install and manage skills
  worktree   Manage git worktrees
  mcp        Configure MCP servers
```
