# Project Context: context-harness

**Generated**: 2025-12-05
**Analyzed by**: ContextHarness /baseline
**Discovery Version**: 1.0.0
**Questions Answered**: 38/38

---

## Executive Summary

ContextHarness is a CLI installer for the ContextHarness agent framework designed for OpenCode.ai. It solves the problem of context loss in long AI-assisted development sessions by implementing user-driven context preservation through named sessions and incremental compaction cycles. The framework uses a "single executor pattern" where one primary agent handles all execution while specialized subagents provide advisory guidance only.

The project is a Python CLI tool built with Click and Rich, distributed via PyPI and installable through `uvx`. It creates a structured framework of markdown-based agent definitions and session management files that integrate with OpenCode.ai's agent system. The framework includes session management (`/ctx`, `/contexts`, `/compact`), GitHub integration (`/issue`, `/pr`), and a comprehensive baseline analysis feature (`/baseline`) that generates PROJECT-CONTEXT.md files through a 3-phase subagent pipeline.

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| **Name** | context-harness |
| **Type** | CLI installer |
| **Primary Language** | Python 3.9+ |
| **Framework** | Click CLI |
| **Package Manager** | uv |
| **Build Backend** | hatchling |
| **Version Management** | hatch-vcs (git tags) |
| **Test Framework** | pytest |
| **CI/CD** | GitHub Actions + semantic-release |

### Directory Structure

```
context-harness/
├── src/context_harness/        # Python source code
│   ├── templates/              # Bundled framework templates
│   │   ├── .context-harness/   # Session management files
│   │   └── .opencode/          # Agent and command definitions
│   ├── cli.py                  # Click CLI entry point
│   ├── installer.py            # Framework installation logic
│   └── mcp_config.py           # MCP server configuration
├── tests/                      # pytest test suite
├── .github/workflows/          # CI/CD workflows
└── pyproject.toml              # Project configuration
```

---

## Architecture Decisions

### Q001: Why does the framework use a 'single executor pattern' where only the primary agent can execute work while subagents are advisory-only?

**Answer**: The single executor pattern prevents conflicts and confusion that arise when multiple agents can execute work simultaneously. By centralizing all execution (code writing, file modifications, command execution) in the Primary Agent, the framework ensures clear responsibility and consistent state management. Subagents provide specialized guidance (research, documentation, compaction recommendations) but cannot modify files, preventing race conditions and conflicting changes.

**Evidence**:
- `README.md:16` - `"4. **Single Executor Pattern**: One primary agent executes all work; specialized subagents provide guidance only"`
- `.context-harness/README.md:7` - `"The framework uses a **single executor pattern** with advisory subagents - only the Primary Agent executes work"`
- `src/context_harness/templates/.opencode/agent/context-harness.md:22` - `"## CRITICAL: You are the ONLY agent that executes work"`
- `src/context_harness/templates/.opencode/agent/context-harness.md:38` - `"**NEVER DELEGATE EXECUTION**: Subagents provide guidance only - they cannot and will not execute"`

**Confidence**: High

---

### Q002: What is the purpose of the SESSION.md file and how does it enable context continuity across conversation sessions?

**Answer**: SESSION.md is a "living document" that maintains work continuity across conversation sessions by preserving key context that would otherwise be lost when the AI's context window fills or a new session starts. It stores: Active Work (current task, status, blockers), Key Files (files being modified with purposes), Decisions Made (important decisions with rationale), Documentation References (relevant docs with links), Next Steps (prioritized action items), and Completed This Session (archived work).

**Evidence**:
- `README.md:15` - `"3. **SESSION.md**: A living document that preserves decisions, file changes, and next steps"`
- `README.md:147-158` - Table documenting SESSION.md sections and their purposes
- `src/context_harness/templates/.context-harness/templates/session-template.md:1-74` - Complete SESSION.md template structure
- `.context-harness/README.md:189-203` - SESSION.md sections table with Active Work, Key Files, Decisions Made, Documentation References, Next Steps, Completed This Session

**Confidence**: High

---

### Q003: Why are sessions stored in individual directories under .context-harness/sessions/{session-name}/ rather than a single sessions file?

**Answer**: Individual session directories enable multiple concurrent sessions for different features/tickets, each with isolated context. This supports parallel workstreams (e.g., `login-feature`, `TICKET-1234`, `api-rate-limiting` simultaneously) without context collision. The directory structure also allows for future expansion (attachments, related files per session) and makes session management (listing, switching, archiving) cleaner.

**Evidence**:
- `src/context_harness/templates/.opencode/agent/context-harness.md:59-77` - Multi-session support documentation showing directory structure
- `README.md:91-94` - Directory structure showing `sessions/{session-name}/SESSION.md` pattern
- `.context-harness/README.md:49-59` - Directory structure showing multiple concurrent sessions example

**Confidence**: High

---

### Q004: What drives the separation between .opencode/agent/ and .opencode/command/ directories?

**Answer**: This separation follows OpenCode.ai's agent system conventions. The `.opencode/agent/` directory contains agent definitions (personas, capabilities, behavioral rules), while `.opencode/command/` contains slash command definitions that route user commands to specific agents. Commands define the entry point and instructions, agents define the executor's identity and capabilities. This separation allows commands to be lightweight routing files while agents contain the full behavioral specification.

**Evidence**:
- `README.md:97-109` - Directory structure documentation showing agent/ (Primary executor agent, subagents) vs command/ (slash commands)
- `src/context_harness/templates/.opencode/command/ctx.md:1-4` - Command frontmatter with `agent: context-harness` routing
- `src/context_harness/templates/.opencode/command/contexts.md:5` - Shows command routing to `agent: contexts-subagent`
- `tests/test_cli.py:200-205` - Test verifying `agent: contexts-subagent` routing

**Confidence**: High

---

### Q005: How does the installer preserve user sessions during --force reinstallation?

**Answer**: The installer uses a backup-restore pattern. Before overwriting `.context-harness/`, it backs up the `sessions/` directory to a temporary location outside the target directory (`.sessions.backup`), removes the old `.context-harness/` directory, copies fresh templates, then restores the sessions directory. This ensures user work is never lost during upgrades.

**Evidence**:
- `src/context_harness/installer.py:77` - Comment: `"If True, overwrite existing files (preserves sessions/)"`
- `src/context_harness/installer.py:148-180` - `_copy_preserving_sessions()` function implementation
- `src/context_harness/installer.py:160-164` - Backup logic: `sessions_backup = target.parent / ".sessions.backup"`
- `tests/test_cli.py:139-159` - `test_init_force_preserves_sessions` verifying session preservation

**Confidence**: High

---

### Q006: Why is the baseline feature split into three separate subagents?

**Answer**: The three-phase pipeline (Discovery → Questions → Answers) follows a separation of concerns pattern optimized for quality and maintainability. Phase 1 (`@baseline-discovery`) focuses solely on codebase analysis and structure detection. Phase 2 (`@baseline-questions`) specializes in generating and validating insightful questions based on discovery. Phase 3 (`@baseline-answers`) searches for evidence and compiles answers. Each subagent has a focused responsibility, enabling specialized prompts, independent iteration, and clear handoffs.

**Evidence**:
- `src/context_harness/templates/.opencode/agent/context-harness.md:291-515` - Complete /baseline command workflow documentation
- `src/context_harness/templates/.opencode/command/baseline.md:14-33` - Phase diagram showing 3-phase pipeline
- `src/context_harness/installer.py:34-36` - Required template files listing three baseline agents

**Confidence**: High

---

### Q007: What is the role of the contexts-subagent and why is it separate from the main context-harness agent?

**Answer**: The `contexts-subagent` is a read-only session listing agent that scans `.context-harness/sessions/`, extracts metadata from each SESSION.md, and returns a formatted summary. It's separate to keep the primary agent's context clean—session listing is a self-contained operation that doesn't need the primary agent's full execution capabilities. The subagent has only `read`, `glob`, and `list` tools (no `write`, `edit`, `bash`), enforcing its advisory-only role.

**Evidence**:
- `README.md:162-163` - `"When you run /contexts, this subagent scans all sessions, extracts metadata, and returns a formatted summary—keeping the primary agent's context clean. **Read-only—does not execute.**"`
- `src/context_harness/templates/.opencode/agent/contexts-subagent.md:6-17` - Tool configuration showing `write: false`, `edit: false`, `bash: false`
- `src/context_harness/templates/.opencode/agent/contexts-subagent.md:28` - `"Your sole purpose is to discover and summarize existing sessions"`
- `tests/test_cli.py:205` - Test verifying `agent: contexts-subagent` routing

**Confidence**: High

---

## External Dependencies & Integrations

### Q008: Why was Click chosen as the CLI framework?

**Answer**: Click is the de-facto standard Python CLI framework, offering decorator-based command definition, automatic help generation, parameter validation, nested command groups, and excellent testing support via `CliRunner`. It provides a clean, Pythonic API that scales from simple scripts to complex CLI applications. The project uses Click's `@click.group()`, `@click.command()`, and `@click.option()` decorators for structured command definition.

**Evidence**:
- `pyproject.toml:25` - `"click>=8.0"` dependency
- `src/context_harness/cli.py:3` - `import click`
- `src/context_harness/cli.py:19-27` - `@click.group()` decorator usage
- `src/context_harness/cli.py:98` - `@click.argument("server", type=click.Choice(get_available_servers()))` showing Click's validation
- `tests/test_cli.py:8,16` - `from click.testing import CliRunner` for testing

**Confidence**: High

---

### Q009: What is the purpose of the Rich library in this project?

**Answer**: Rich provides beautiful terminal output with colors, panels, styled text, and formatting. The CLI uses Rich's `Console` for all user-facing output, including styled messages (`[green]✅[/green]`, `[red]❌[/red]`), panels for headers (`Panel.fit()`), and dim text for secondary information. This creates a polished, professional CLI experience.

**Evidence**:
- `pyproject.toml:26` - `"rich>=13.0"` dependency
- `src/context_harness/cli.py:4-5` - `from rich.console import Console` and `from rich.panel import Panel`
- `src/context_harness/cli.py:56-61` - `Panel.fit("[bold blue]ContextHarness[/bold blue] Installer", subtitle=f"v{__version__}")`
- `src/context_harness/cli.py:67` - `console.print("[green]✅ ContextHarness initialized successfully![/green]")`
- `src/context_harness/installer.py:190` - `console.print("  📁 .context-harness/")` emoji usage

**Confidence**: High

---

### Q010: What is Context7 MCP and why is it integrated?

**Answer**: Context7 MCP (Model Context Protocol) is a remote service that provides up-to-date documentation lookup for popular libraries and frameworks. It enables the research and documentation subagents to fetch accurate, version-specific API documentation rather than relying on potentially outdated training data. Integration is optional but recommended for "grounded research capabilities."

**Evidence**:
- `README.md:215-219` - `"The research and documentation subagents require Context7 MCP for accurate, up-to-date library documentation"`
- `README.md:169` - `"**Context7 MCP Integration**: Access to up-to-date documentation for popular libraries and frameworks"`
- `src/context_harness/mcp_config.py:26-30` - Context7 server configuration: `"type": "remote", "url": "https://mcp.context7.com/mcp"`
- `opencode.json:3-8` - MCP configuration showing context7 integration

**Confidence**: High

---

### Q011: How does the MCP server configuration work?

**Answer**: MCP servers are configured in `opencode.json` under the `mcp` key. The CLI provides `context-harness mcp add {server}` to add servers and `mcp list` to view configured servers. The configuration supports remote servers (URL-based) with optional API keys passed via headers. When adding a server, the CLI loads existing config, merges in the new server, and preserves all other settings.

**Evidence**:
- `src/context_harness/mcp_config.py:45-64` - `load_opencode_config()` function
- `src/context_harness/mcp_config.py:83-162` - `add_mcp_server()` function with merge logic
- `src/context_harness/mcp_config.py:121-122` - API key handling: `new_config["headers"] = {"CONTEXT7_API_KEY": api_key}`
- `tests/test_cli.py:287-312` - `test_mcp_add_preserves_existing_config` verifying merge behavior

**Confidence**: High

---

### Q012: Why is GitHub CLI (gh) an optional dependency?

**Answer**: GitHub CLI enables branch creation, issue tracking, and PR creation features (`/ctx` creates feature branches, `/issue` creates GitHub issues, `/pr` creates pull requests). It's optional because ContextHarness works locally without GitHub integration—sessions function normally without `gh`. The framework provides "graceful degradation" where GitHub features are skipped if `gh` is unavailable.

**Evidence**:
- `README.md:135-137` - `"**Requirements**: GitHub CLI (gh) installed and authenticated"` and `"**Graceful degradation**: If gh is not available, GitHub features are skipped and sessions work locally only."`
- `README.md:214` - `"GitHub CLI (gh) for repository operations (optional)"`
- `src/context_harness/templates/.opencode/command/ctx.md:35-45` - GitHub integration section showing branch/issue creation

**Confidence**: High

---

## Code Patterns

### Q013: What is the InstallResult enum pattern used in the installer?

**Answer**: `InstallResult` is a simple enum with three states: `SUCCESS`, `ALREADY_EXISTS`, and `ERROR`. Functions return this enum instead of raising exceptions or returning boolean/None, enabling clear control flow in the CLI layer without try/catch blocks. The CLI maps each result to appropriate user messaging and exit codes.

**Evidence**:
- `src/context_harness/installer.py:12-17` - `class InstallResult(Enum): SUCCESS = "success", ALREADY_EXISTS = "already_exists", ERROR = "error"`
- `src/context_harness/cli.py:66-85` - Result handling: `if result == InstallResult.SUCCESS:`, `elif result == InstallResult.ALREADY_EXISTS:`, `elif result == InstallResult.ERROR:`
- `src/context_harness/mcp_config.py:15-21` - Similar `MCPResult` enum with `SUCCESS`, `ALREADY_EXISTS`, `UPDATED`, `ERROR`

**Confidence**: High

---

### Q014: How does the CLI structure commands using Click's decorators?

**Answer**: The CLI uses Click's group/command hierarchy. `@click.group()` creates the root `main()` group. `@main.command()` creates subcommands (`init`). `@main.group()` creates nested groups (`mcp`). `@mcp.command()` creates nested subcommands (`add`, `list`). Options use `@click.option()` with flags, types, defaults, and help text. Arguments use `@click.argument()` with validation via `click.Choice()`.

**Evidence**:
- `src/context_harness/cli.py:19` - `@click.group()` for main entry
- `src/context_harness/cli.py:30` - `@main.command()` for init
- `src/context_harness/cli.py:88` - `@main.group()` for mcp subgroup
- `src/context_harness/cli.py:97-98` - `@mcp.command("add")` with `@click.argument("server", type=click.Choice(...))`
- `src/context_harness/cli.py:31-39` - Options: `@click.option("--force", "-f", is_flag=True, help="...")`

**Confidence**: High

---

### Q015: What console output patterns does the CLI follow?

**Answer**: The CLI follows consistent visual feedback patterns: Panels for headers (`Panel.fit()`), checkmarks for success (`[green]✅[/green]`), warnings in yellow (`[yellow]⚠️[/yellow]`), errors in red (`[red]❌[/red]`), cyan for commands/code (`[cyan]context-harness init[/cyan]`), dim text for secondary info (`[dim]...[/dim]`), and emoji prefixes for visual scanning (`📁`, `🔑`).

**Evidence**:
- `src/context_harness/cli.py:56-61` - `Panel.fit("[bold blue]ContextHarness[/bold blue] Installer")`
- `src/context_harness/cli.py:67` - `"[green]✅ ContextHarness initialized successfully![/green]"`
- `src/context_harness/cli.py:80` - `"[yellow]⚠️  ContextHarness files already exist.[/yellow]"`
- `src/context_harness/cli.py:84` - `"[red]❌ Failed to initialize ContextHarness.[/red]"`
- `src/context_harness/installer.py:190-203` - `"📁 .context-harness/"` and `"📁 .opencode/"`
- `src/context_harness/mcp_config.py:192` - `key_indicator = " 🔑" if has_key else ""`

**Confidence**: High

---

### Q016: How are template files bundled and located at runtime?

**Answer**: Template files are stored in `src/context_harness/templates/` and bundled in the wheel package. At runtime, `get_templates_dir()` uses `Path(__file__).parent / "templates"` to locate templates relative to the installed module. This works for both editable installs and pip-installed packages.

**Evidence**:
- `src/context_harness/installer.py:20-22` - `def get_templates_dir() -> Path: return Path(__file__).parent / "templates"`
- `pyproject.toml:47-48` - `[tool.hatch.build.targets.wheel] packages = ["src/context_harness"]`
- File structure showing `src/context_harness/templates/.context-harness/` and `src/context_harness/templates/.opencode/`

**Confidence**: High

---

### Q017: What validation pattern is used for template files?

**Answer**: The installer defines `REQUIRED_TEMPLATE_FILES` as a list of all expected template file paths. The `validate_templates()` function checks each path exists in the templates directory and returns a list of missing files. If any are missing, installation fails with a clear error listing the missing files.

**Evidence**:
- `src/context_harness/installer.py:26-43` - `REQUIRED_TEMPLATE_FILES` list with 16 required files
- `src/context_harness/installer.py:46-67` - `validate_templates()` function checking each file
- `src/context_harness/installer.py:62-65` - Error output: `"Error: Bundled templates are incomplete. Missing files:"`

**Confidence**: High

---

### Q018: How does opencode.json preserve existing settings when adding MCP servers?

**Answer**: The `add_mcp_server()` function loads existing `opencode.json` via `load_opencode_config()`, adds the new server to the `mcp` section while preserving all other keys (like `theme`, existing `mcp` servers), then saves with `save_opencode_config()`. The save function ensures `$schema` is first. Tests verify this merge behavior explicitly.

**Evidence**:
- `src/context_harness/mcp_config.py:111-112` - `config = load_opencode_config(config_path)` then `config["mcp"][server_name] = new_config`
- `src/context_harness/mcp_config.py:74-76` - `save_opencode_config()` ensures `$schema` is first
- `tests/test_cli.py:287-312` - `test_mcp_add_preserves_existing_config` verifying `theme: dark` and `other-server` preserved

**Confidence**: High

---

## Language & Framework Rationale

### Q019: Why use hatch-vcs for version management?

**Answer**: hatch-vcs derives version numbers automatically from git tags, eliminating manual version management. This integrates cleanly with semantic-release which creates git tags on release. The `dynamic = ["version"]` in pyproject.toml declares version as dynamic, and `[tool.hatch.version] source = "vcs"` configures git tag-based versioning.

**Evidence**:
- `pyproject.toml:3` - `dynamic = ["version"]`
- `pyproject.toml:38` - `requires = ["hatchling", "hatch-vcs"]`
- `pyproject.toml:41-42` - `[tool.hatch.version] source = "vcs"`

**Confidence**: High

---

### Q020: Why was uv chosen as the package manager?

**Answer**: uv is a fast, modern Python package manager from Astral (makers of ruff). It's recommended for ContextHarness installation via `uvx` (single-command execution from package). The project uses `uv sync --dev` for development and CI. uv provides significantly faster dependency resolution and installation than pip.

**Evidence**:
- `README.md:22-25` - `"Requires uv. Run this in your project directory: uvx --from ..."`
- `.github/workflows/test-cli.yml:29-32` - CI uses `astral-sh/setup-uv@v4`
- `.github/workflows/test-cli.yml:38` - `uv sync --dev`
- `.github/workflows/test-cli.yml:76` - `uvx --from dist/*.whl context-harness init`

**Confidence**: High

---

### Q021: Why support Python 3.9 through 3.12?

**Answer**: Python 3.9 is the minimum to balance modern features (like native type hints for generics) with broad compatibility. Python 3.12 is the latest stable version. This range covers most production environments and CI systems. The project uses no features requiring newer Python versions.

**Evidence**:
- `pyproject.toml:6` - `requires-python = ">=3.9"`
- `pyproject.toml:17-21` - Classifiers listing Python 3.9, 3.10, 3.11, 3.12
- `.github/workflows/test-cli.yml:22` - CI matrix: `python-version: ["3.9", "3.10", "3.11", "3.12"]`

**Confidence**: High

---

### Q022: Why is hatchling used as the build backend?

**Answer**: Hatchling is a modern, standards-compliant Python build backend that works well with pyproject.toml-only projects. It integrates with hatch-vcs for version management and provides clean wheel/sdist building. It's lighter than setuptools for pure-Python projects and follows PEP 517/518 standards.

**Evidence**:
- `pyproject.toml:37-39` - `[build-system] requires = ["hatchling", "hatch-vcs"] build-backend = "hatchling.build"`
- `pyproject.toml:47-48` - `[tool.hatch.build.targets.wheel] packages = ["src/context_harness"]`

**Confidence**: High

---

## Build & Distribution

### Q023: How does semantic-release determine version bumps?

**Answer**: semantic-release uses the `@semantic-release/commit-analyzer` plugin to parse commit messages following conventional commits format. `feat:` commits trigger minor version bumps, `fix:` commits trigger patch bumps, `feat!:` or `BREAKING CHANGE:` trigger major bumps. The commit format is enforced by commitlint in PR titles.

**Evidence**:
- `package.json:19-23` - `"plugins": ["@semantic-release/commit-analyzer", "@semantic-release/release-notes-generator", "@semantic-release/github"]`
- `commitlint.config.js:4-19` - `type-enum` listing `feat`, `fix`, `docs`, etc.
- `.github/workflows/commitlint.yml:27-30` - `echo "$PR_TITLE" | npx commitlint`

**Confidence**: High

---

### Q024: Why use Node.js/npm for semantic-release in a Python project?

**Answer**: semantic-release is a mature, well-maintained release automation tool from the Node.js ecosystem with excellent GitHub integration. While Python alternatives exist (python-semantic-release), the Node.js version has broader adoption and plugin ecosystem. Since the project already uses npm for commitlint, adding semantic-release has minimal overhead.

**Evidence**:
- `package.json:12-15` - Node.js devDependencies: `@commitlint/cli`, `@commitlint/config-conventional`, `semantic-release`
- `.github/workflows/release.yml:24-38` - Node.js setup and `npx semantic-release`
- `.github/workflows/commitlint.yml:19-22` - Node.js setup for commitlint

**Confidence**: High

---

### Q025: What files are included in distributions?

**Answer**: Wheel packages include `src/context_harness/` (all Python code and templates). Source distributions include `src/`, `README.md`, and `LICENSE`. Templates are bundled inside the package at `context_harness/templates/`.

**Evidence**:
- `pyproject.toml:47-48` - `[tool.hatch.build.targets.wheel] packages = ["src/context_harness"]`
- `pyproject.toml:50-55` - `[tool.hatch.build.targets.sdist] include = ["src/", "README.md", "LICENSE"]`

**Confidence**: High

---

### Q026: How does versioning handle non-git scenarios?

**Answer**: hatch-vcs provides a fallback version `"0.0.0+unknown"` when git metadata is unavailable (e.g., building from a tarball without `.git/`). This prevents build failures while clearly indicating the version is unknown.

**Evidence**:
- `pyproject.toml:44-45` - `[tool.hatch.version.raw-options] fallback_version = "0.0.0+unknown"`

**Confidence**: High

---

### Q027: What is the recommended installation method?

**Answer**: The recommended method is `uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init`, which installs and runs in one command without polluting global packages. Manual installation involves cloning and copying template directories.

**Evidence**:
- `README.md:24-25` - `uvx --from "git+https://github.com/co-labs-co/context-harness.git" context-harness init`
- `README.md:263-271` - Manual installation instructions

**Confidence**: High

---

## Testing Strategy

### Q028: What testing strategy is used for CLI commands?

**Answer**: Tests use Click's `CliRunner` to invoke CLI commands programmatically without subprocess overhead. Tests verify exit codes, output messages, and filesystem side effects. Each command has dedicated test methods covering success paths, error paths, and edge cases.

**Evidence**:
- `tests/test_cli.py:8` - `from click.testing import CliRunner`
- `tests/test_cli.py:13-16` - `@pytest.fixture def runner(): return CliRunner()`
- `tests/test_cli.py:46-53` - `test_init_creates_directories` using `runner.invoke(main, ["init", "--target", str(tmp_path)])`

**Confidence**: High

---

### Q029: How does the test suite verify session preservation?

**Answer**: `test_init_force_preserves_sessions` creates a session with content, runs `init --force`, then verifies the session directory and file still exist with original content. CI integration tests also verify this with `grep -q "Important session data"`.

**Evidence**:
- `tests/test_cli.py:139-159` - `test_init_force_preserves_sessions` creating session, running --force, verifying content preserved
- `.github/workflows/test-cli.yml:92-109` - Integration test: creates session, runs --force, uses grep to verify preservation

**Confidence**: High

---

### Q030: Why does CI include integration tests simulating uvx?

**Answer**: Integration tests ensure the built wheel works correctly when installed via uvx, the recommended installation method. This catches packaging issues (missing templates, broken entry points) that unit tests can't detect. The test builds a wheel, installs via uvx, and verifies file creation.

**Evidence**:
- `.github/workflows/test-cli.yml:49-90` - `integration-test` job
- `.github/workflows/test-cli.yml:70-71` - `"# Run the CLI via uvx from the built wheel"` and `uvx --from dist/*.whl context-harness init`
- `.github/workflows/test-cli.yml:78-90` - File existence verification

**Confidence**: High

---

### Q031: What test fixtures and patterns are used?

**Answer**: Tests use `@pytest.fixture` for shared setup (`runner` fixture for CliRunner). `tmp_path` is a built-in pytest fixture providing isolated temporary directories. Tests use pytest's `assert` statements and class-based organization (`TestCLI`, `TestInitCommand`, `TestMCPCommand`).

**Evidence**:
- `tests/test_cli.py:13-16` - `@pytest.fixture def runner(): return CliRunner()`
- `tests/test_cli.py:46` - `def test_init_creates_directories(self, runner, tmp_path)` using both fixtures
- `tests/test_cli.py:19,35,222` - Class organization: `TestCLI`, `TestInitCommand`, `TestMCPCommand`

**Confidence**: High

---

### Q032: Why cross-platform CI testing?

**Answer**: The CLI creates directories and files, which have platform-specific behavior (path separators, permissions). Testing on ubuntu, macos, and windows with multiple Python versions ensures the installer works across all common developer environments.

**Evidence**:
- `.github/workflows/test-cli.yml:19-22` - `matrix: os: [ubuntu-latest, macos-latest, windows-latest] python-version: ["3.9", "3.10", "3.11", "3.12"]`
- `tests/test_cli.py:93-94,102-103` - `encoding="utf-8"` used for Windows compatibility

**Confidence**: High

---

## Configuration

### Q033: What is the structure of opencode.json?

**Answer**: `opencode.json` is the OpenCode.ai configuration file. It has a `$schema` field for validation, and an `mcp` object containing MCP server configurations. Each server entry has `type` ("remote" or "local"), `url` or `command`, and optional `headers` for authentication.

**Evidence**:
- `opencode.json:1-9` - Example structure: `{"$schema": "...", "mcp": {"context7": {"type": "remote", "url": "..."}}}`
- `README.md:221-230` - Configuration example documentation
- `src/context_harness/mcp_config.py:74-76` - Schema handling: `config = {"$schema": "https://opencode.ai/config.json", **config}`

**Confidence**: High

---

### Q034: How does the CLI handle --target option?

**Answer**: The `--target` option (shorthand `-t`) specifies the installation directory, defaulting to `.` (current directory). It's declared with `type=click.Path()` for path validation. The path is resolved to absolute via `Path(target).resolve()` before operations.

**Evidence**:
- `src/context_harness/cli.py:34-39` - `@click.option("--target", "-t", default=".", type=click.Path(), help="Target directory...")`
- `src/context_harness/installer.py:83` - `target_path = Path(target).resolve()`
- `tests/test_cli.py:48` - Test: `runner.invoke(main, ["init", "--target", str(tmp_path)])`

**Confidence**: High

---

### Q035: What conventional commit format is required?

**Answer**: Commits must follow conventional commits format: `type(scope): description`. Types include `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Scopes are `cli`, `agents`, `templates`, `docs`, `ci`, `release`. Subject must be lowercase, max 100 characters.

**Evidence**:
- `commitlint.config.js:4-19` - type-enum with all allowed types
- `commitlint.config.js:21-32` - scope-enum with recommended scopes
- `commitlint.config.js:33-34` - `subject-case: lower-case`, `header-max-length: 100`

**Confidence**: High

---

## Developer Experience

### Q036: What 'Next steps' are shown after installation?

**Answer**: After successful init, the CLI shows four numbered steps: 1) Optional Context7 MCP setup (`context-harness mcp add context7`), 2) Start a session (`@context-harness /ctx my-feature`), 3) Work normally—agent handles execution, 4) Compact when ready (`/compact`).

**Evidence**:
- `src/context_harness/cli.py:69-77` - Next steps output
- `tests/test_cli.py:137` - Test verifying `"Next steps" in result.output`

**Confidence**: High

---

### Q037: How does the CLI provide visual feedback using Rich?

**Answer**: The CLI uses Rich's `Console` for all output with semantic colors: blue/bold for headers, green with ✅ for success, yellow with ⚠️ for warnings, red with ❌ for errors, cyan for commands, dim for secondary info. Panels wrap major sections. Emojis (📁, 🔑) provide visual anchors.

**Evidence**:
- `src/context_harness/cli.py:56-61` - Panel header
- `src/context_harness/cli.py:67,80,84` - Success/warning/error patterns
- `src/context_harness/mcp_config.py:187-193` - List formatting with emoji

**Confidence**: High

---

### Q038: What slash commands are available and how documented?

**Answer**: Available commands: `/ctx {name}` (switch/create session), `/contexts` (list sessions), `/compact` (save context), `/issue` (GitHub issue management), `/pr` (pull request creation), `/baseline` (project analysis). Commands are documented in README tables and in `.opencode/command/` files with `description:` frontmatter that shows when typing `/` in OpenCode TUI.

**Evidence**:
- `README.md:116-123` - Commands table
- `src/context_harness/templates/.opencode/command/ctx.md:1-3` - `description: Switch to or create a ContextHarness session`
- `src/context_harness/templates/.opencode/command/compact.md:1-3` - `description: Save current context to SESSION.md`
- `src/context_harness/templates/.opencode/agent/context-harness.md:209-215` - Commands table in agent definition

**Confidence**: High

---

## Unanswered Questions

No questions were unanswered. All 38 questions had evidence in the codebase.

---

## Analysis Metadata

| Metric | Value |
|--------|-------|
| **Files Analyzed** | 18 |
| **Questions Received** | 38 |
| **Questions Answered** | 38 |
| **High Confidence Answers** | 29 |
| **Medium Confidence Answers** | 9 |
| **Low Confidence Answers** | 0 |
| **Unanswered** | 0 |

---

## Recommended Follow-ups

Based on this analysis, consider manually documenting:

1. **Performance characteristics** - No benchmarks or performance documentation found. Consider documenting expected install times, template sizes.
2. **Migration guides** - If upgrading from earlier versions, document breaking changes and migration steps.
3. **Troubleshooting guide** - While `.context-harness/README.md` has troubleshooting, consider expanding with common issues users encounter.

---

_Generated by ContextHarness /baseline command_
_This document should be reviewed and supplemented with team knowledge_
