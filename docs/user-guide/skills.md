# Skills

Skills are pre-built patterns and workflows that extend the agent's capabilities.

## What are Skills?

Skills are markdown files with YAML frontmatter that provide specialized knowledge and step-by-step guidance for specific tasks. When you load a skill, the agent gains access to detailed instructions for that domain.

## Using Skills

### List Available Skills

```bash
# List all skills from the registry
context-harness skill list

# Filter by tag
context-harness skill list --tags react
context-harness skill list --tags python
```

### Install a Skill

```bash
# Interactive picker (recommended)
context-harness skill install

# Install specific skill
context-harness skill install react-forms
```

**Interactive picker:**

```
? Select a skill to install: (Use arrow keys, type to filter)
 » react-forms - React form handling with validation
   django-auth - Django authentication patterns
   fastapi-crud - FastAPI CRUD patterns
```

### View Skill Details

```bash
context-harness skill info react-forms
```

### List Installed Skills

```bash
context-harness skill list-local
```

## Skill Structure

Skills are stored in `.opencode/skill/`:

```
.opencode/skill/
├── react-forms/
│   └── SKILL.md
├── fastapi-crud/
│   └── SKILL.md
└── my-custom-skill/
    └── SKILL.md
```

Each skill has YAML frontmatter:

```markdown
---
name: react-forms
description: React form handling with validation
version: 0.1.0
tags:
  - react
  - forms
  - validation
---

# React Forms Skill

Instructions for the agent...
```

## Creating Custom Skills

### 1. Create the Skill File

Create `.opencode/skill/my-skill/SKILL.md`:

```markdown
---
name: my-skill
description: What this skill does
version: 0.1.0
tags:
  - category
---

# My Skill

## When to Use

Use this skill when...

## Instructions

1. Step one
2. Step two
3. Step three

## Examples

```python
# Example code
```
```

### 2. Extract to Share

```bash
# Interactive picker
context-harness skill extract

# Or specify skill name
context-harness skill extract my-skill
```

This generates a JSON file you can submit to a skills repository.

## Custom Skills Repository

You can configure a custom skills repository for your organization.

### Configuration

```bash
# Project-level (in opencode.json)
context-harness config set skills-repo my-org/my-skills-repo

# User-level (in ~/.context-harness/config.json)
context-harness config set skills-repo my-org/my-skills-repo --user

# Environment variable
export CONTEXT_HARNESS_SKILLS_REPO=my-org/private-skills
```

### Repository Structure

```
my-skills-repo/
├── skills.json          # Registry of available skills
└── skill/               # Directory containing skills
    ├── my-skill/
    │   └── SKILL.md
    └── another-skill/
        └── SKILL.md
```

### skills.json Format

```json
{
  "schema_version": "1.0",
  "skills": [
    {
      "name": "my-skill",
      "description": "What this skill does",
      "version": "0.1.0",
      "author": "your-username",
      "tags": ["category"],
      "path": "skill/my-skill"
    }
  ]
}
```

## Configuration Precedence

Skills repository is resolved in this order:

| Priority | Source | Location |
|----------|--------|----------|
| 1 (Highest) | Environment Variable | `CONTEXT_HARNESS_SKILLS_REPO` |
| 2 | Project Config | `opencode.json` → `skillsRegistry.default` |
| 3 | User Config | `~/.context-harness/config.json` |
| 4 (Lowest) | Default | Official skills repository |
