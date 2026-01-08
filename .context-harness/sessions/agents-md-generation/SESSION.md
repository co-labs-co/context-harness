# ContextHarness Session

**Session**: agents-md-generation
**Last Updated**: 2025-01-08
**Compaction Cycle**: #0
**Session Started**: 2025-01-08

---

## Active Work

**Current Task**: Add AGENTS.md generation as Phase 5 of /baseline command
**Status**: In Progress
**Description**: Implement Phase 5 that generates AGENTS.md following OpenCode specification, combining PROJECT-CONTEXT.md with discovered skills
**Blockers**: None

---

## GitHub Integration

**Branch**: feat/agents-md-generation
**Issue**: #60 - https://github.com/co-labs-co/context-harness/issues/60
**PR**: (pending)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agent/baseline-agents.md` | Phase 5 subagent - generates AGENTS.md content | Created |
| `.opencode/command/baseline.md` | Updated command with Phase 5 flow | Updated |
| `src/context_harness/templates/.opencode/agent/baseline-agents.md` | Template for installer | Created |
| `src/context_harness/templates/.opencode/command/baseline.md` | Template for installer | Updated |

---

## Decisions Made

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| Phase 5 placement | After skill extraction | AGENTS.md depends on both PROJECT-CONTEXT.md and skills | 2025-01-08 |
| Lazy-loading syntax | `@path/to/skill.md` | Follows OpenCode specification for external file references | 2025-01-08 |
| Update mode | `--agents-update` flag | Allow incremental updates to preserve custom sections | 2025-01-08 |
| Subagent name | `@baseline-agents` | Consistent with existing naming (`baseline-*`) | 2025-01-08 |

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| OpenCode Rules Documentation | https://opencode.ai/docs/rules/ | AGENTS.md specification and format |
| GitHub Issue #60 | https://github.com/co-labs-co/context-harness/issues/60 | Feature specification |

---

## Next Steps

1. Commit changes and push to remote
2. Create PR linking to issue #60
3. Test the implementation by running /baseline

---

## Notes

### Phase 5 Flow

```
Phase 4 Complete (skills in .opencode/skill/)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: AGENTS.MD GENERATION                              │
│                                                              │
│  Inputs:                                                    │
│  - PROJECT-CONTEXT.md (from Phase 3)                        │
│  - Skills metadata (from Phase 4)                           │
│  - discovery_report (from Phase 1)                          │
│  - existing AGENTS.md (if present)                          │
│                                                              │
│              ┌─────────────────────┐                        │
│              │ @baseline-agents    │                        │
│              └─────────────────────┘                        │
│                         │                                   │
│                         ▼                                   │
│              AGENTS.md (OpenCode rules file)                │
└─────────────────────────────────────────────────────────────┘
```

### New Flags Added

| Flag | Effect |
|------|--------|
| `--skip-agents` | Run Phases 1-4, skip AGENTS.md generation |
| `--agents-only` | Run only Phase 5 with existing context + skills |
| `--agents-update` | Update existing AGENTS.md instead of overwriting |
| `--agents-output [path]` | Custom output location for AGENTS.md |

---

_Session created for feature implementation_
