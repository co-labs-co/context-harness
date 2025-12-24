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
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  PHASE 4: @baseline-skills          │
│  Identify skill opportunities       │
│  → skeleton skills in .opencode/    │
└─────────────────────────────────────┘
```

### Execution Steps

1. **Announce Start**:
   ```
   🔍 Starting baseline analysis...
   
   This will analyze your project and generate PROJECT-CONTEXT.md
   Phases: Discovery → Questions → Answers → Skills
   
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

5. **Phase 4: Skills** (unless `--skip-skills` flag)
   - Invoke `@baseline-skills` subagent via Task tool
   - Prompt: Include the `discovery_report` JSON
   - Request: "Analyze skill opportunities and generate skeleton SKILL.md content for recommended skills."
   - Store result as `skill_skeletons`
   - For each skeleton skill:
     - Create directory `.opencode/skill/{skill-name}/`
     - Write SKILL.md from skeleton content
   - Display progress:
     ```
     ✅ Phase 4 Complete: Skills
        - Opportunities identified: [count]
        - Skills created: [count]
        - Location: .opencode/skill/
     ```

6. **Write Output**
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
     - Skills Created: [count] skeleton skills
     
     The PROJECT-CONTEXT.md file provides comprehensive context about this codebase.
     Share it with new team members or use it as a reference.
     
     Skills created in .opencode/skill/:
     - [skill-name-1] (skeleton - needs refinement)
     - [skill-name-2] (skeleton - needs refinement)
     
     To refine skills: /skill refine [name]
     To regenerate: /baseline
     ```

### Flags

Parse from $ARGUMENTS:

| Flag | Effect |
|------|--------|
| `--discovery-only` | Run only Phase 1, output discovery report |
| `--questions-only` | Run Phases 1-2, output questions (skip answers and skills) |
| `--skip-skills` | Run Phases 1-3, skip skill extraction |
| `--skills-only` | Run only Phase 4 with existing discovery report |
| `--output [path]` | Write to custom path instead of PROJECT-CONTEXT.md |
| `--json` | Output raw JSON instead of markdown |
| `--verbose` | Show detailed progress for each phase |

### Example Invocations

```
/baseline                           # Full analysis (all 4 phases)
/baseline --verbose                 # Full analysis with details
/baseline --discovery-only          # Just discovery phase
/baseline --skip-skills             # Generate PROJECT-CONTEXT.md without skills
/baseline --skills-only             # Only generate skills (uses cached discovery)
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

**Phase 4 Failure** (skill extraction):
```
⚠️ Skill extraction warning
   
   [error message]
   
   PROJECT-CONTEXT.md was generated successfully.
   Skills can be generated later with: /baseline --skills-only
```

**No Skills Identified**:
```
ℹ️ No skill opportunities identified
   
   No patterns in the codebase met the threshold for skill creation.
   This is normal for simple projects or highly unique codebases.
   
   You can manually create skills using the skill-creator skill.
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
