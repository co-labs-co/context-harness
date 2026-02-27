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
ch init                    # or: context-harness init

# Open OpenCode and start working
/baseline              # Analyze project (first time)
/ctx my-feature        # Create session + branch
# ... do your work ...
/compact               # Save context
/pr                    # Create pull request
```

That's it. Your context persists across sessions.

> **Tip**: Use `ch` instead of `context-harness` for faster typing. Both commands work identically.

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
| `/baseline` | Analyze project and generate PROJECT-CONTEXT.md + AGENTS.md | `/baseline` |
| `/baseline --path` | Analyze specific directory (monorepo support) | `/baseline --path apps/frontend` |
| `/baseline --full` | Force full regeneration | `/baseline --full` |

#### Monorepo Support

For monorepos with multiple projects, use `--path` to generate project-specific context:

```bash
/baseline --path apps/frontend      # Generates apps/frontend/AGENTS.md
/baseline --path packages/shared    # Generates packages/shared/AGENTS.md
```

Each generated `AGENTS.md` is self-contained—AI agents read the nearest one in the directory tree.

---

## CLI Reference

> **Note**: Both `ch` and `context-harness` commands work identically. Use `ch` for convenience.

### Installation

```bash
# Install globally (recommended)
uv tool install "git+https://github.com/co-labs-co/context-harness.git"

# Or run without installing
uvx --from "git+https://github.com/co-labs-co/context-harness.git" ch init
```

### Core Commands

```bash
ch init                    # Initialize in current project
ch init --force            # Overwrite existing files
ch init --target ./path    # Install in specific directory
```

### MCP Configuration

```bash
ch mcp add context7        # Add Context7 for docs lookup
ch mcp add context7 -k KEY # With API key for higher limits
ch mcp list                # List configured MCP servers
```

### Skill Management

```bash
ch skill list              # List available skills
ch skill list --tags react # Filter by tag
ch skill list-local        # List installed skills
ch skill info <name>       # Show skill details
ch skill install           # Interactive picker (type to filter)
ch skill install <name>    # Install specific skill
ch skill extract           # Interactive picker for local skills
ch skill extract <name>    # Share a specific local skill
ch skill outdated          # Check for available upgrades
ch skill upgrade <name>    # Upgrade a single skill
ch skill upgrade --all     # Upgrade all outdated skills
ch skill init-repo <name>  # Create a skills registry repo on GitHub
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
ch config list                    # Show all configuration
ch config get skills-repo         # Get skills repository
ch config set skills-repo <repo>  # Set project-level skills repo
ch config set skills-repo <repo> --user  # Set user-level default
ch config unset skills-repo       # Remove project-level setting
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
ch config set skills-repo my-org/my-skills-repo
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
ch config set skills-repo my-fork/context-harness-skills --user
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
ch skill list  # Uses my-org/private-skills
```

### Creating a Custom Skills Repository

The fastest way to create a registry with automated versioning:

```bash
# Create a private registry (16 files scaffolded with CI/CD)
ch skill init-repo my-skills

# Create under an organization, public
ch skill init-repo my-org/team-skills --public

# Create and configure as your default in one step
ch skill init-repo my-skills --configure-user
```

The scaffold includes release-please for per-skill semantic versioning, PR validation workflows, and automatic `skills.json` updates. See [Skills Guide](https://co-labs-co.github.io/context-harness/user-guide/skills/) for the full workflow.

**Or create manually** with this structure:

1. Create a new repo with this structure:
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
   ---
   
   # My Skill
   
   Instructions for the AI agent...
   ```

4. Configure your repo:
   ```bash
   ch config set skills-repo my-org/my-skills-repo
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

## For LLM Agents

If you're an AI coding assistant (Claude Code or opencode) helping someone install ContextHarness, welcome!

**Quick Install** — Fetch and execute:
```bash
curl -fsSL https://raw.githubusercontent.com/co-labs-co/context-harness/main/docs/agent-install.md
```

**Or paste this prompt** into your LLM coding assistant:
```
Install context-harness for me by following the guide at:
https://raw.githubusercontent.com/co-labs-co/context-harness/main/docs/agent-install.md
```

The guide includes prerequisite checks, installation steps, verification, and troubleshooting.

---

## Contributing

Contributions welcome! See [DOCS.md](DOCS.md) for development details.

---

## License

[GNU AGPLv3](LICENSE)
