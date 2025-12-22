---
description: Save current context to SESSION.md
agent: context-harness
---

Trigger a manual compaction cycle for the current session.

## Instructions

1. **Verify active session**: Ensure there is an active session. If not, prompt user to start one with `/ctx {session-name}`.

2. **Notify user**:
   ```
   🔄 Running compaction...
   ```

3. **Invoke @compaction-guide** with current context:
   ```
   @compaction-guide I need compaction guidance for a manual compaction.
   
   Current context:
   - **Working on**: [Current feature/task]
   - **Status**: [In progress/blocked/testing]
   - **Modified files**:
     - [file1]: [what was changed]
     - [file2]: [what was changed]
   - **Recent decisions**:
     - [Decision 1 and rationale]
     - [Decision 2 and rationale]
   - **Active documentation**:
     - [Link 1]: [How I used it]
   - **Blockers**: [Any blockers or none]
   
   What should I preserve in SESSION.md?
   ```

4. **Receive guidance** from @compaction-guide on what to preserve.

5. **Update SESSION.md** at `.context-harness/sessions/{active_session}/SESSION.md`:
   - Update metadata (timestamp, increment cycle number)
   - Update Active Work section
   - Update Key Files with modified files
   - Add new Decisions Made
   - Update Documentation References
   - Update Next Steps
   - Archive completed work

6. **Confirm completion**:
   ```
   ✅ Compaction complete!
      - Active work: [feature/task]
      - Key files: [count] preserved
      - Decisions: [count] recorded
      - Next steps: [count] defined
   
   SESSION.md updated at .context-harness/sessions/{active_session}/SESSION.md
   ```
