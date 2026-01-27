---
name: skill-creator
description: Guide for creating effective skills that extend Claude's capabilities with specialized knowledge, workflows, or tool integrations. Use when creating new skills or updating existing ones.
---

# Skill Creator

This skill provides guidance for creating effective skills.

## About Skills

Skills are modular, self-contained packages that extend Claude's capabilities by providing specialized knowledge, workflows, and tools.

### What Skills Provide

1. Specialized workflows - Multi-step procedures for specific domains
2. Tool integrations - Instructions for working with specific file formats or APIs
3. Domain expertise - Company-specific knowledge, schemas, business logic
4. Bundled resources - Scripts, references, and assets for complex tasks

## Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/          - Executable code
    ├── references/       - Documentation for context
    └── assets/           - Templates, images, etc.
```

## Skill Creation Process

1. **Understand** the skill with concrete examples
2. **Plan** reusable contents (scripts, references, assets)
3. **Initialize** the skill directory
4. **Edit** SKILL.md with proper frontmatter and instructions
5. **Test** the skill in real usage
6. **Iterate** based on feedback

## SKILL.md Guidelines

### Frontmatter

```yaml
---
name: my-skill
description: What this skill does and when to use it. Include triggers.
---
```

### Body

- Keep under 500 lines
- Use imperative form
- Include code examples
- Reference bundled resources clearly

## Progressive Disclosure

- **Metadata** (~100 words) - Always in context
- **SKILL.md body** (<5k words) - When skill triggers
- **Bundled resources** - As needed by Claude

Keep SKILL.md lean. Move detailed information to `references/` files.
