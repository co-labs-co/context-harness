# ContextHarness

> Context-aware agent framework for [OpenCode.ai](https://opencode.ai) that maintains session continuity.

## Requirements

**Required:**
- [OpenCode.ai](https://opencode.ai) — AI coding assistant (ContextHarness is a framework for this)
- [uv](https://docs.astral.sh/uv/) — Python package installer

**Optional:**
- [GitHub CLI](https://cli.github.com/) `gh` — For `/issue`, `/pr` commands
- [Context7 MCP](https://context7.com/) — For research features via `@research-subagent`

---

## Quickstart

```bash
# Install (one-time)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Initialize in your project
context-harness init

# Open OpenCode and start working
/baseline              # Analyze project (first time)
/ctx my-feature        # Create session + branch
# ... do your work ...
/compact               # Save context
/pr                    # Create pull request
```

That's it. Your context persists across sessions.

---

## Commands Reference

### Session Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/ctx {name}` | Create or switch to a session (creates git branch) | `/ctx login-feature` |
| `/contexts` | List all sessions with status | `/contexts` |
| `/compact` | Save current context to SESSION.md | `/compact` |

### GitHub Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/issue` | Create GitHub issue from current context | `/issue` |
| `/issue update` | Add progress comment to linked issue | `/issue update` |
| `/pr` | Create pull request for current branch | `/pr` |

### Analysis Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/baseline` | Analyze project and generate PROJECT-CONTEXT.md | `/baseline` |
| `/baseline --full` | Force full regeneration | `/baseline --full` |

---

## CLI Reference

### Installation

```bash
# Install globally (recommended)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Or run without installing
uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init
```

### Core Commands

```bash
context-harness init                    # Initialize in current project
context-harness init --force            # Overwrite existing files
context-harness init --target ./path    # Install in specific directory
```

### MCP Configuration

```bash
context-harness mcp add context7        # Add Context7 for docs lookup
context-harness mcp add context7 -k KEY # With API key for higher limits
context-harness mcp list                # List configured MCP servers
```

### Skill Management

```bash
context-harness skill list              # List available skills
context-harness skill list --tags react # Filter by tag
context-harness skill list-local        # List installed skills
context-harness skill info <name>       # Show skill details
context-harness skill install           # Interactive picker (type to filter)
context-harness skill install <name>    # Install specific skill
context-harness skill extract           # Interactive picker for local skills
context-harness skill extract <name>    # Share a specific local skill
```

**Interactive skill selection**: Run `skill install` or `skill extract` without a name to get a fuzzy-searchable picker:

```
? Select a skill to install: (Use arrow keys, type to filter)
 » react-forms - React form handling with validation
   django-auth - Django authentication patterns
   fastapi-crud - FastAPI CRUD patterns
```

### Configuration Management

```bash
context-harness config list                    # Show all configuration
context-harness config get skills-repo         # Get skills repository
context-harness config set skills-repo <repo>  # Set project-level skills repo
context-harness config set skills-repo <repo> --user  # Set user-level default
context-harness config unset skills-repo       # Remove project-level setting
```

---

## How It Works

ContextHarness maintains a `SESSION.md` file for each feature/task you work on:

```
.context-harness/sessions/
├── login-feature/
│   └── SESSION.md          # Your context for this feature
├── TICKET-1234/
│   └── SESSION.md
└── api-refactor/
    └── SESSION.md
```

When you run `/compact`, your current work context is saved. When you switch sessions with `/ctx`, the previous context is preserved and the new session's context is loaded.

### Typical Workflow

```
/ctx login-feature          # Start new session, creates feature/login-feature branch
# ... work on login ...
/compact                    # Save progress
# ... more work ...
/issue                      # Create GitHub issue from context
# ... finish feature ...
/pr                         # Create pull request
```

### GitHub Integration

When `gh` CLI is available and authenticated:

- `/ctx {name}` creates a `feature/{name}` branch
- `/issue` creates a GitHub issue with full context
- `/issue update` posts progress comments
- `/pr` creates a PR linked to the issue

Graceful fallback: works locally without GitHub.

---

## Custom Skills Repository

You can configure a custom skills repository (e.g., your organization's private skills repo or a personal fork).

### Configuration Precedence

ContextHarness resolves the skills repository in this order:

| Priority | Source | Location | Use Case |
|----------|--------|----------|----------|
| 1 (Highest) | Environment Variable | `CONTEXT_HARNESS_SKILLS_REPO` | CI/CD, temporary overrides |
| 2 | Project Config | `opencode.json` → `skillsRegistry.default` | Per-project custom repo |
| 3 | User Config | `~/.context-harness/config.json` | Personal default |
| 4 (Lowest) | Default | Hardcoded | Official skills repository |

### Setting a Custom Skills Repository

You can specify the repository using either the short `owner/repo` format or the full GitHub URL:

```bash
# Short format
context-harness config set skills-repo my-org/my-skills-repo

# Full GitHub URL (automatically normalized to owner/repo)
context-harness config set skills-repo https://github.com/my-org/my-skills-repo
```

**Project-level** (for team/project-specific repos):
```bash
context-harness config set skills-repo my-org/my-skills-repo
```

This adds to your `opencode.json`:
```json
{
  "skillsRegistry": {
    "default": "my-org/my-skills-repo"
  }
}
```

**User-level** (personal default across all projects):
```bash
context-harness config set skills-repo my-fork/context-harness-skills --user
```

This creates/updates `~/.context-harness/config.json`:
```json
{
  "skillsRegistry": {
    "default": "my-fork/context-harness-skills"
  }
}
```

**Environment variable** (CI/CD or temporary override):
```bash
export CONTEXT_HARNESS_SKILLS_REPO=my-org/private-skills
context-harness skill list  # Uses my-org/private-skills
```

### Creating a Custom Skills Repository

To create your own skills repository:

1. Fork or create a new repo with this structure:
   ```
   my-skills-repo/
   ├── skills.json          # Registry of available skills
   └── skill/               # Directory containing skills
       ├── my-skill/
       │   └── SKILL.md     # Skill definition with YAML frontmatter
       └── another-skill/
           └── SKILL.md
   ```

2. Create `skills.json`:
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

3. Each skill needs a `SKILL.md` with frontmatter:
   ```markdown
   ---
   name: my-skill
   description: What this skill does
   version: 0.1.0
   ---
   
   # My Skill
   
   Instructions for the AI agent...
   ```

4. Configure your repo:
   ```bash
   context-harness config set skills-repo my-org/my-skills-repo
   ```

The official repository [`co-labs-co/context-harness-skills`](https://github.com/co-labs-co/context-harness-skills) serves as a reference implementation.

---

## Documentation

**Full documentation**: [co-labs-co.github.io/context-harness](https://co-labs-co.github.io/context-harness/)

See [DOCS.md](DOCS.md) for:

- Architecture and design
- SESSION.md structure
- Subagent reference
- Model configuration
- Customization guide
- Manual installation

---

## Contributing

Contributions welcome! See [DOCS.md](DOCS.md) for development details.

---

## License

[GNU AGPLv3](LICENSE)
