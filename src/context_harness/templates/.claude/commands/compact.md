---
description: Manually trigger context compaction and update SESSION.md for the current session
allowed-tools: Read, Write, Edit, Glob
---

Compact context for current session.

## Instructions

1. **Identify current session**: Check for active session in context

2. **Gather current context**:
   - Files modified in this conversation
   - Decisions made and their rationale
   - Documentation references used
   - Current task status
   - Next steps identified

3. **Invoke @compaction-guide** for preservation recommendations

4. **Update SESSION.md** with compacted context:
   - Increment compaction cycle number
   - Update timestamp
   - Preserve essential context per recommendations

5. **Confirm to user**:
   ```
   Context compacted (Cycle #[N])
   - Preserved: [summary]
   - SESSION.md updated
   ```
