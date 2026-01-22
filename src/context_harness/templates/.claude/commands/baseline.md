---
description: Analyze project and generate PROJECT-CONTEXT.md with comprehensive codebase documentation
allowed-tools: Read, Write, Bash, Glob, Grep, Task
argument-hint: [--full]
---

Generate project baseline context.

## Instructions

Run a 3-phase analysis to generate PROJECT-CONTEXT.md:

### Phase 1: Discovery
Invoke @baseline-discovery to analyze:
- Directory structure
- Primary language and frameworks
- Build tools
- External dependencies

Output: `.context-harness/baseline/discovery-report.json`

### Phase 2: Question Generation
Invoke @baseline-questions to:
- Generate 30-50 analysis questions
- Score each question (relevance, validity, helpfulness)
- Filter to questions with score >= 8.0
- Minimum 30 validated questions required

Output: `.context-harness/baseline/validated-questions.json`

### Phase 3: Answer Generation
Invoke @baseline-answers to:
- Answer each validated question
- Search codebase for evidence
- Rate confidence (High/Medium/Low)

Output: `.context-harness/PROJECT-CONTEXT.md`

## Flags

- `--full`: Force full regeneration (ignore existing context)

## Output

```
Baseline analysis complete!

PROJECT-CONTEXT.md generated:
- Location: .context-harness/PROJECT-CONTEXT.md
- Questions answered: 34/36
- High confidence: 28
```
