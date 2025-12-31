# ContextHarness Session

**Session**: web-ui
**Last Updated**: 2025-12-31T12:30:00Z  
**Compaction Cycle**: #0  
**Session Started**: 2025-12-31T12:00:00Z

---

## Active Work

**Current Task**: Web UI for ContextHarness with Agent Context Protocol Integration  
**Status**: Planning  
**Description**: Build a web interface that uses OpenCode Agent Context Protocol as the backend for executing work. Manage projects, sessions, and agents through a unified UI.  
**Blockers**: Need decisions on tech stack preferences (local-first vs hosted, monorepo vs separate)

---

## GitHub Integration

**Branch**: feature/web-ui
**Issue**: #54 - https://github.com/co-labs-co/context-harness/issues/54
**PR**: (none yet)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `src/context_harness/interfaces/sdk/client.py` | SDK client ready for web integration | Existing |
| `src/context_harness/services/` | Service layer for business logic | Existing |
| `src/context_harness/primitives/` | Domain models for API responses | Existing |
| `ARCHITECTURE.md` | System architecture documentation | Reference |
| `web/` | Web UI directory (to be created) | Planned |

---

## Decisions Made

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| Primary integration path | OpenCode Server HTTP API | Provides REST + SSE, TypeScript SDK available | 2025-12-31 |
| Real-time streaming | SSE (Server-Sent Events) | Simpler than WebSocket, sufficient for agent streaming | 2025-12-31 |
| Backend framework | FastAPI (Python) | Already using Python, direct SDK integration | 2025-12-31 |
| Frontend framework | React + TypeScript | Ecosystem support, @opencode-ai/sdk compatibility | 2025-12-31 |

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| OpenCode SDK Docs | https://opencode.ai/docs/sdk | TypeScript SDK for frontend |
| OpenCode Server Docs | https://opencode.ai/docs/server | Backend integration patterns |
| Agent Client Protocol | https://agentclientprotocol.com | ACP specification for agent communication |
| ContextHarness ARCHITECTURE.md | Local file | Primitives/Services/Interfaces pattern |

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         WEB UI (React/Next.js)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Projects   │  │  Sessions   │  │   Agents    │  │   Chat    │ │
│  │  Dashboard  │  │   Manager   │  │   Monitor   │  │ Interface │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└────────────────────────────────────────────────────────────────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌────────────────────────────────────────────────────────────────────┐
│                    WEB BACKEND (FastAPI/Python)                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              ContextHarness SDK Client                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Sessions API │  │ Projects API │  │  Agent Bridge (ACP/HTTP) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
          │                │                        │
          ▼                ▼                        ▼
┌─────────────────┐  ┌─────────────────┐   ┌──────────────────────┐
│ ContextHarness  │  │ File System     │   │   OpenCode Server    │
│   Services      │  │ (.context-      │   │  (Agent Execution)   │
│                 │  │   harness/)     │   │    port 4096         │
└─────────────────┘  └─────────────────┘   └──────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (High Priority)
- [ ] Create `web/` directory structure with FastAPI backend scaffolding
- [ ] Create React/Next.js frontend scaffolding
- [ ] Define OpenAPI spec for Sessions, Projects, Agents endpoints

### Phase 2: Core APIs (High Priority)
- [ ] Sessions API - REST endpoints wrapping ContextHarness SDK
- [ ] Projects API - Endpoints for connecting/managing multiple projects

### Phase 3: Agent Integration (Medium Priority)
- [ ] Agent Bridge - Integration with OpenCode Server
- [ ] SSE streaming for real-time agent activity

### Phase 4: Frontend Implementation (Medium Priority)
- [ ] React components for dashboard, sessions, agent monitor
- [ ] Chat Interface for interacting with agents

### Phase 5: Polish & Deploy (Low Priority)
- [ ] Authentication and access control
- [ ] Docker/local-first deployment configuration

---

## Next Steps

1. Get decisions on open questions (local-first vs hosted, monorepo vs separate)
2. Create `web/` directory structure
3. Set up FastAPI backend with basic routes
4. Set up React frontend scaffolding
5. Implement Sessions API first (wrapping existing SDK)

---

## Open Questions

1. **Local-first or hosted?** Should this run on localhost with projects on the same machine, or support remote project connections?
2. **Monorepo or separate repos?** Keep web UI in this repo under `web/` or create a separate repo?
3. **MVP scope?** Start with session management + agent chat, or include all features?

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

- [x] Created GitHub issue #54 with full feature specification
- [x] Researched OpenCode Server HTTP API and Agent Context Protocol
- [x] Reviewed existing ContextHarness SDK client architecture
- [x] Defined recommended tech stack and architecture
- [x] Created implementation phases breakdown

</details>

---

## Notes

Session `web-ui` initialized by ContextHarness Primary Agent.

Key insight: The existing `src/context_harness/interfaces/sdk/client.py` provides a solid foundation for web integration. The primitives-based architecture means API responses can serialize cleanly.

---

_Auto-updated by ContextHarness Primary Agent every 2nd user interaction_
