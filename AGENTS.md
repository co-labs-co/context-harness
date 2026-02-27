# context-harness

A CLI installer for the ContextHarness agent framework that solves context loss in long AI-assisted development sessions through user-driven context preservation via named sessions and incremental compaction cycles.

## Project Overview

ContextHarness provides tools for AI agents to maintain context continuity across conversations. It generates SESSION.md files that preserve decisions, file changes, and next steps between sessions. The framework uses a "single executor pattern" where one primary agent handles all execution while specialized subagents provide advisory guidance only.

Key capabilities:
- **Session Management**: `/ctx`, `/contexts`, `/compact` commands for context preservation
- **GitHub Integration**: `/issue`, `/pr` commands for repository operations
- **Baseline Analysis**: `/baseline` command with 5-phase subagent pipeline for PROJECT-CONTEXT.md generation
- **Skill Management**: `skill list`, `skill install`, `skill outdated`, `skill upgrade`, `skill init-repo` for managing and distributing reusable agent skills

## Project Structure

```
context-harness/
├── src/context_harness/        # Python source code
│   ├── primitives/             # Domain models (dataclasses, enums)
│   │   ├── __init__.py         # Re-exports all primitives
│   │   ├── base.py             # Result[T] = Success | Failure, ErrorCode
│   │   ├── config.py           # Configuration primitives
│   │   ├── installer.py        # InstallResult enum
│   │   ├── mcp.py              # MCP server primitives
│   │   ├── skill.py            # Skill, VersionComparison, RegistryRepo
│   │   └── tool.py             # ToolType, ToolDetector, ToolTarget
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── config_service.py   # Configuration management
│   │   └── skill_service.py    # Skill operations (install, upgrade, init-repo)
│   ├── interfaces/             # CLI/SDK entry points
│   │   └── cli/
│   │       ├── __init__.py
│   │       ├── skill_cmd.py    # Click commands for skill management
│   │       └── config_cmd.py   # Click commands for configuration
│   ├── templates/              # Bundled framework templates
│   │   ├── .context-harness/   # Session management files
│   │   └── .opencode/          # Agent and command definitions
│   ├── cli.py                  # Click CLI entry point (registers groups)
│   ├── installer.py            # Framework installation logic
│   └── mcp_config.py           # MCP server configuration
├── tests/                      # pytest test suite
│   └── unit/
│       ├── services/           # Service unit tests
│       └── interfaces/cli/     # CLI integration tests
├── .github/workflows/          # CI/CD workflows
├── .opencode/                  # Agent definitions for this repo
│   ├── agent/                  # Subagent specifications
│   ├── command/                # Command definitions
│   └── skill/                  # Project skills (15 total)
└── pyproject.toml              # Project configuration
```

## Technology Stack

- **Language**: Python 3.9+
- **CLI Framework**: Click with Rich output formatting
- **Build Backend**: Hatchling with hatch-vcs (git tag versioning)
- **Package Manager**: uv
- **Test Framework**: pytest with Click's CliRunner
- **CI/CD**: GitHub Actions + semantic-release (Node.js)
- **Continuous Documentation**: GitHub Agentic Workflows (gh-aw) for auto-updating docs on PRs
- **Linting**: commitlint for conventional commits

## Code Standards

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`

### Architecture Patterns

- **Three-Layer Architecture**: Primitives (domain models) → Services (business logic) → Interfaces (CLI/SDK)
- **Single Executor Pattern**: Primary agent executes all work; subagents provide advisory guidance only
- **Result Pattern**: `Result[T] = Union[Success[T], Failure]` for explicit, type-safe error handling in services
- **Result Enum Pattern**: `InstallResult`/`MCPResult` enums for simpler control flow in installer/MCP modules
- **Protocol-Based DI**: `typing.Protocol` for structural subtyping enables dependency injection and testable services
- **Template Bundling**: Templates stored in `src/context_harness/templates/` and located at runtime via `Path(__file__).parent / "templates"`
- **Backup-Restore Pattern**: Session preservation during `--force` reinstallation

### Console Output Patterns

| Element | Style |
|---------|-------|
| Headers | `Panel.fit("[bold blue]...[/bold blue]")` |
| Success | `[green]✅[/green]` |
| Warning | `[yellow]⚠️[/yellow]` |
| Error | `[red]❌[/red]` |
| Commands | `[cyan]...[/cyan]` |
| Secondary | `[dim]...[/dim]` |
| Emojis | `📁`, `🔑` for visual anchors |

## Development Guidelines

### Setup

```bash
# Clone and install
git clone https://github.com/co-labs-co/context-harness.git
cd context-harness
uv sync --dev

# Run tests
uv run pytest

# Run CLI locally
uv run context-harness --help
```

### Testing

- Use pytest with Click's `CliRunner` for CLI testing
- Tests verify exit codes, output messages, and filesystem side effects
- Use `tmp_path` fixture for isolated temporary directories
- All new features require tests covering success, error, and edge cases
- CI runs on ubuntu, macos, windows with Python 3.9-3.12

```bash
uv run pytest                    # Run all tests
uv run pytest -v                 # Verbose output
uv run pytest tests/test_cli.py  # Specific test file
```

### Commits

Follow conventional commits format for automatic semantic versioning:

| Type | Description | Version Bump |
|------|-------------|--------------|
| `feat:` | New features | Minor |
| `fix:` | Bug fixes | Patch |
| `feat!:` | Breaking changes | Major |
| `docs:` | Documentation | None |
| `test:` | Test changes | None |
| `refactor:` | Code refactoring | None |
| `ci:` | CI changes | None |

Scopes: `cli`, `agents`, `templates`, `docs`, `ci`, `release`

Example: `feat(cli): add support for custom template paths`

## Available Skills

**CRITICAL**: When you encounter a skill reference (e.g., `@.opencode/skill/example/SKILL.md`), use your Read tool to load it on a need-to-know basis. Skills are relevant to SPECIFIC tasks.

**Instructions**:
- Do NOT preemptively load all skill references - use lazy loading based on actual need
- When loaded, treat skill content as detailed instructions for that specific task
- Follow skill references when the task matches the skill's triggers

### Core Architecture

#### Python Primitives Architecture

**Triggers**: architecture, new features, domain models, business logic, layer separation
**Reference**: @.opencode/skill/python-primitives-architecture/SKILL.md

Guide for implementing ContextHarness's three-layer architecture: Primitives → Services → Interfaces.

#### Python Result Pattern

**Triggers**: error handling, Result[T] pattern, explicit error returns, service methods that can fail
**Reference**: @.opencode/skill/python-result-pattern/SKILL.md

Implements the Result[T] = Union[Success[T], Failure] pattern for explicit, type-safe error handling.

#### Python Service with Protocol

**Triggers**: service implementation, dependency injection, external system integration, testable services
**Reference**: @.opencode/skill/python-service-with-protocol/SKILL.md

Guide for implementing services with Protocol-based dependency injection for clean testing.

#### Python Storage Abstraction

**Triggers**: storage backends, file operations, filesystem testing, memory storage
**Reference**: @.opencode/skill/python-storage-abstraction/SKILL.md

Protocol-based storage abstraction pattern enabling dependency injection and testable file operations.

### CLI & SDK

#### Python CLI Click

**Triggers**: CLI commands, Click decorators, Rich output, shell completion, CliRunner testing
**Reference**: @.opencode/skill/python-cli-click/SKILL.md

Patterns for building Click CLI applications with Rich output formatting and interactive pickers.

#### Python SDK Client

**Triggers**: SDK client, facade pattern, high-level API, client composition
**Reference**: @.opencode/skill/python-sdk-client/SKILL.md

Pattern for building SDK clients that wrap services for programmatic access.

### Testing

#### Python Protocol Mock Testing

**Triggers**: unit testing, mock implementations, protocol testing, pytest fixtures
**Reference**: @.opencode/skill/python-protocol-mock-testing/SKILL.md

Pattern for testing services with Protocol-based dependencies using mock implementations.

### Project Setup

#### Pyproject Modern Python

**Triggers**: project setup, pyproject.toml, packaging, versioning, uv
**Reference**: @.opencode/skill/pyproject-modern-python/SKILL.md

Configure modern Python projects using pyproject.toml (PEP 621), hatchling, hatch-vcs, and uv.

#### Conventional Commits Release

**Triggers**: commit messages, PR titles, version bumps, release automation
**Reference**: @.opencode/skill/conventional-commits-release/SKILL.md

Enforces conventional commit format for PR titles and commit messages, automating semantic versioning.

### Integrations

#### MCP Integration

**Triggers**: MCP servers, OAuth authentication, API keys, opencode.json, Context7
**Reference**: @.opencode/skill/mcp-integration/SKILL.md

Configure and manage MCP (Model Context Protocol) servers for AI agent tooling.

#### OAuth PKCE Flow

**Triggers**: OAuth authentication, PKCE, token management, browser-based auth
**Reference**: @.opencode/skill/oauth-pkce-flow/SKILL.md

Implement OAuth 2.1 with PKCE for secure authentication flows in CLI applications.

#### GitHub CLI Integration

**Triggers**: GitHub integration, gh CLI, PR creation, repository operations
**Reference**: @.opencode/skill/github-cli-integration/SKILL.md

Use GitHub CLI (gh) for authenticated API operations including repo access and PR creation.

#### FastAPI Static SPA

**Triggers**: FastAPI, SPA serving, static files, Next.js, React
**Reference**: @.opencode/skill/fastapi-static-spa/SKILL.md

Guide for serving static single-page applications from FastAPI backends.

### Agent Development

#### OpenCode Agent Definition

**Triggers**: agent creation, subagent definition, YAML frontmatter, tool configuration
**Reference**: @.opencode/skill/opencode-agent-definition/SKILL.md

Guide for defining AI agents using OpenCode.ai markdown format with YAML frontmatter.

#### Skill Creator

**Triggers**: skill creation, skill updates, documentation integration
**Reference**: @.opencode/skill/skill-creator/SKILL.md

Guide for creating effective skills with Context7 integration.

#### Skill Release

**Triggers**: skill versioning, skill release lifecycle, conventional commits for skills, release-please, registry repo management, init-repo scaffolding, troubleshooting releases
**Reference**: @.opencode/skill/skill-release/SKILL.md

Operational guide for creating, versioning, and releasing skills in a ContextHarness skills registry repository.

---

## External Dependencies

| Dependency | Purpose |
|------------|---------|
| **Click** | CLI framework with decorator-based commands |
| **Rich** | Terminal output with colors, panels, formatting |
| **Context7 MCP** | Remote documentation lookup (optional) |
| **GitHub CLI (gh)** | Repository operations (optional, graceful degradation) |
| **semantic-release** | Automated versioning and releases |
| **commitlint** | Commit message format enforcement |

## Quick Reference

### Common Commands

```bash
# Development
uv sync --dev                     # Install dependencies
uv run pytest                     # Run tests
uv run context-harness --help     # CLI help

# Installation (for users)
uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init

# MCP configuration
context-harness mcp add context7  # Add Context7 MCP server
context-harness mcp list          # List configured servers

# Skill management
context-harness skill list        # List available skills
context-harness skill install     # Interactive skill picker
context-harness skill outdated    # Check for updates
context-harness skill upgrade --all  # Upgrade all outdated
context-harness skill init-repo my-skills  # Scaffold registry repo

# Framework commands (after installation)
/ctx my-feature                   # Start/switch session
/contexts                         # List all sessions
/compact                          # Save context to SESSION.md
/baseline                         # Generate PROJECT-CONTEXT.md
/issue                            # GitHub issue management
/pr                               # Create pull request
```

### Key Files

| File | Purpose |
|------|---------|
| `src/context_harness/cli.py` | Click CLI entry point |
| `src/context_harness/installer.py` | Framework installation logic |
| `src/context_harness/mcp_config.py` | MCP server configuration |
| `src/context_harness/services/skill_service.py` | Skill operations (install, upgrade, init-repo) |
| `src/context_harness/interfaces/cli/skill_cmd.py` | Click commands for skill management |
| `src/context_harness/primitives/skill.py` | Skill, VersionComparison, RegistryRepo models |
| `src/context_harness/primitives/base.py` | Result[T] = Success \| Failure, ErrorCode |
| `src/context_harness/templates/` | Bundled framework templates |
| `pyproject.toml` | Project configuration, dependencies |
| `commitlint.config.js` | Conventional commits config |
| `package.json` | Node.js deps for semantic-release |

### Result Enums

```python
# src/context_harness/installer.py
class InstallResult(Enum):
    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    ERROR = "error"

# src/context_harness/mcp_config.py
class MCPResult(Enum):
    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    UPDATED = "updated"
    ERROR = "error"
```

### Result[T] Pattern (Services Layer)

Services use `Result[T] = Union[Success[T], Failure]` for explicit error handling:

```python
# src/context_harness/primitives/base.py
@dataclass
class Success(Generic[T]):
    value: T

@dataclass
class Failure:
    code: ErrorCode
    message: str

Result = Union[Success[T], Failure]
```

Used in `skill_service.py` for operations like `init_repo()`, `compare_versions()`, etc.

### opencode.json Structure

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

---

_Generated by ContextHarness /baseline command_
_Last updated: 2026-01-11_
