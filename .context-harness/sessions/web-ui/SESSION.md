# ContextHarness Session

**Session**: web-ui
**Last Updated**: 2025-12-31T13:00:00Z  
**Compaction Cycle**: #0  
**Session Started**: 2025-12-31T12:00:00Z

---

## Active Work

**Current Task**: Web UI MVP - Sessions + Chat + Voice  
**Status**: Ready to Build  
**Description**: Build a local-first web interface with session management, chat interface, and voice-to-text input. Monorepo structure under `web/` with new primitives as needed.  
**Blockers**: None - all decisions made

---

## GitHub Integration

**Branch**: feature/web-ui
**Issue**: #54 - https://github.com/co-labs-co/context-harness/issues/54
**PR**: (none yet)

---

## Key Decisions

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| Deployment model | **Local-first** | Prioritize localhost with local projects | 2025-12-31 |
| Repository structure | **Monorepo (`web/`)** | Keep in this repo, add/update primitives | 2025-12-31 |
| MVP scope | **Sessions + Chat + Voice** | Core interaction loop with voice input | 2025-12-31 |
| Primary integration | OpenCode Server HTTP API | REST + SSE, TypeScript SDK | 2025-12-31 |
| Real-time streaming | SSE (Server-Sent Events) | Simpler than WebSocket | 2025-12-31 |
| Backend framework | FastAPI (Python) | Already using Python | 2025-12-31 |
| Frontend framework | React + TypeScript | Ecosystem, SDK compatibility | 2025-12-31 |
| Voice input (MVP) | Web Speech API | Browser-native, no backend needed | 2025-12-31 |

---

## MVP Features

### 1. Session Management
- View all sessions from `.context-harness/sessions/*/SESSION.md`
- Create, switch, and archive sessions
- Real-time session state visualization

### 2. Chat Interface
- Send prompts to ContextHarness Primary Agent
- Stream agent responses in real-time (SSE)
- View tool calls and results
- Message history within session

### 3. Voice-to-Text Input 🎤
- Microphone button for voice input
- Speech-to-text via Web Speech API
- Visual feedback during recording
- Transcription preview before sending

---

## Directory Structure (Planned)

```
context-harness/
├── src/context_harness/
│   ├── primitives/
│   │   ├── message.py             # NEW: Chat message primitives
│   │   └── voice.py               # NEW: Voice transcription primitives
│   ├── services/
│   │   ├── session_service.py     # NEW: Full session CRUD
│   │   └── chat_service.py        # NEW: Chat/prompt handling
│   └── interfaces/
│       └── web/                   # NEW: FastAPI backend
│           ├── app.py
│           └── routes/
│
├── web/                           # NEW: React frontend
│   ├── package.json
│   └── src/
│       ├── components/
│       │   ├── SessionList.tsx
│       │   ├── ChatInterface.tsx
│       │   └── VoiceInput.tsx
│       └── hooks/
│           ├── useSession.ts
│           ├── useChat.ts
│           └── useVoice.ts
```

---

## New Primitives Needed

### Message (`primitives/message.py`)
```python
@dataclass
class Message:
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    session_id: str
    tool_calls: Optional[List[ToolCall]] = None

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class ToolResult:
    tool_call_id: str
    output: str
    is_error: bool = False
```

### VoiceTranscription (`primitives/voice.py`)
```python
@dataclass
class VoiceTranscription:
    id: str
    text: str
    confidence: float
    duration_ms: int
    timestamp: datetime
    source: Literal["web_speech_api", "whisper"]
```

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `src/context_harness/interfaces/sdk/client.py` | SDK client for web integration | Existing |
| `src/context_harness/primitives/` | Domain models | Existing (extend) |
| `src/context_harness/services/` | Business logic | Existing (extend) |
| `src/context_harness/interfaces/web/` | FastAPI backend | To Create |
| `web/` | React frontend | To Create |

---

## Implementation Phases

### Phase 1: Foundation 🎯 CURRENT
- [ ] Create `src/context_harness/primitives/message.py`
- [ ] Create `src/context_harness/primitives/voice.py`
- [ ] Create `src/context_harness/interfaces/web/` with FastAPI app
- [ ] Create `web/` with React/Next.js scaffolding
- [ ] Basic health check endpoint

### Phase 2: Sessions MVP
- [ ] SessionService with full CRUD
- [ ] Sessions API endpoints
- [ ] Frontend: SessionList component
- [ ] Frontend: Session detail view

### Phase 3: Chat MVP
- [ ] ChatService with OpenCode Server integration
- [ ] Chat API with SSE streaming
- [ ] Frontend: ChatInterface component
- [ ] Frontend: MessageBubble component

### Phase 4: Voice Input
- [ ] VoiceInput component (Web Speech API)
- [ ] Recording indicator UI
- [ ] Transcription preview
- [ ] Optional: Whisper fallback

### Phase 5: Polish
- [ ] Error handling and loading states
- [ ] Session persistence
- [ ] Keyboard shortcuts
- [ ] Mobile-responsive design

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| OpenCode SDK Docs | https://opencode.ai/docs/sdk | TypeScript SDK |
| OpenCode Server Docs | https://opencode.ai/docs/server | Backend integration |
| Agent Client Protocol | https://agentclientprotocol.com | ACP specification |
| Web Speech API | https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API | Voice input |
| FastAPI | https://fastapi.tiangolo.com | Backend framework |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         WEB UI (React/Next.js)                      │
│  ┌─────────────┐  ┌─────────────────────────────────┐              │
│  │  Sessions   │  │         Chat Interface          │              │
│  │   Manager   │  │  ┌─────────┐  ┌─────────────┐   │              │
│  │             │  │  │  Text   │  │   Voice 🎤  │   │              │
│  │             │  │  │  Input  │  │   Input     │   │              │
│  └──────┬──────┘  └──────┬──────────────┬───────────┘              │
└─────────┼────────────────┼──────────────┼──────────────────────────┘
          │                │              │
          ▼                ▼              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    WEB BACKEND (FastAPI/Python)                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              ContextHarness SDK Client                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Sessions API │  │   Chat API   │  │  Agent Bridge (SSE)      │  │
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

## Next Steps

1. ✅ ~~Get decisions on open questions~~
2. Create new primitives (`message.py`, `voice.py`)
3. Create FastAPI backend skeleton
4. Create React frontend skeleton
5. Implement Sessions API

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

- [x] Created GitHub issue #54 with full feature specification
- [x] Researched OpenCode Server HTTP API and Agent Context Protocol
- [x] Reviewed existing ContextHarness SDK client architecture
- [x] Defined recommended tech stack and architecture
- [x] Created implementation phases breakdown
- [x] Got decisions: local-first, monorepo, sessions+chat+voice MVP
- [x] Updated issue #54 with MVP scope and voice requirements

</details>

---

## Notes

**Voice-to-Text Strategy**: Start with Web Speech API (browser-native, free, works in Chrome) for MVP. Can add Whisper as optional upgrade later for better accuracy/privacy.

**Key insight**: The existing SDK client provides a solid foundation. Primitives architecture means API responses serialize cleanly.

---

_Auto-updated by ContextHarness Primary Agent every 2nd user interaction_
