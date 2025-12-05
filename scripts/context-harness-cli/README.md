# ContextHarness CLI

CLI installer for the [ContextHarness](https://github.com/cmtzco/context-harness) agent framework for OpenCode.ai.

## Installation

Requires [uv](https://docs.astral.sh/uv/) to be installed.

```bash
uvx --from "git+https://github.com/cmtzco/context-harness.git#subdirectory=scripts/context-harness-cli" context-harness init
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
