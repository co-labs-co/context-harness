# Skills

Skills are pre-built patterns and workflows that extend the agent's capabilities.

## What are Skills?

Skills are markdown files with YAML frontmatter that provide specialized knowledge and step-by-step guidance for specific tasks. When you load a skill, the agent gains access to detailed instructions for that domain.

## Using Skills

### List Available Skills

```bash
# List all skills from the registry
ch skill list

# Filter by tag
ch skill list --tags react
ch skill list --tags python
```

### Install a Skill

```bash
# Interactive picker (recommended)
ch skill install

# Install specific skill
ch skill install react-forms
```

**Interactive picker:**

```
? Select a skill to install: (Use arrow keys, type to filter)
 » react-forms - React form handling with validation
   django-auth - Django authentication patterns
   fastapi-crud - FastAPI CRUD patterns
```

!!! info "Dual-Tool Installation"
    When both OpenCode and Claude Code are configured, skills are automatically installed to both tool directories.

### View Skill Details

```bash
ch skill info react-forms
```

### List Installed Skills

```bash
ch skill list-local
```

This command searches both `.opencode/skill/` and `.claude/skills/` directories.

## Skill Structure

Skills are stored in tool-specific directories:

=== "OpenCode"

    ```
    .opencode/skill/
    ├── react-forms/
    │   └── SKILL.md
    ├── fastapi-crud/
    │   └── SKILL.md
    └── my-custom-skill/
        └── SKILL.md
    ```

=== "Claude Code"

    ```
    .claude/skills/
    ├── react-forms/
    │   └── SKILL.md
    ├── fastapi-crud/
    │   └── SKILL.md
    └── my-custom-skill/
        └── SKILL.md
    ```

=== "Both Tools"

    When both tools are installed, skills exist in both locations:
    
    ```
    .opencode/skill/react-forms/SKILL.md
    .claude/skills/react-forms/SKILL.md
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

=== "OpenCode"

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

=== "Claude Code"

    Create `.claude/skills/my-skill/SKILL.md`:
    
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

!!! tip "Skill Content is Identical"
    The skill file content is the same for both tools—only the directory path differs.

### 2. Extract to Share

```bash
# Interactive picker
ch skill extract

# Or specify skill name
ch skill extract my-skill
```

This generates a JSON file you can submit to a skills repository.

## Custom Skills Repository

You can host your own skills registry instead of using the default `co-labs-co/context-harness-skills` repository. This is useful for organizations that want to share private skills across teams.

### Creating a Registry Repository

The fastest way to get started is with the `init-repo` command, which creates a properly scaffolded GitHub repository:

```bash
# Create a private registry under your personal account
ch skill init-repo my-skills

# Create under an organization
ch skill init-repo my-org/team-skills

# Create a public registry
ch skill init-repo my-org/team-skills --public

# Create and configure as your default in one step
ch skill init-repo my-skills --configure-user
```

!!! note "Prerequisite"
    The GitHub CLI (`gh`) must be installed and authenticated. Run `gh auth login` if you haven't already.

The command creates a repository with:

```
my-skills/
├── skills.json     # Empty registry: {"schema_version": "1.0", "skills": []}
├── skill/
│   └── .gitkeep    # Directory for skill files
└── README.md       # Usage instructions
```

Once created, you can start adding skills to the repository with `ch skill extract`.

**Auto-configuration options:**

| Flag | Effect |
|------|--------|
| `--configure-user` | Sets the new repo as your default `skills-repo` in `~/.context-harness/config.json` — applies to **all projects** on your machine |
| `--configure-project` | Sets the new repo as the project's `skills-repo` in `opencode.json` — applies to **this project only** |

If you don't use either flag, the command prints manual `config set` instructions for both scopes.

!!! tip "Which one should I use?"
    Use `--configure-user` if you want every project on your machine to pull skills from this registry by default. Use `--configure-project` if only the current project should use it. Project-level config takes precedence over user-level config (see [Configuration Precedence](#configuration-precedence) below).

### Configuration

=== "OpenCode"

    ```bash
    # Project-level (in opencode.json)
    ch config set skills-repo my-org/my-skills-repo
    
    # User-level (in ~/.context-harness/config.json)
    ch config set skills-repo my-org/my-skills-repo --user
    
    # Environment variable
    export CONTEXT_HARNESS_SKILLS_REPO=my-org/private-skills
    ```

=== "Claude Code"

    ```bash
    # Project-level (in .claude/settings.json)
    ch config set skills-repo my-org/my-skills-repo
    
    # User-level (in ~/.context-harness/config.json)
    ch config set skills-repo my-org/my-skills-repo --user
    
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

## Keeping Skills Up to Date

### Check for Updates

See which of your installed skills have newer versions available:

```bash
ch skill outdated
```

**Example output:**

```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Skill           ┃ Installed     ┃ Latest        ┃ Status              ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ react-forms     │ 0.1.0         │ 0.2.0         │ upgrade available   │
│ fastapi-crud    │ 1.0.0         │ 1.0.0         │ up to date          │
└─────────────────┴───────────────┴───────────────┴─────────────────────┘
```

### Upgrade Skills

```bash
# Upgrade a single skill
ch skill upgrade react-forms

# Upgrade all outdated skills at once
ch skill upgrade --all
```

### Compatibility

Skills can declare a minimum ContextHarness version they require via `min_context_harness_version` in their metadata. If your installed version is too old, the upgrade is blocked:

```
❌ react-forms requires context-harness >= 4.0.0 (you have 3.9.0)
   Run: pipx upgrade context-harness
   Or use --force to skip this check
```

Use `--force` to bypass the check if needed:

```bash
ch skill upgrade react-forms --force
```

## Configuration Precedence

Skills repository is resolved in this order:

| Priority | Source | Location |
|----------|--------|----------|
| 1 (Highest) | Environment Variable | `CONTEXT_HARNESS_SKILLS_REPO` |
| 2 | Project Config | `opencode.json` → `skillsRegistry.default` |
| 3 | User Config | `~/.context-harness/config.json` |
| 4 (Lowest) | Default | Official skills repository |
