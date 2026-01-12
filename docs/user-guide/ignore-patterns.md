# Ignore Patterns

ContextHarness supports a `.contextignore` file for excluding files and directories from context scanning. This is useful for large projects with directories that don't need to be analyzed.

## Overview

The `.contextignore` file uses the same syntax as `.gitignore`. When you run `ch init`, an empty `.contextignore` template is created in your project root.

## Default Patterns

ContextHarness automatically ignores common directories even without a `.contextignore` file:

| Category | Patterns |
|----------|----------|
| **Version Control** | `.git/`, `.svn/`, `.hg/` |
| **Dependencies** | `node_modules/`, `vendor/`, `.venv/`, `venv/`, `__pycache__/` |
| **Build Artifacts** | `dist/`, `build/`, `.next/`, `.nuxt/`, `out/`, `target/` |
| **Cache** | `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.cache/` |
| **IDE** | `.idea/`, `.vscode/` |
| **Lock Files** | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock` |

## Syntax

The `.contextignore` file follows `.gitignore` syntax:

```gitignore
# Comments start with #
node_modules/          # Directory pattern (trailing slash)
*.pyc                  # Wildcard pattern
!important.pyc         # Negation (un-ignore)
**/test_*.py           # Recursive wildcard
apps/legacy/           # Specific path
```

### Pattern Types

| Pattern | Matches |
|---------|---------|
| `foo/` | Directory named `foo` and all contents |
| `*.log` | All files ending in `.log` |
| `!keep.log` | Exclude `keep.log` from being ignored |
| `**/temp/` | Any `temp/` directory at any depth |
| `docs/*.md` | Markdown files directly in `docs/` |

## Examples

### Monorepo with Multiple Apps

Exclude apps you're not working on:

```gitignore
# Ignore legacy app
apps/legacy-app/

# Ignore deprecated packages
packages/deprecated/
packages/old-utils/

# But keep the shared package
!packages/shared/
```

### Large Generated Content

Exclude generated files that inflate context:

```gitignore
# Generated code
.generated/
codegen/
*.generated.ts

# API clients
src/api/generated/
```

### Test Data

Exclude large test fixtures:

```gitignore
# Large test fixtures
tests/fixtures/large/
test-data/
__fixtures__/

# But keep small fixtures
!tests/fixtures/small/
```

### Documentation Sites

Exclude built documentation:

```gitignore
# Built docs
docs/_build/
site/
.docusaurus/
```

### Vendored Dependencies

Exclude third-party code copied into repo:

```gitignore
vendor/
third_party/
external/
```

## Programmatic Usage

The `IgnoreService` can be used programmatically in Python:

```python
from context_harness.services import IgnoreService
from pathlib import Path

# Load ignore configuration
service = IgnoreService()
config = service.load_or_default(Path("."))

# Check if a path should be ignored
if service.should_ignore(Path("node_modules/foo.js"), config):
    print("Ignoring node_modules/foo.js")

# Filter a list of paths
paths = [Path("src/main.py"), Path("node_modules/x.js")]
filtered = service.filter_paths(paths, config)
# Returns: [Path("src/main.py")]

# Get patterns for external tools
result = service.get_exclusion_patterns()
if isinstance(result, Success):
    for pattern in result.value:
        print(f"--exclude={pattern}")
```

## How It Works

1. **On `ch init`**: A minimal `.contextignore` template is created
2. **On `/baseline`**: The discovery phase respects ignore patterns
3. **Pattern matching**: Uses the `pathspec` library for accurate gitignore-style matching
4. **Layered patterns**: Default patterns are applied first, then your custom patterns

## Tips

- **Start minimal**: Only add patterns when you notice context overload
- **Use negation sparingly**: `!` patterns can be confusing; prefer explicit includes
- **Test patterns**: Run `/baseline` and check what's included in PROJECT-CONTEXT.md
- **Share patterns**: Commit `.contextignore` so your team benefits
