# ContextHarness Session

**Session**: web-ui
**Last Updated**: 2025-12-31T20:45:00Z  
**Compaction Cycle**: #1  
**Session Started**: 2025-12-31T12:00:00Z

---

## Active Work

**Current Task**: Web UI with OpenCode ACP Integration  
**Status**: ✅ COMPLETE - Ready for PR merge  
**Description**: Local-first web interface with full OpenCode ACP integration. Real AI agent responses, tool call visualization, session context management.  
**Blockers**: None

---

## GitHub Integration

**Branch**: feature/web-ui
**Issue**: #54 - https://github.com/co-labs-co/context-harness/issues/54
**PR**: #55 - https://github.com/co-labs-co/context-harness/pull/55

---

## Key Decisions

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| Deployment model | **Local-first** | Prioritize localhost with local projects | 2025-12-31 |
| Repository structure | **Monorepo (`web/`)** | Keep in this repo, add/update primitives | 2025-12-31 |
| MVP scope | **Sessions + Chat + Voice** | Core interaction loop with voice input | 2025-12-31 |
| Agent protocol | **ACP (Agent Client Protocol)** | JSON-RPC 2.0 over stdio with OpenCode | 2025-12-31 |
| Real-time streaming | SSE (Server-Sent Events) | Bridge ACP notifications to frontend | 2025-12-31 |
| Backend framework | FastAPI (Python) | Already using Python | 2025-12-31 |
| Frontend framework | React + TypeScript | Ecosystem, SDK compatibility | 2025-12-31 |
| Voice input (MVP) | Web Speech API | Browser-native, no backend needed | 2025-12-31 |
| Default agent | **context-harness** | Use ContextHarness Primary Agent | 2025-12-31 |
| Session context | **Prepend /ctx** | First message includes /ctx {session} | 2025-12-31 |

---

## Implementation Summary

### Phase 1-5: MVP Foundation ✅ COMPLETE
- FastAPI backend with health, sessions, chat routes
- Next.js frontend with SessionList, ChatInterface, VoiceInput
- Dark cyberpunk theme with mobile-responsive design
- Keyboard shortcuts, toasts, session persistence

### Phase 6: OpenCode ACP Integration ✅ COMPLETE
- Full ACP client (`acp_client.py`) - JSON-RPC 2.0 over stdio
- Real AI agent responses instead of placeholders
- SSE bridge for streaming updates
- Tool call, thought, and plan visualization in UI
- Session context via `/ctx {session_id}` on first message
- Default to `context-harness` agent mode
- Auto-init framework on startup

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `src/context_harness/interfaces/web/services/acp_client.py` | ACP client for OpenCode | ✅ Created |
| `src/context_harness/interfaces/web/services/__init__.py` | Services module exports | ✅ Created |
| `src/context_harness/interfaces/web/routes/chat.py` | Chat API + ACP bridge | ✅ Updated |
| `src/context_harness/interfaces/web/app.py` | FastAPI app + auto-init | ✅ Updated |
| `web/src/components/ChatInterface.tsx` | Chat UI + SSE events | ✅ Updated |

---

## ACP Integration Details

### Protocol Flow
```
1. Initialize: negotiate version (1) and capabilities
2. session/new: create session with cwd
3. session/set_mode: set to "context-harness" agent
4. session/prompt: send /ctx {session}\n\n{message}
5. Receive session/update notifications → SSE events
```

### SSE Event Types
| Event | Description |
|-------|-------------|
| `user_message` | User's message recorded |
| `start` | Agent response started |
| `chunk` | Text chunk from agent |
| `thought` | Agent's internal thought |
| `tool_call` | Agent invoked a tool |
| `tool_call_update` | Tool status changed |
| `plan` | Agent's plan entries |
| `mode_change` | Agent mode changed |
| `error` | Error occurred |
| `complete` | Response finished |

### Frontend Components
- **ToolCallDisplay**: Expandable tool calls with status icons
- **ThoughtDisplay**: Collapsible agent thoughts
- **PlanDisplay**: Task list with progress tracking

---

## Commits in This Branch

| SHA | Message |
|-----|---------|
| `952baa5` | feat(web): integrate OpenCode ACP for real AI agent responses |
| `273ec83` | feat(web): add frontend support for tool calls, thoughts, and plans |
| `f0752cb` | fix(web): pass ContextHarness session context to OpenCode via /ctx |
| `55a6187` | feat(web): auto-init framework and default to context-harness agent |

---

## How to Run

```bash
# Start the web server (auto-initializes framework)
uv run context-harness serve

# Or manually:
uv run uvicorn context_harness.interfaces.web.app:app --reload --port 8000

# Access at http://localhost:8000
```

---

## Test Results

```
GET /api/chat/status
→ OpenCode v1.0.219 connected
→ Capabilities: load_session, prompt_image

POST /api/chat/web-ui/stream
→ Agent reads .context-harness/sessions/web-ui/SESSION.md
→ Responds with correct session context
→ Tool calls displayed with live status updates
```

---

## Next Steps (Future Work)

1. **Tool Call Details**: Show tool input/output in expandable UI
2. **Permission Requests**: Handle agent permission prompts
3. **Multiple Agents**: Allow switching between agent modes
4. **Session History**: Persist chat messages to disk
5. **WebSocket Option**: Alternative to SSE for bidirectional comms

---

## Archived Work

<details>
<summary>Previous Session Work (Expand to view)</summary>

### Initial MVP (Phase 1-4)
- Created GitHub issue #54
- Researched OpenCode Server HTTP API
- Built FastAPI backend with health, sessions, chat routes
- Built Next.js frontend with SessionList, ChatInterface, VoiceInput
- Added Phase 5 polish (mobile design, toasts, shortcuts)

### ACP Research
- Corrected ACP spec URL: https://agentclientprotocol.com
- NOT the IBM BeeAI "Agent Communication Protocol"
- ACP uses JSON-RPC 2.0 over stdio

</details>

---

_Auto-updated by ContextHarness Primary Agent_
