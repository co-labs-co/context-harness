# ContextHarness CLI

CLI installer for the [ContextHarness](https://github.com/cmtzco/context-harness) agent framework for OpenCode.ai.

## Installation

### Using uvx (recommended)

Once published to PyPI:
```bash
uvx context-harness init
```

### Using pip

Once published to PyPI:
```bash
pip install context-harness
context-harness init
```

### Install from GitHub (for testing)

To install directly from the GitHub repository (e.g., to test a branch or before PyPI publication):

```bash
# Install from main branch
uvx --from "git+https://github.com/cmtzco/context-harness.git#subdirectory=scripts/context-harness-cli" context-harness init

# Install from a specific branch
uvx --from "git+https://github.com/cmtzco/context-harness.git@feature/cli-installer#subdirectory=scripts/context-harness-cli" context-harness init

# Or using pip
pip install "git+https://github.com/cmtzco/context-harness.git#subdirectory=scripts/context-harness-cli"
context-harness init
```

## Usage

### Initialize ContextHarness in your project

```bash
# Initialize in current directory
context-harness init

# Initialize in a specific directory
context-harness init --target ./my-project

# Force overwrite existing files
context-harness init --force
```

### Other commands

```bash
# Show version
context-harness --version

# Show help
context-harness --help
context-harness init --help
```

## What gets installed

Running `context-harness init` creates the following structure in your project:

```
your-project/
├── .context-harness/
│   ├── README.md
│   ├── sessions/           # Named session directories
│   └── templates/
│       └── session-template.md
└── .opencode/
    └── agent/
        ├── context-harness.md    # Primary executor agent
        ├── compaction-guide.md   # Compaction advisory subagent
        ├── docs-subagent.md      # Documentation subagent
        └── research-subagent.md  # Research subagent
```

## Development

### Setup

```bash
cd scripts/context-harness-cli
uv sync --dev
```

### Run tests

```bash
uv run pytest tests/ -v
```

### Build

```bash
uv build
```

### Test locally

```bash
uv run context-harness --help
uv run context-harness init --target ./test-output
```

## License

MIT
