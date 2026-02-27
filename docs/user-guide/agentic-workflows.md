# Agentic Workflows

ContextHarness uses [GitHub Agentic Workflows](https://github.github.com/gh-aw/) to keep documentation automatically in sync with code changes. When a pull request is opened against `main`, an AI agent reviews the diff and updates the docs as part of the same PR.

## What Are Agentic Workflows?

GitHub Agentic Workflows (gh-aw) are AI-powered automation that run in response to repository events. Unlike traditional GitHub Actions that execute scripts, agentic workflows give an AI agent access to tools (GitHub API, file editing, bash) and let it reason about what to do.

Key characteristics:

- **Markdown-based**: Workflows are defined as `.md` files in `.github/workflows/` with YAML frontmatter
- **Tool-equipped**: Agents can use GitHub API, edit files, and run commands
- **Safe outputs**: Write operations (pushing to branches, commenting on PRs) go through a safety layer
- **Defense-in-depth**: Sandboxed execution, tool allowlisting, network isolation, and output sanitization

## Continuous Documentation

The `update-docs.md` agentic workflow implements **continuous documentation** — a pattern where documentation is treated as a living artifact that evolves with the code, not as an afterthought.

### How It Works

```
Developer opens PR → Agentic Workflow triggers → AI reviews diff
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    │                                       │
                              Code changes?                          Docs-only change?
                                    │                                       │
                                    ▼                                       ▼
                          Update relevant docs                        Skip (no-op)
                                    │
                                    ▼
                          Commit docs back to PR
```

1. A developer opens or updates a PR against `main`
2. The agentic workflow triggers on `pull_request` events (`opened`, `synchronize`)
3. The AI agent analyzes the code diff to understand what changed
4. It checks all documentation pages for gaps or outdated content
5. If updates are needed, it edits the docs and commits them back to the PR branch
6. The developer reviews both code and doc changes together

### What Gets Updated

The agent monitors and updates these documentation files:

| File | Description |
|------|-------------|
| `docs/getting-started/*.md` | Installation and quick start guides |
| `docs/user-guide/*.md` | Feature guides (commands, sessions, skills, etc.) |
| `docs/reference/*.md` | CLI reference and architecture docs |
| `docs/contributing.md` | Contributing guidelines |
| `docs/agent-install.md` | LLM agent install guide |
| `AGENTS.md` | Root project context file |
| `mkdocs.yml` | Navigation (when new pages are needed) |

### Skip Conditions

The agent intentionally skips documentation updates when a PR only contains:

- CI/CD workflow changes (`.github/workflows/*.yml`)
- Test-only changes (`tests/`)
- Dependency updates with no API changes
- Formatting or linting fixes

## Setup

### Prerequisites

- A GitHub repository with [GitHub Copilot](https://github.com/features/copilot) enabled
- The [gh-aw CLI extension](https://github.com/github/gh-aw) installed locally

### Install the gh-aw Extension

```bash
gh extension install github/gh-aw
```

### Compile the Lock File

Agentic workflows require a compiled `.lock.yml` file alongside the `.md` workflow file. The lock file is generated from the frontmatter:

```bash
gh aw compile
```

This creates `.github/workflows/update-docs.lock.yml` from `.github/workflows/update-docs.md`.

!!! warning "Both files must be committed"
    The `.md` workflow file and its `.lock.yml` companion must both be committed to the repository. The lock file is what GitHub Actions actually executes.

### Verify

After committing both files and pushing to a branch, open a PR against `main`. The agentic workflow should appear in the PR's checks.

## Workflow File Reference

The agentic workflow is defined in `.github/workflows/update-docs.md`:

```yaml
---
name: Update Documentation
on:
  pull_request:
    types: [opened, synchronize]
    branches: [main]
tools:
  - github
  - edit
  - bash
safe-outputs:
  - push-to-branch
permissions:
  contents: read
  pull-requests: read
---
```

### Frontmatter Fields

| Field | Description |
|-------|-------------|
| `name` | Display name for the workflow |
| `on` | Trigger events (same syntax as GitHub Actions) |
| `tools` | Tools available to the agent (`github`, `edit`, `bash`) |
| `safe-outputs` | Pre-approved write operations (`push-to-branch`, `create-pr`, `comment`) |
| `permissions` | Repository permissions (read-only by default) |

### Tools

| Tool | Purpose |
|------|---------|
| `github` | Read repository files, PRs, issues, and diffs |
| `edit` | Modify files in the repository |
| `bash` | Execute shell commands |

### Safe Outputs

Safe outputs are the mechanism for write operations. The agent runs with read-only permissions by default; write operations go through a safety layer that validates them.

| Safe Output | What It Does |
|-------------|--------------|
| `push-to-branch` | Push commits to the PR's branch |
| `create-pr` | Create a new pull request |
| `comment` | Comment on issues or PRs |

For this workflow, we use `push-to-branch` to commit documentation updates back to the PR.

## Customization

### Modifying the Workflow

Edit `.github/workflows/update-docs.md` to change the agent's behavior:

- Add or remove documentation files from the monitoring list
- Adjust skip conditions
- Change quality standards
- Add project-specific instructions

After editing, recompile the lock file:

```bash
gh aw compile
```

!!! note "Always recompile"
    Any change to the `.md` workflow file requires recompiling the lock file. The lock file is what actually runs — the `.md` file is the human-readable source.

### Adding More Agentic Workflows

You can create additional agentic workflows for other tasks:

- **Code review**: Automated code review on PRs
- **Issue triage**: Automatically label and categorize issues  
- **Release notes**: Generate release notes from commit history
- **Test generation**: Suggest tests for uncovered code

Each workflow follows the same pattern: a `.md` file with frontmatter + instructions, compiled to a `.lock.yml`.

## Billing

Each agentic workflow run consumes approximately **2 premium Copilot requests**:

1. One request for the actual work
2. One request for a guardrail safety check

This is billed against your GitHub Copilot subscription's premium request quota.

## Security

Agentic workflows use a defense-in-depth security model:

- **Sandboxed execution**: Workflows run in isolated environments
- **Tool allowlisting**: Only explicitly declared tools are available
- **Network isolation**: Limited network access
- **Output sanitization**: All outputs are validated before being applied
- **Read-only by default**: Write operations require explicit `safe-outputs` declaration
- **Guardrail checks**: An independent AI verifies the safety of each run's output

## Troubleshooting

### Workflow Not Triggering

- Verify both `.md` and `.lock.yml` files are committed
- Check that the PR targets the `main` branch
- Ensure GitHub Copilot is enabled for the repository
- Verify the `gh aw compile` output matches the current `.md` file

### Workflow Runs but Makes No Changes

This is expected when:

- The PR only contains skip-condition changes (tests, CI, formatting)
- Documentation is already up to date
- The diff doesn't introduce user-facing changes

### Lock File Out of Sync

If the workflow behaves unexpectedly, recompile:

```bash
gh aw compile
```

Then commit and push the updated `.lock.yml`.
