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
│   ├── cli.py              # CLI entry point
│   ├── primitives/         # Data models
│   ├── services/           # Business logic
│   └── templates/          # Agent and command templates
├── tests/                  # Test suite
├── docs/                   # Documentation source
├── mkdocs.yml              # MkDocs configuration
└── pyproject.toml          # Project configuration
```

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
## License

By contributing, you agree that your contributions will be licensed under the [GNU AGPLv3](https://github.com/co-labs-co/context-harness/blob/main/LICENSE).
