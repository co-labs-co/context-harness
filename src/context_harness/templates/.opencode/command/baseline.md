---
description: Generate comprehensive PROJECT-CONTEXT.md through 3-phase analysis
agent: context-harness
---

Run baseline project analysis: $ARGUMENTS

## Instructions

Execute the 3-phase baseline analysis pipeline to generate `PROJECT-CONTEXT.md`:

### Phase Overview

```
┌─────────────────────────────────────┐
│  PHASE 1: @baseline-discovery       │
│  Analyze project structure          │
│  → discovery-report.json            │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  PHASE 2: @baseline-questions       │
│  Generate & validate questions      │
│  → validated-questions.json         │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  PHASE 3: @baseline-answers         │
│  Answer questions with evidence     │
│  → PROJECT-CONTEXT.md               │
└─────────────────────────────────────┘
```

### Execution Steps

1. **Announce Start**:
   ```
   🔍 Starting baseline analysis...
   
   This will analyze your project and generate PROJECT-CONTEXT.md
   Phases: Discovery → Questions → Answers
   
   Estimated time: 2-5 minutes depending on project size
   ```

2. **Phase 1: Discovery**
   - Invoke `@baseline-discovery` subagent via Task tool
   - Prompt: "Analyze this project and generate a comprehensive discovery report. Return JSON."
   - Store result as `discovery_report`
   - Display progress:
     ```
     ✅ Phase 1 Complete: Discovery
        - Languages: [detected languages]
        - Framework: [detected framework]
        - Files analyzed: [count]
     ```

3. **Phase 2: Questions**
   - Invoke `@baseline-questions` subagent via Task tool
   - Prompt: Include the `discovery_report` JSON
   - Request: "Generate and validate questions based on this discovery report. Return JSON with validated questions."
   - Store result as `validated_questions`
   - Display progress:
     ```
     ✅ Phase 2 Complete: Questions
        - Generated: [count] questions
        - Validated: [count] questions (score >= 8.0)
        - Categories covered: [list]
     ```

4. **Phase 3: Answers**
   - Invoke `@baseline-answers` subagent via Task tool
   - Prompt: Include the `validated_questions` JSON
   - Request: "Answer these validated questions with evidence citations and generate PROJECT-CONTEXT.md content."
   - Store result as `project_context_content`
   - Display progress:
     ```
     ✅ Phase 3 Complete: Answers
        - Questions answered: [count]
        - High confidence: [count]
        - Medium confidence: [count]
        - Unanswered: [count]
     ```

5. **Write Output**
   - Write `project_context_content` to `PROJECT-CONTEXT.md` in project root
   - Display completion:
     ```
     ✅ Baseline Analysis Complete!
     
     📄 Generated: PROJECT-CONTEXT.md
     
     Summary:
     - Project: [name]
     - Primary Language: [language]
     - Framework: [framework]
     - Questions Answered: [count]/[total]
     
     The PROJECT-CONTEXT.md file provides comprehensive context about this codebase.
     Share it with new team members or use it as a reference.
     
     To regenerate: /baseline
     ```

### Flags

Parse from $ARGUMENTS:

| Flag | Effect |
|------|--------|
| `--discovery-only` | Run only Phase 1, output discovery report |
| `--questions-only` | Run Phases 1-2, output questions (skip answers) |
| `--output [path]` | Write to custom path instead of PROJECT-CONTEXT.md |
| `--json` | Output raw JSON instead of markdown |
| `--verbose` | Show detailed progress for each phase |

### Example Invocations

```
/baseline                           # Full analysis
/baseline --verbose                 # Full analysis with details
/baseline --discovery-only          # Just discovery phase
/baseline --output docs/CONTEXT.md  # Custom output location
```

### Error Handling

**Phase 1 Failure**:
```
❌ Discovery failed: [error]
   
   Possible causes:
   - Empty directory
   - No recognizable project files
   
   Try running from project root directory.
```

**Phase 2 Failure** (not enough valid questions):
```
⚠️ Question validation warning
   
   Only [N] questions met quality threshold.
   Proceeding with available questions.
   
   Consider:
   - Adding more documentation to your project
   - Running /baseline again after code changes
```

**Phase 3 Failure**:
```
❌ Answer generation failed: [error]
   
   Discovery and questions are cached.
   Fix the issue and run: /baseline --skip-discovery
```

### Caching (Future Enhancement)

For projects that haven't changed:
- Cache discovery report with file hash
- Skip Phase 1 if no files changed
- Flag: `--force` to ignore cache

### Integration with ContextHarness Sessions

If running within an active session:
1. Add PROJECT-CONTEXT.md to session's Key Files
2. Reference in Documentation References
3. Note in SESSION.md:
   ```markdown
   ## Notes
   
   PROJECT-CONTEXT.md generated via /baseline on [date]
   ```
