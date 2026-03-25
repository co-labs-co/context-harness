# Contributing to ContextHarness

Thanks for your interest in contributing!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/co-labs-co/context-harness.git
cd context-harness

# Install dev dependencies with uv
uv sync

# Create a feature branch
git checkout -b feature/my-feature
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/context_harness
```

## Code Style

- Python 3.9+ compatible
- Follow the existing architecture (primitives → services → interfaces)
- Add tests for new functionality
- Update documentation as needed

## Project Structure

```
src/context_harness/
├── primitives/     # Domain models (pure dataclasses, no I/O)
├── services/       # Business logic
├── storage/        # Persistence layer
├── interfaces/     # CLI and future interfaces
└── templates/      # Framework templates
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design.

## Commit Convention

Use conventional commits:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance tasks

## Pull Requests

1. Create a feature branch
2. Make your changes
3. Run tests: `uv run pytest`
4. Submit a PR with a clear description

## Adding MCP Server Support

To add support for a new MCP server:

1. Add server config to `src/context_harness/mcp_config.py`
2. Add OAuth provider config if needed (in `oauth.py`)
3. Add tests
4. Update documentation

## Adding Skills

Skills are managed in a separate repository. See the [skills documentation](docs/user-guide/skills.md) for how to create and publish skills.

## Documentation

Documentation is built with MkDocs:

```bash
# Serve docs locally
uv run mkdocs serve

# Build for production
uv run mkdocs build
```

## License

By contributing, you agree that your contributions will be licensed under AGPL-3.0-or-later.
