---
description: Switch to or create a ContextHarness session with optional GitHub integration
allowed-tools: Read, Write, Edit, Bash, Glob
argument-hint: <session-name>
---

Switch to session: $ARGUMENTS

## Instructions

1. **Check if session exists**: Look for `.context-harness/sessions/$ARGUMENTS/SESSION.md`

2. **If session EXISTS**:
   - Read the SESSION.md file
   - Load the context (Active Work, Key Files, Decisions, Next Steps)
   - Greet user with session summary

3. **If session DOES NOT EXIST**:
   - Create directory: `.context-harness/sessions/$ARGUMENTS/`
   - Create SESSION.md from template
   - Check if in a git repo with GitHub remote
   - If yes, create a feature branch: `feature/$ARGUMENTS`
   - Greet user as new session

## Flags

- `--no-branch`: Skip branch creation
- `--no-issue`: Skip issue creation prompt
