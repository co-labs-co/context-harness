---
description: Generate comprehensive PROJECT-CONTEXT.md and AGENTS.md through 5-phase analysis with parallel question answering, skill extraction, and agent instructions
agent: context-harness
---

Run baseline project analysis: $ARGUMENTS

## Instructions

Execute the 5-phase baseline analysis pipeline to generate `PROJECT-CONTEXT.md` and `AGENTS.md`.

### Monorepo Support

The baseline command supports **directory-scoped analysis** for monorepos. Use the `--path` flag to target a specific project within a monorepo:

```bash
# Analyze specific project in monorepo
/baseline --path apps/frontend

# Output files are placed in the target directory:
# - apps/frontend/PROJECT-CONTEXT.md
# - apps/frontend/AGENTS.md
```

**How it works**:
- Discovery phase analyzes only the target directory
- Output files are generated relative to the target directory
- The generated AGENTS.md is **self-contained** (no inheritance from root)
- All other flags work normally with `--path`

**AGENTS.md Precedence** (per [agents.md](https://agents.md/) standard):
> "For large monorepos, use nested AGENTS.md files for subprojects. Agents automatically read the nearest file in the directory tree."

When editing a file, AI agents traverse UP the directory tree and use the CLOSEST `AGENTS.md` found. No merging occurs - the nearest file wins entirely.

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
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: PARALLEL ANSWER PROCESSING                        │
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Q001        │ │ Q002        │ │ Q003        │  ...      │
│  │ @baseline-  │ │ @baseline-  │ │ @baseline-  │           │
│  │ question-   │ │ question-   │ │ question-   │           │
│  │ answer      │ │ answer      │ │ answer      │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │                   │
│         └───────────────┼───────────────┘                   │
│                         ▼                                   │
│              ┌─────────────────────┐                        │
│              │ @baseline-answers   │                        │
│              │ (Coordinator)       │                        │
│              └─────────────────────┘                        │
│                         │                                   │
│                         ▼                                   │
│              PROJECT-CONTEXT.md                             │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: PARALLEL SKILL EXTRACTION                         │
│                                                              │
│  @baseline-skills (mode: identify)                          │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ S001        │ │ S002        │ │ S003        │  ...      │
│  │ @baseline-  │ │ @baseline-  │ │ @baseline-  │           │
│  │ skill-      │ │ skill-      │ │ skill-      │           │
│  │ answer      │ │ answer      │ │ answer      │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │                   │
│         └───────────────┼───────────────┘                   │
│                         ▼                                   │
│              ┌─────────────────────┐                        │
│              │ @baseline-skills    │                        │
│              │ (mode: aggregate)   │                        │
│              └─────────────────────┘                        │
│                         │                                   │
│                         ▼                                   │
│              skeleton skills in .opencode/skill/            │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: AGENTS.MD GENERATION                              │
│                                                              │
│              ┌─────────────────────┐                        │
│              │ @baseline-agents    │                        │
│              └─────────────────────┘                        │
│                         │                                   │
│                         ▼                                   │
│              AGENTS.md (OpenCode rules file)                │
└─────────────────────────────────────────────────────────────┘
```

### Execution Steps

0. **Parse Arguments and Resolve Target Path**:
   ```
   IF --path flag provided:
     target_dir = resolve(cwd + path_argument)
     IF not exists(target_dir) OR not is_directory(target_dir):
       ERROR: "Path does not exist or is not a directory: {path}"
     
     Display:
     📂 Target directory: {target_dir}
        (Running baseline for subdirectory, not repository root)
   ELSE:
     target_dir = cwd
   
   # All output paths are relative to target_dir:
   # - {target_dir}/PROJECT-CONTEXT.md
   # - {target_dir}/AGENTS.md
   # - {target_dir}/.context-harness/baseline/
   # - {target_dir}/.opencode/skill/ (if skills generated)
   ```

1. **Announce Start**:
   ```
   🔍 Starting baseline analysis...
   
   This will analyze your project and generate PROJECT-CONTEXT.md + AGENTS.md
   Phases: Discovery → Questions → Parallel Answers → Parallel Skills → AGENTS.md
   
   Estimated time: 2-5 minutes depending on project size
   ```
   
   If `--path` was provided, also show:
   ```
   📂 Target: {target_dir}
      Outputs will be placed in this directory.
   ```

2. **Phase 1: Discovery**
   - Invoke `@baseline-discovery` subagent via Task tool
   - Prompt: "Analyze the project at {target_dir} and generate a comprehensive discovery report. Return JSON."
   - **Important**: Pass `target_directory: "{target_dir}"` to the subagent so it knows to analyze only that directory
   - Store result as `discovery_report`
   - Display progress:
     ```
     ✅ Phase 1 Complete: Discovery
        - Target: {target_dir}
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

4. **Phase 3: Parallel Answer Processing**
   
   This phase uses a three-step approach:
   
   **Step 3a: Dispatch Questions in Parallel Batches**
   
   ```
   For each question in validated_questions:
     - Create a Task invocation for @baseline-question-answer
     - Include:
       - question_id
       - category  
       - question text
       - expected_evidence_locations
       - discovery_context (condensed project info)
   
   Batch size: 5-10 concurrent questions
   ```
   
   Example parallel invocation:
   ```
   // Invoke multiple @baseline-question-answer subagents in parallel
   Task(@baseline-question-answer, {
     question_id: "Q001",
     category: "architecture_decisions",
     question: "Why was PostgreSQL chosen?",
     expected_evidence_locations: ["README.md", "config/"],
     discovery_context: { project_name: "...", primary_language: "...", ... }
   })
   
   Task(@baseline-question-answer, {
     question_id: "Q002",
     ...
   })
   ```
   
   Display progress:
   ```
   ⏳ Phase 3a: Answering questions in parallel...
      - Questions dispatched: [count]
      - Batch size: [N] concurrent workers
      - Processing...
   ```
   
   **Step 3b: Collect and Track Answers**
   
   ```
   As each @baseline-question-answer completes:
     - Collect the JSON answer
     - Track completion count
     - Handle any failures (mark as unanswered)
   
   Store all answers in `answered_questions` array
   ```
   
   **Step 3c: Aggregate with Coordinator**
   
   - Invoke `@baseline-answers` (coordinator) subagent via Task tool
   - Prompt: Include:
     - `discovery_report` JSON
     - `validated_questions` JSON
     - `answered_questions` array (all JSON answers from workers)
   - Request: "Aggregate these answered questions into PROJECT-CONTEXT.md format."
   - Store result as `project_context_content`
   
   Display progress:
   ```
   ✅ Phase 3 Complete: Parallel Answers
      - Questions processed: [count]
      - Workers used: [count] parallel
      - High confidence: [count]
      - Medium confidence: [count]
      - Unanswered: [count]
   ```

5. **Phase 4: Parallel Skill Extraction** (unless `--skip-skills` flag)
   
   This phase uses a three-step approach similar to Phase 3:
   
   **Step 4a: Identify Skill Opportunities**
   
   - Invoke `@baseline-skills` (coordinator, mode: identify) via Task tool
   - Prompt: Include `discovery_report` JSON with `mode: "identify"`
   - Request: "Identify skill opportunities in this codebase. Return JSON with opportunities."
   - Store result as `skill_opportunities`
   
   Display progress:
   ```
   ⏳ Phase 4a: Identifying skill opportunities...
      - Scanning codebase patterns...
   ```
   
   **Step 4b: Dispatch Skills in Parallel**
   
   ```
   For each opportunity in skill_opportunities:
     - Create a Task invocation for @baseline-skill-answer
     - Include:
       - skill_id
       - skill_name
       - category
       - initial_patterns (hints)
       - discovery_context (condensed project info)
   
   Batch size: 5 concurrent (skills are more complex)
   ```
   
   Example parallel invocation:
   ```
   // Invoke multiple @baseline-skill-answer subagents in parallel
   Task(@baseline-skill-answer, {
     skill_id: "S001",
     skill_name: "api-integration",
     category: "external_integrations",
     initial_patterns: ["src/services/*.ts"],
     discovery_context: { project_name: "...", ... }
   })
   
   Task(@baseline-skill-answer, {
     skill_id: "S002",
     ...
   })
   ```
   
   Display progress:
   ```
   ⏳ Phase 4b: Analyzing skills in parallel...
      - Opportunities dispatched: [count]
      - Batch size: [N] concurrent workers
      - Processing...
   ```
   
   **Step 4c: Aggregate and Filter Skills**
   
   - Invoke `@baseline-skills` (coordinator, mode: aggregate) via Task tool
   - Prompt: Include:
     - `discovery_report` JSON
     - `skill_opportunities` JSON
     - `analyzed_skills` array (all JSON from workers)
   - Request: "Aggregate analyzed skills, filter by score >= 6.0, and generate final report."
   - Store result as `skill_skeletons`
   
   **Step 4d: Create Skill Files**
   
   For each recommended skeleton skill:
   - Create directory `.opencode/skill/{skill-name}/`
   - Write SKILL.md from skeleton content
   
   Display progress:
   ```
   ✅ Phase 4 Complete: Parallel Skills
      - Opportunities analyzed: [count]
      - Workers used: [count] parallel
      - Skills created: [count] (score >= 6.0)
      - Skipped: [count] (below threshold)
      - Location: .opencode/skill/
   ```

6. **Phase 5: AGENTS.md Generation** (unless `--skip-agents` flag)
   
   This phase generates the `AGENTS.md` file following the [OpenCode specification](https://opencode.ai/docs/rules/).
   
   **Step 5a: Gather Inputs**
   
   ```
   Collect from previous phases:
   - PROJECT-CONTEXT.md content (from Phase 3)
   - Skill metadata from .opencode/skill/ (from Phase 4)
   - discovery_report (from Phase 1)
   - Existing AGENTS.md (if present, for update mode)
   ```
   
   **Step 5b: Invoke @baseline-agents**
   
   - Invoke `@baseline-agents` subagent via Task tool
   - Prompt: Include:
     - `project_context` (PROJECT-CONTEXT.md content)
     - `skills` array (metadata for each skill created)
     - `discovery_report` JSON
     - `existing_agents_md` (if file exists)
   - Request: "Generate AGENTS.md content following OpenCode specification."
   - Store result as `agents_md_content`
   
   Example invocation:
   ```
   Task(@baseline-agents, {
     project_context: {
       content: "...",  // Full PROJECT-CONTEXT.md
       path: "PROJECT-CONTEXT.md"
     },
     skills: [
       {
         name: "python-result-pattern",
         path: ".opencode/skill/python-result-pattern/SKILL.md",
         description: "Result[T] pattern for error handling",
         triggers: ["error handling", "Result pattern"]
       },
       ...
     ],
     discovery_report: {...},
     existing_agents_md: null  // or existing content
   })
   ```
   
   **Step 5c: Write AGENTS.md**
   
   - Write `agents_md_content` to `AGENTS.md` in **target directory** (not necessarily project root)
   - Path: `{target_dir}/AGENTS.md`
   - If file exists and `--agents-update` flag, merge with existing content
   - **For nested directories**: The AGENTS.md is self-contained and does NOT inherit from root
   
   Display progress:
   ```
   ✅ Phase 5 Complete: AGENTS.md
      - Generated: {target_dir}/AGENTS.md
      - Skills referenced: [count]
      - Mode: [create/update]
   ```

7. **Write Output**
   - Write `project_context_content` to `{target_dir}/PROJECT-CONTEXT.md` (if not already written)
   - Write `agents_md_content` to `{target_dir}/AGENTS.md` (if Phase 5 ran)
   - Display completion:
     ```
     ✅ Baseline Analysis Complete!
     
     📄 Generated Files:
        - {target_dir}/PROJECT-CONTEXT.md (comprehensive project context)
        - {target_dir}/AGENTS.md (OpenCode rules for AI agents)
     
     Summary:
     - Project: [name]
     - Target Directory: {target_dir}
     - Primary Language: [language]
     - Framework: [framework]
     - Questions Answered: [count]/[total]
     - Processing Mode: Parallel
     - Skills Created: [count] skeleton skills
     - Skills Referenced in AGENTS.md: [count]
     
     The PROJECT-CONTEXT.md file provides comprehensive context about this codebase.
     The AGENTS.md file provides rules and instructions for AI agents working with this repo.
     
     Skills created in .opencode/skill/:
     - [skill-name-1] (skeleton - needs refinement)
     - [skill-name-2] (skeleton - needs refinement)
     
     Next steps:
     - Review AGENTS.md and customize as needed
     - Commit both files to Git for team sharing
     - To refine skills: /skill refine [name]
     - To regenerate: /baseline
     ```

### Parallel Processing Configuration

**Phase 3 (Questions):**

| Project Size | Question Count | Batch Size | Strategy |
|--------------|----------------|------------|----------|
| Small | < 15 questions | All at once | Single batch |
| Medium | 15-30 questions | 10 concurrent | 2-3 batches |
| Large | 30-50 questions | 10 concurrent | 4-5 batches |

**Phase 4 (Skills):**

| Project Size | Opportunity Count | Batch Size | Strategy |
|--------------|-------------------|------------|----------|
| Small | < 5 opportunities | All at once | Single batch |
| Medium | 5-10 opportunities | 5 concurrent | 1-2 batches |
| Large | 10+ opportunities | 5 concurrent | Multiple batches |

**Batching Logic:**
```
// Phase 3: Questions
if question_count <= 15:
    question_batch_size = question_count
else:
    question_batch_size = 10  # Max 10 concurrent

// Phase 4: Skills
if opportunity_count <= 5:
    skill_batch_size = opportunity_count
else:
    skill_batch_size = 5  # Max 5 concurrent (skills are more complex)
```

### Error Handling for Parallel Phases

**Individual Worker Failure:**
```
If a worker (@baseline-question-answer or @baseline-skill-answer) fails:
1. Log the failure with ID
2. Mark as unanswered/not_recommended with reason "Worker failed"
3. Continue processing other items
4. Include in final report
```

**Batch Timeout:**
```
If a batch takes > 2 minutes:
1. Collect completed results
2. Mark remaining as "timeout"
3. Proceed with what we have
```

**All Workers Fail:**
```
❌ Phase [3|4] failed: No results received

All workers failed to respond.
Previous phases cached.
Try again with appropriate skip flags.
```

### Flags

Parse from $ARGUMENTS:

| Flag | Effect |
|------|--------|
| `--path [dir]` | **Target directory for analysis** (default: current directory). Outputs are placed in this directory. |
| `--discovery-only` | Run only Phase 1, output discovery report |
| `--questions-only` | Run Phases 1-2, output questions (skip answers, skills, and agents) |
| `--skip-skills` | Run Phases 1-3 and 5, skip skill extraction |
| `--skip-agents` | Run Phases 1-4, skip AGENTS.md generation |
| `--skills-only` | Run only Phase 4 with existing discovery report |
| `--agents-only` | Run only Phase 5 with existing PROJECT-CONTEXT.md and skills |
| `--agents-update` | Update existing AGENTS.md instead of overwriting |
| `--output [path]` | Write to custom path instead of PROJECT-CONTEXT.md |
| `--agents-output [path]` | Write AGENTS.md to custom path |
| `--json` | Output raw JSON instead of markdown |
| `--verbose` | Show detailed progress for each phase |
| `--sequential` | Disable parallel processing (legacy mode for ALL phases) |
| `--batch-size [N]` | Override automatic batch size for questions (max 10) |
| `--skill-batch-size [N]` | Override automatic batch size for skills (max 5) |
| `--skill-threshold [N]` | Override skill score threshold (default 6.0) |

**Path Resolution**:
- `--path` is resolved relative to the current working directory
- If the path doesn't exist or is not a directory, an error is returned
- All output paths (PROJECT-CONTEXT.md, AGENTS.md, .context-harness/) are relative to `--path`

### Example Invocations

```
/baseline                           # Full analysis: PROJECT-CONTEXT.md + skills + AGENTS.md
/baseline --path apps/frontend      # Analyze specific directory (monorepo support)
/baseline --path packages/shared    # Analyze shared package in monorepo
/baseline --verbose                 # Full analysis with detailed progress
/baseline --discovery-only          # Just discovery phase
/baseline --skip-skills             # Generate PROJECT-CONTEXT.md + AGENTS.md without skills
/baseline --skip-agents             # Generate PROJECT-CONTEXT.md + skills without AGENTS.md
/baseline --skills-only             # Only generate skills (uses cached discovery)
/baseline --agents-only             # Only generate AGENTS.md (uses existing context + skills)
/baseline --agents-update           # Update existing AGENTS.md with new context
/baseline --output docs/CONTEXT.md  # Custom output location for PROJECT-CONTEXT.md
/baseline --agents-output docs/AGENTS.md  # Custom output location for AGENTS.md
/baseline --sequential              # Use legacy sequential mode for all phases
/baseline --batch-size 5            # Use smaller batches for questions
/baseline --skill-batch-size 3      # Use smaller batches for skills
/baseline --skill-threshold 5.0     # Lower threshold for skill creation

# Combining flags with --path
/baseline --path apps/api --skip-skills --verbose
/baseline --path packages/ui --agents-only
```

### Legacy Sequential Mode

If `--sequential` flag is passed, use the original single-worker approach for ALL phases:
- Phase 3: Invoke `@baseline-answers` with all questions (answers them sequentially)
- Phase 4: Invoke `@baseline-skills` in single-worker mode
- Slower but uses less parallel resources

```
⚠️ Using legacy sequential mode (--sequential flag)
   This may take longer for large projects.
```

### Error Handling

**Invalid --path Argument**:
```
❌ Invalid path: [path]
   
   The specified path does not exist or is not a directory.
   
   Usage:
   /baseline --path <directory>
   
   Examples:
   /baseline --path apps/frontend
   /baseline --path packages/shared
```

**Path Outside Repository**:
```
⚠️ Warning: Path is outside the git repository
   
   The specified directory is outside the current git repository.
   Some features may not work correctly (e.g., git-based analysis).
   
   Proceeding with limited context...
```

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
   Fix the issue and run: /baseline --skip-discovery --skip-questions
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
   
   You can manually create skills or lower threshold with --skill-threshold 5.0
```

**Phase 5 Failure** (AGENTS.md generation):
```
⚠️ AGENTS.md generation warning
   
   [error message]
   
   PROJECT-CONTEXT.md and skills were generated successfully.
   AGENTS.md can be generated later with: /baseline --agents-only
```

**No PROJECT-CONTEXT.md for --agents-only**:
```
❌ Cannot generate AGENTS.md: PROJECT-CONTEXT.md not found
   
   Run /baseline first to generate PROJECT-CONTEXT.md,
   or run /baseline without --agents-only flag.
```

### Caching (Future Enhancement)

For projects that haven't changed:
- Cache discovery report with file hash
- Skip Phase 1 if no files changed
- Flag: `--force` to ignore cache

### Integration with ContextHarness Sessions

If running within an active session:
1. Add PROJECT-CONTEXT.md to session's Key Files
2. Add AGENTS.md to session's Key Files
3. Reference in Documentation References
4. Note in SESSION.md:
   ```markdown
   ## Notes
   
   PROJECT-CONTEXT.md generated via /baseline on [date]
   AGENTS.md generated via /baseline on [date]
   Processing mode: Parallel (questions: [N] workers, skills: [M] workers)
   ```

### AGENTS.md Best Practices

The generated AGENTS.md follows the [OpenCode specification](https://opencode.ai/docs/rules/):

1. **Commit to Git** - Share with your team
2. **Customize** - Add project-specific rules after generation
3. **Lazy Loading** - Skills are referenced with `@path/to/skill.md` syntax
4. **Precedence** - Local AGENTS.md combines with global `~/.config/opencode/AGENTS.md`
5. **External Files** - Can reference other files via `opencode.json` instructions field
