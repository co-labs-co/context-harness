# ContextHarness Session

**Session**: rlm-pattern
**Last Updated**: 2025-12-05  
**Compaction Cycle**: #0  
**Session Started**: 2025-12-05

---

## Active Work

**Current Task**: Implement Recursive Language Model (RLM) Pattern via Agent Definitions  
**Status**: Research / Planning  
**Description**: Enable processing of unbounded context lengths through recursive self-calls and REPL-style environment interaction  
**Blockers**: None

---

## GitHub Integration

**Branch**: (not yet created)
**Issue**: #14 - https://github.com/cmtzco/context-harness/issues/14
**PR**: (none yet)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agent/rlm-orchestrator.md` | Root LM (depth=0) that manages recursive processing | To Create |
| `.opencode/agent/rlm-worker.md` | Subagent for partitioned context processing | To Create |
| `.context-harness/rlm-context/` | Storage for large context files | To Create |

---

## Decisions Made

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| - | - | - | - |

---

## Documentation References

| Title | URL | Relevance |
|-------|-----|-----------|
| GitHub Issue #14 | https://github.com/cmtzco/context-harness/issues/14 | Full feature specification |
| RLM Paper (Zhang & Khattab) | https://alexzhang13.github.io/blog/2025/rlm/ | Original research paper |
| Python Implementation | https://github.com/ysz/recursive-llm | Reference implementation |
| Official Implementation | https://github.com/alexzhang13/rlm | Canonical implementation |

---

## Next Steps

### Phase 1: Proof of Concept
1. Create `rlm-orchestrator.md` agent definition
2. Create `rlm-worker.md` subagent definition
3. Test with simple long-context summarization task
4. Document patterns that emerge

### Phase 2: Production Ready
5. Add configurable chunking strategies
6. Implement recursion depth limits
7. Add cost/token tracking
8. Create user-facing CLI commands

### Phase 3: Optimization
9. Implement prefix caching (if available)
10. Add parallel partition processing
11. Create benchmarking suite
12. Compare with baseline direct LLM calls

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

- ✅ Session created from GitHub issue #14

</details>

---

## Notes

### RLM Concept Alignment with ContextHarness

| RLM Concept | ContextHarness Equivalent |
|-------------|---------------------------|
| Root LM (depth=0) | Primary Agent |
| Recursive LM calls (depth=1+) | Subagent invocations |
| REPL Environment | Bash tool + file operations |
| Context as variable | SESSION.md + file system |
| Partition + Map | Task tool for parallel subagent work |

### Key Results from Paper
- RLM(GPT-5-mini) outperforms GPT-5 on long-context benchmarks by 33%+ while being cheaper
- Processes 100k+ tokens effectively with any LLM
- Mitigates "context rot" - performance degradation with longer context
- RLMs maintain performance even at 10M+ tokens

### Challenges to Address
1. Recursion depth management - prevent infinite loops
2. Cost tracking across recursive calls
3. Context partitioning strategies - when to chunk vs. grep vs. summarize
4. Token efficiency - minimize redundant context in recursive calls
5. Error propagation in deep recursion chains

---

_Auto-updated by ContextHarness Primary Agent every 2nd user interaction_
