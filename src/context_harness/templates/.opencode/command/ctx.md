---
description: Switch to or create a ContextHarness session with optional GitHub integration
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
   
   **GitHub Integration (if available)**:
   - Check if in a git repo with GitHub remote
   - If yes, create a feature branch: `feature/$ARGUMENTS`
   - Add GitHub Integration section to SESSION.md:
     ```markdown
     ## GitHub Integration
     
     **Branch**: feature/$ARGUMENTS
     **Issue**: (none yet - describe your task and I'll create one)
     **PR**: (none yet)
     ```
   
   - Greet user as new session:
     ```
     👋 ContextHarness Primary Agent Activated
     
     ✓ New session created: $ARGUMENTS
     ✓ SESSION.md initialized
     ✓ Branch created: feature/$ARGUMENTS (if git repo)
     ✓ Subagents standing by:
       - @research-subagent (Research & best practices)
       - @docs-subagent (Documentation research)
       - @compaction-guide (Context preservation)
     
     Session path: .context-harness/sessions/$ARGUMENTS/SESSION.md
     
     Describe what you want to work on, and I'll create a GitHub issue 
     to track the context. Or say "skip issue" to work without GitHub integration.
     
     What would you like me to work on?
     ```

## GitHub Integration Behavior

When the user describes their task/feature:

1. **Gather context**:
   - User's description of the feature/bug
   - Relevant code files (use grep/glob to find them)
   - Documentation links (via @research-subagent if needed)

2. **Create GitHub issue** using `gh issue create`:
   - Title: Derived from user description
   - Body: Structured template with description, relevant files, and context

3. **Update SESSION.md** with issue link:
   ```markdown
   ## GitHub Integration
   
   **Branch**: feature/$ARGUMENTS
   **Issue**: #[number] - [url]
   **PR**: (none yet)
   ```

4. **Confirm to user**:
   ```
   ✅ GitHub Issue #[N] created: [title]
      [url]
   
   Ready to start implementing. What's the first step?
   ```

## Flags

- `--no-branch`: Skip branch creation
- `--no-issue`: Skip issue creation prompt

Parse these from $ARGUMENTS if present (e.g., `/ctx my-feature --no-branch`).
