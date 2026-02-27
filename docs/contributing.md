# Contributing

Contributions are welcome! Here's how to get started.

## Development Setup

1. Clone the repository:

```bash
git clone https://github.com/co-labs-co/context-harness.git
cd context-harness
```

2. Install dependencies:

```bash
uv sync --group dev --group docs
```

3. Run tests:

```bash
uv run pytest
```

## Documentation

### Local Development

Start the documentation server:

```bash
uv run mkdocs serve
```

Visit http://127.0.0.1:8000 to preview changes.

### Building

```bash
uv run mkdocs build
```

Output is in the `site/` directory.

## Project Structure

```
context-harness/
├── src/context_harness/
│   ├── primitives/         # Domain models (dataclasses, enums, Result[T])
│   │   ├── base.py         # Result[T] = Success | Failure, ErrorCode
│   │   ├── config.py       # Configuration primitives
│   │   ├── installer.py    # InstallResult enum
│   │   ├── mcp.py          # MCP server primitives
│   │   ├── skill.py        # Skill, VersionComparison, RegistryRepo
│   │   └── tool.py         # ToolType, ToolDetector, ToolTarget
│   ├── services/           # Business logic (uses Result[T] pattern)
│   │   ├── config_service.py   # Configuration management
│   │   └── skill_service.py    # Skill operations (install, upgrade, init-repo)
│   ├── interfaces/         # CLI/SDK entry points
│   │   └── cli/
│   │       ├── skill_cmd.py    # Click commands for skill management
│   │       └── config_cmd.py   # Click commands for configuration
│   ├── cli.py              # CLI entry point (registers command groups)
│   ├── installer.py        # Framework installation logic
│   ├── mcp_config.py       # MCP server configuration
│   └── templates/          # Agent and command templates
├── tests/                  # Test suite
│   └── unit/
│       ├── services/       # Service unit tests
│       └── interfaces/cli/ # CLI integration tests
├── docs/                   # Documentation source
├── mkdocs.yml              # MkDocs configuration
└── pyproject.toml          # Project configuration
```

### Architecture: Primitives → Services → Interfaces

The codebase follows a three-layer architecture:

1. **Primitives** (`primitives/`): Pure data models using `@dataclass` and `Enum`. No business logic. Includes `Result[T] = Union[Success[T], Failure]` for explicit error handling.
2. **Services** (`services/`): Business logic that operates on primitives. Uses Protocol-based dependency injection for testability.
3. **Interfaces** (`interfaces/`): CLI commands (Click) and SDK clients that call services. Handle user I/O and formatting only.

## Guidelines

### Code Style

- Use type hints
- Follow PEP 8
- Write docstrings for public functions

### Commits

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `chore:` — Maintenance tasks

### Pull Requests

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Run tests: `uv run pytest`
4. Create a PR with a clear description

!!! note "Automatic Documentation Updates"
    When you open a PR against `main`, the [Update Documentation](user-guide/agentic-workflows.md) agentic workflow automatically reviews your code changes and updates any affected documentation pages. You'll see doc update commits appear on your PR branch — review them along with your code changes.

## License

By contributing, you agree that your contributions will be licensed under the [GNU AGPLv3](https://github.com/co-labs-co/context-harness/blob/main/LICENSE).
