# ContextHarness Framework

> A context-aware agent framework for OpenCode.ai that maintains session continuity through user-driven compaction cycles.

## Overview

ContextHarness solves the problem of context loss in long development sessions by implementing user-driven context preservation. The framework uses a **single executor pattern** with advisory subagents - only the Primary Agent executes work, while specialized subagents provide guidance.

## Key Features

- **User-Driven Compaction**: Use `/compact` command or choose compaction from options
- **Always-Available Option**: Every response offers compaction as a "What's Next?" choice
- **Single Executor**: Only Primary Agent writes code and modifies files
- **Advisory Subagents**: Specialized guidance without execution authority
- **SESSION.md**: Living document that maintains work continuity
- **Pure Markdown**: No custom code - entirely OpenCode.ai agent files

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PRIMARY AGENT                        │
│  - Executes ALL work (code, files, commands)            │
│  - Offers compaction option after every response        │
│  - Supports /compact command                            │
│  - Reads/writes SESSION.md                              │
│  - Invokes subagents for guidance                       │
└────────────┬──────────────────────────────────┬─────────┘
             │                                  │
    @research-subagent                  @compaction-guide
    @docs-subagent                             │
             │                                  │
             ▼                                  ▼
┌──────────────────────────┐      ┌─────────────────────────┐
│ Grounded Research        │      │ Compaction Guide        │
│ & Docs Subagents         │      │ Subagent                │
│                          │      │                         │
│ - Context7 MCP access    │      │ - Analyze session       │
│ - Web search verification│      │ - Recommend preserve    │
│ - Provide guidance       │      │ - NO execution          │
│ - Return recommendations │      │                         │
│ - NO execution           │      │                         │
└──────────────────────────┘      └─────────────────────────┘
```

## Directory Structure

```
.context-harness/
├── sessions/                      # Multiple concurrent sessions
│   ├── login-feature/
│   │   └── SESSION.md             # Session context for login feature
│   ├── TICKET-1234/
│   │   └── SESSION.md             # Session context for ticket 1234
│   └── api-rate-limiting/
│       └── SESSION.md             # Session context for rate limiting
├── templates/
│   └── session-template.md        # Template for new sessions
└── README.md                      # This file

.opencode/agent/
├── context-harness.md             # The ONLY executor (Primary Agent)
├── research-subagent.md           # Research guidance (advisory)
├── docs-subagent.md               # Documentation guidance (advisory)
└── compaction-guide.md            # Compaction guidance (advisory)
```

## Quick Start

### 1. Start or Resume a Session

Invoke the Primary Agent with a session identifier:

```
@context-harness /session login-feature
@context-harness /session TICKET-1234
@context-harness Let's work on the api-rate-limiting feature
```

**Session Naming Conventions**:
- Feature names: `login-feature`, `oauth-integration`, `dashboard-redesign`
- Ticket IDs: `TICKET-1234`, `JIRA-567`, `GH-89`
- Story IDs: `STORY-456`, `US-789`

### 2. Work Normally

The Primary Agent handles all execution. It will:
- Read SESSION.md on activation to resume context
- Execute your requests (code, files, commands)
- Invoke subagents when guidance is needed
- **Offer compaction as an option after every response**

### 3. Compact When Ready

You have two ways to trigger compaction:

**Option A: Choose from "What's Next?"**
Every response ends with options, including compaction:
```
## What's Next?

Here are your options:
1. Continue with next task
2. Review the changes
3. 🔄 **Compact context** (`/compact`) - Save current progress to SESSION.md
```

**Option B: Use the `/compact` command**
Type `/compact` anytime to immediately save context:
```
/compact
```

## Commands

| Command | Description |
|---------|-------------|
| `/session {name}` | Switch to or create a named session |
| `/sessions` | List all available sessions |
| `/compact` | Save current context to SESSION.md immediately |

## Agents

### Primary Agent (`@primary-agent`)

**Role**: Executor  
**Authority**: Full execution (code, files, commands)

The Primary Agent is the sole executor in the framework. It:
- Writes code and modifies files
- Runs commands and creates directories
- Maintains SESSION.md
- Invokes subagents for guidance
- **Always offers compaction option at end of responses**
- **Supports `/compact` command for immediate compaction**

### Research Subagent (`@research-subagent`)

**Role**: Advisory  
**Authority**: None (guidance only)

Provides grounded research guidance using Context7 MCP and web search:
- **Context7 MCP**: Up-to-date documentation for popular libraries/frameworks
- **Web Search**: Real-time information lookup and verification
- **Best Practices**: Current patterns and approaches
- **API Documentation**: Accurate, version-specific usage
- **Technology Comparisons**: Informed analysis with sources

**Enhanced Capabilities**:
- All responses are grounded in verifiable sources
- Cross-references information from Context7, web search, and official docs
- Includes version information and compatibility notes
- Cites sources with verification dates

**Example**:
```
@research-subagent What are best practices for rate limiting in Flask?
```

### Documentation Subagent (`@docs-subagent`)

**Role**: Advisory  
**Authority**: None (guidance only)

Provides documentation guidance on:
- Official documentation summaries
- Framework and library docs
- API references
- Configuration guides

**Example**:
```
@docs-subagent Summarize Next.js App Router authentication patterns
```

### Compaction Guide (`@compaction-guide`)

**Role**: Advisory  
**Authority**: None (guidance only)

Provides compaction guidance on:
- What context to preserve
- What to archive vs. discard
- SESSION.md structure recommendations
- Next steps prioritization

**Invoked by Primary Agent** when user triggers compaction via `/compact` or selects the compaction option.

## SESSION.md

The living document that maintains session continuity. Each session has its own SESSION.md file at `.context-harness/sessions/{session-name}/SESSION.md`.

### Sections

| Section | Purpose |
|---------|---------|
| **Active Work** | Current task, status, blockers |
| **Key Files** | Files being modified with purposes |
| **Decisions Made** | Important decisions with rationale |
| **Documentation References** | Relevant docs with links |
| **Next Steps** | Prioritized action items |
| **Completed This Session** | Archived completed work |
| **Notes** | Additional context |

### Update Cycle

1. User triggers compaction (`/compact` or selects option)
2. Primary Agent invokes @compaction-guide with current context
3. Receives structured preservation recommendations
4. Updates SESSION.md with current state
5. Confirms compaction to user

## Compaction Workflow

### User-Driven Compaction

```
User works with Primary Agent
        │
        ▼
Every response ends with "What's Next?" options
        │
        ├─► User selects compaction option
        │   OR
        ├─► User types /compact
        │
        ▼
┌─────────────────────────────────┐
│     COMPACTION TRIGGERED        │
│  1. Invoke @compaction-guide    │
│  2. Receive recommendations     │
│  3. Update SESSION.md           │
│  4. Confirm to user             │
└─────────────────────────────────┘
        │
        ▼
User continues working...
```

### Example Flow

```
User: "Add a login button"
Agent: [Creates login button]
       ---
       ## What's Next?
       1. Add logout functionality
       2. Style the button
       3. 🔄 **Compact context** (`/compact`)

User: "/compact"
Agent: 🔄 Running compaction...
       ✅ Compaction complete!
       - Active work: Login feature
       - Key files: 2 preserved
       - Decisions: 1 recorded
```

## Subagent Isolation

Subagents are **advisory only** - they cannot execute work. Isolation is enforced through:

1. **Persona Identity**: Each subagent explicitly states "guidance only"
2. **Absolute Prohibitions**: Forbidden actions listed in persona
3. **Mandatory Response Format**: Structured guidance with handoff
4. **Violation Detection**: Rules to catch and redirect execution requests

If a subagent is asked to execute, it responds:
> "I provide guidance only. @primary-agent will execute based on my recommendations."

## Best Practices

### For Users

1. **Compact regularly**: Use `/compact` or select the option when you've made progress
2. **Trust the Primary Agent**: It's the sole executor
3. **Use subagents for research**: Invoke them before complex implementations
4. **Review SESSION.md**: Check it to understand current context

### For Session Continuity

1. **Use meaningful session names**: Match feature names or ticket IDs for easy reference
2. **Start with @context-harness /session {name}**: It reads/creates SESSION.md on activation
3. **Don't delete SESSION.md**: It's your context lifeline for that session
4. **Compact before switching sessions**: Ensures context is preserved
5. **Check "Next Steps"**: Resume work from where you left off
6. **Use `/sessions` to see all work**: View all active sessions at a glance

### When to Compact

- After completing a significant task or feature
- Before taking a break or ending your session
- When you've made important decisions
- After modifying multiple files
- When the conversation is getting long

## Troubleshooting

### SESSION.md Missing

Primary Agent will create a new session directory and SESSION.md from template. Previous context for that session is lost.

### Session Not Found

If you try to switch to a session that doesn't exist, Primary Agent will offer to create it.

### Compaction Not Working

1. Try running `/compact` explicitly
2. Check that SESSION.md exists at `.context-harness/sessions/{session-name}/SESSION.md`
3. Ensure the Primary Agent has write permissions

### Subagent Trying to Execute

This shouldn't happen with proper persona definitions. If it does, remind the subagent:
> "You provide guidance only. Return to @primary-agent for execution."

### Context Seems Lost

1. Check SESSION.md for current state
2. Invoke @primary-agent to reload context
3. Review "Active Work" and "Next Steps" sections
4. Run `/compact` to save current state

## Technical Details

### Implementation

- **Platform**: OpenCode.ai markdown agent files
- **No Custom Code**: Entirely persona-based behavioral rules
- **File-Based State**: SESSION.md is the only persistent storage
- **Incremental Updates**: SESSION.md updated, not rewritten

### Limitations

- **No Automatic Context Detection**: Platform doesn't expose context metrics
- **Behavioral Isolation**: Subagent restrictions are persona-enforced, not technical
- **Manual Activation**: User must invoke @primary-agent to start

### OpenCode.ai Compatibility

This framework follows OpenCode.ai agent file conventions:
- Markdown files with persona definitions
- @mention syntax for agent invocation
- File system access for SESSION.md management

## Contributing

To extend ContextHarness:

1. **New Subagents**: Create in `.context-harness/agents/` following the advisory pattern
2. **SESSION.md Sections**: Update template and compaction guide recommendations
3. **Compaction Logic**: Modify compaction-guide.md preservation rules

All changes should maintain:
- Single executor pattern (Primary Agent only)
- Advisory-only subagents (no execution)
- Incremental SESSION.md updates

## License

[Your License Here]

---

**ContextHarness** - Harness your context, maintain your flow.
