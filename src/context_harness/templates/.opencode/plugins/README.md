# ContextHarness Session Tracker Plugin

OpenCode plugin that tracks conversation turns and automatically updates SESSION.md files before summarization/compaction occurs.

## Problem Solved

Without this plugin, SESSION.md updates rely on the AI agent's memory to track turns - which resets when compaction occurs. This causes detail loss when:
- Context windows fill and auto-compaction triggers
- The agent forgets how many turns have passed
- SESSION.md isn't updated before summarization

## Features

- **Turn-based tracking**: Updates SESSION.md every N assistant turns (default: 2)
- **Token-based tracking**: Preemptive update when approaching context limit (default: 75%)
- **Pre-compaction injection**: Injects SESSION.md content into compaction context
- **Per-session state**: Tracks turns independently for each OpenCode session

## Installation

The plugin is automatically installed with ContextHarness. It lives at:

```
.opencode/plugins/session-tracker.ts
```

OpenCode automatically loads plugins from this directory.

## Configuration

Configure via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CH_TURN_THRESHOLD` | `2` | Update SESSION.md every N assistant turns |
| `CH_TOKEN_THRESHOLD` | `0.75` | Update when context usage exceeds this ratio |
| `CH_DEBUG` | `false` | Enable verbose logging |

Example:

```bash
export CH_TURN_THRESHOLD=3
export CH_TOKEN_THRESHOLD=0.8
export CH_DEBUG=true
```

## How It Works

### 1. Turn Tracking

The plugin listens to `message.updated` events and tracks:
- User message count
- Assistant message count (with `finish: true`)
- Token usage from message metadata

### 2. Automatic Updates

SESSION.md is updated when either:
- Assistant turns since last update >= `CH_TURN_THRESHOLD`
- Token usage ratio >= `CH_TOKEN_THRESHOLD`

Updates include:
- `**Last Updated**` timestamp
- Plugin Metrics section with turn counts and token usage

### 3. Pre-Compaction Hook

When OpenCode triggers compaction, the plugin:
1. Reads current SESSION.md content
2. Injects it into the compaction context
3. Instructs the summarizer to preserve key sections
4. Updates SESSION.md with final state

This ensures context is preserved even if compaction triggers between update intervals.

## Plugin Metrics Section

The plugin adds/updates a metrics section in SESSION.md:

```markdown
## Plugin Metrics

**User Turns**: 12
**Assistant Turns**: 11
**Last Auto-Update**: Turn 10
**Token Usage**: ~45,230

_Auto-tracked by session-tracker plugin_
```

## Debugging

Enable debug mode to see plugin activity:

```bash
export CH_DEBUG=true
```

Logs appear in OpenCode's application log with `[session-tracker]` prefix.

## Technical Notes

- **Experimental hooks**: Uses `experimental.session.compacting` which may change
- **Session detection**: Finds most recently modified SESSION.md in sessions directory
- **Model limits**: Includes conservative context limits for Claude and GPT models
- **State persistence**: Turn counts persist within an OpenCode session but reset on restart

## Related

- [Issue #89](https://github.com/co-labs-co/context-harness/issues/89) - Original feature request
- [OpenCode Plugin Docs](https://opencode.ai/docs/plugins) - Plugin system documentation
