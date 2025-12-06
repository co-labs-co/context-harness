# ContextHarness Session

**Session**: baseline-command
**Last Updated**: 2025-12-05  
**Compaction Cycle**: #0  
**Session Started**: 2025-12-05

---

## Active Work

**Current Task**: Add /baseline command for comprehensive project analysis  
**Status**: Planning  
**Description**: Implement 3-phase analysis (discovery → questions → answers) to generate PROJECT-CONTEXT.md  
**Blockers**: None

---

## GitHub Integration

**Branch**: (not yet created)
**Issue**: #16 - https://github.com/cmtzco/context-harness/issues/16
**PR**: (none yet)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agent/baseline-discovery.md` | Phase 1: Analyze directory, language, tools, dependencies | To Create |
| `.opencode/agent/baseline-questions.md` | Phase 2: Generate and score project analysis questions | To Create |
| `.opencode/agent/baseline-answers.md` | Phase 3: Answer questions and generate PROJECT-CONTEXT.md | To Create |
| `src/context_harness/templates/.opencode/command/baseline.md` | CLI command for /baseline | To Create |

---

## Decisions Made

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| - | - | - | - |

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| GitHub Issue #16 | https://github.com/cmtzco/context-harness/issues/16 | Full feature specification |

---

## Next Steps

1. Create `@baseline-discovery` subagent
2. Create `@baseline-questions` subagent
3. Create `@baseline-answers` subagent
4. Update Primary agent with `/baseline` command workflow
5. Create `/baseline` command template
6. Add templates to installer package
7. Test on a real project

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

- ✅ Session created from GitHub issue #16

</details>

---

## Notes

### 3-Phase Architecture

```
/baseline Command Flow
┌─────────────────┐
│   User: /baseline│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  PHASE 1: @baseline-discovery       │
│  - Directory structure              │
│  - Language detection               │
│  - Build tools                      │
│  - External dependencies            │
│  → discovery-report.json            │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  PHASE 2: @baseline-questions       │
│  - Generate 30-50 questions         │
│  - Score each (0-10) on:            │
│    - Relevance                      │
│    - Validity                       │
│    - Helpfulness                    │
│  - Filter: composite score >= 8     │
│  - Regenerate if < 30 validated     │
│  → validated-questions.json         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  PHASE 3: @baseline-answers         │
│  - Answer each validated question   │
│  - Cite evidence (file:line)        │
│  - Rate confidence                  │
│  → PROJECT-CONTEXT.md               │
└─────────────────────────────────────┘
```

### Question Categories

1. Architecture Decisions
2. External Dependencies
3. Code Patterns
4. Language/Framework Choice
5. Build & Distribution
6. Security & Authentication
7. Performance & Scaling

---

_Auto-updated by ContextHarness Primary Agent every 2nd user interaction_
