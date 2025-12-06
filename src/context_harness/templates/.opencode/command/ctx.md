---
description: Switch to or create a ContextHarness session
agent: context-harness
---

Switch to session: $ARGUMENTS

## Instructions

1. **Check if session exists**: Look for `.context-harness/sessions/$ARGUMENTS/SESSION.md`

2. **If session EXISTS**:
   - Read the SESSION.md file
   - Load the context (Active Work, Key Files, Decisions, Next Steps)
   - Set `active_session = "$ARGUMENTS"`
   - Greet user with session summary:
     ```
     👋 ContextHarness Primary Agent Activated
     
     📂 Session: $ARGUMENTS
        - **Active Work**: [from SESSION.md]
        - **Key Files**: [from SESSION.md]
        - **Last Compaction**: Cycle #[N]
        - **Status**: [from SESSION.md]
     
     I'm ready to continue. What would you like me to work on?
     ```

3. **If session DOES NOT EXIST**:
   - Create directory: `.context-harness/sessions/$ARGUMENTS/`
   - Create SESSION.md from template at `.context-harness/templates/session-template.md`
   - Initialize with session name "$ARGUMENTS"
   - Set `active_session = "$ARGUMENTS"`
   - Greet user as new session:
     ```
     👋 ContextHarness Primary Agent Activated
     
     ✓ New session created: $ARGUMENTS
     ✓ SESSION.md initialized
     ✓ Subagents standing by:
       - @research-subagent (Research & best practices)
       - @docs-subagent (Documentation research)
       - @compaction-guide (Context preservation)
     
     Session path: .context-harness/sessions/$ARGUMENTS/SESSION.md
     
     What would you like me to work on?
     ```

4. **Initialize interaction counter**: `user_interaction_count = 0`
