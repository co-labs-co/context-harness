# ContextHarness Session

**Session**: spec-system
**Last Updated**: 2025-12-05  
**Compaction Cycle**: #0  
**Session Started**: 2025-12-05

---

## Active Work

**Current Task**: Add feature/bug specification system for named sessions  
**Status**: Planning  
**Description**: Create SPEC.md system to preserve intent and requirements alongside execution state in SESSION.md  
**Blockers**: None

---

## GitHub Integration

**Branch**: (not yet created)
**Issue**: #2 - https://github.com/cmtzco/context-harness/issues/2
**PR**: (none yet)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.context-harness/templates/spec-template.md` | Template for new SPEC.md files | To Create |
| `.opencode/agent/context-harness.md` | Primary agent - add SPEC.md creation logic | To Update |
| `src/context_harness/templates/.opencode/command/spec.md` | CLI command for /spec | To Create |

---

## Decisions Made

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| - | - | - | - |

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| GitHub Issue #2 | https://github.com/cmtzco/context-harness/issues/2 | Full feature specification |

---

## Next Steps

1. Design SPEC.md template
2. Add template to `.context-harness/templates/`
3. Update primary agent to create SPEC.md when starting new sessions
4. Add `/spec` command to view/edit current session's spec
5. Update README with spec workflow documentation

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

- ✅ Session created from GitHub issue #2

</details>

---

## Notes

### Problem Being Solved
- Original intent can get lost as implementation progresses
- Context about *why* we're building something gets scattered
- Hard to validate if final implementation matches original requirements
- SESSION.md tracks execution state, but not the specification/intent

### Proposed Directory Structure
```
.context-harness/sessions/{session-name}/
├── SESSION.md    # Execution state (current)
└── SPEC.md       # Feature/bug specification (new)
```

### SPEC.md Should Include
- **Intent**: What are we trying to accomplish and why?
- **Requirements**: Specific acceptance criteria
- **Scope**: What's in/out of scope
- **Context**: Links to issues, PRs, discussions, documentation
- **Success Criteria**: How do we know when it's done?

### Benefits
1. **Clarity**: Clear reference for what we're building
2. **Validation**: Can check implementation against spec
3. **Context Continuity**: Intent survives compaction cycles
4. **Collaboration**: Others can understand the feature quickly
5. **History**: Documents the "why" for future reference

---

_Auto-updated by ContextHarness Primary Agent every 2nd user interaction_
