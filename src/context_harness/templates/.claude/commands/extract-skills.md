---
description: Extract skills from project patterns and create reusable skill definitions
allowed-tools: Read, Write, Glob, Grep
---

Extract project-specific skills from codebase patterns.

## Instructions

1. **Analyze codebase** for recurring patterns:
   - Code patterns and conventions
   - Architecture decisions
   - Testing approaches
   - Build and deployment patterns

2. **Identify skill candidates**:
   - Patterns used in 3+ places
   - Complex workflows that need documentation
   - Domain-specific knowledge

3. **Generate skill definitions**:
   - Create SKILL.md with proper frontmatter
   - Include code examples from actual codebase
   - Reference relevant files

4. **Save to skills directory**:
   - `.claude/skills/[skill-name]/SKILL.md`

## Output

```
Skills extracted:

1. [skill-name]
   - Pattern: [what it captures]
   - Files: [relevant source files]
   - Location: .claude/skills/[skill-name]/SKILL.md

2. [skill-name]
   ...
```
