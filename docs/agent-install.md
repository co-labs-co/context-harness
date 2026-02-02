# context-harness

> Context-aware agent framework for OpenCode.ai that maintains session continuity across conversations.

If you're an LLM agent (Claude Code or opencode) helping a user install ContextHarness, welcome! Execute these steps autonomously.

**OBJECTIVE**: Install the `ch` CLI tool and initialize it in the user's project.

**DONE WHEN**: Running `ch --version` outputs a version number AND `ch init` completes successfully.

---

## TODO

- [ ] Verify Python 3.9+ is installed
- [ ] Install uv package manager (if missing)
- [ ] Install context-harness via uv
- [ ] Verify CLI installation
- [ ] Initialize in project directory
- [ ] Confirm success to user

---

## Step 1: Check Python Version

Run this command to check the Python version:

```bash
python3 --version
```

**Requirement**: Python 3.9 or higher.

- If version is **3.9+**: Continue to Step 2
- If version is **below 3.9** or command not found: STOP and tell the user:
  > "ContextHarness requires Python 3.9 or higher. Please install or upgrade Python before continuing."
  > - macOS: `brew install python@3.12`
  > - Ubuntu/Debian: `sudo apt install python3.12`
  > - Windows: Download from https://python.org

---

## Step 2: Install uv Package Manager (if needed)

Check if uv is already installed:

```bash
uv --version
```

- If uv **is installed** (outputs version): Continue to Step 3
- If uv **is NOT installed** (command not found): Install it using the appropriate command:

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, the shell may need to be restarted or PATH updated. Try:
```bash
source ~/.bashrc   # Linux
source ~/.zshrc    # macOS with zsh
# Or restart the terminal
```

Verify uv is now available:
```bash
uv --version
```

---

## Step 3: Install ContextHarness

Install the CLI globally using uv:

```bash
uv tool install "git+https://github.com/co-labs-co/context-harness.git"
```

This installs both the `context-harness` and `ch` commands (they are identical).

**Expected output**: Installation success message with no errors.

**If you see a PATH warning**: The uv tool directory may not be in PATH. Add it:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## Step 4: Verify CLI Installation

```bash
ch --version
```

**Expected output**: A version string like `context-harness 0.x.x`

- If version **is displayed**: Continue to Step 5
- If **command not found**: Check that `~/.local/bin` is in PATH, then retry

---

## Step 5: Initialize in Project Directory

Navigate to the user's project directory (if not already there), then run:

```bash
ch init
```

**What this creates:**
- `.context-harness/` — Session storage directory
- `.opencode/agent/` — Agent definitions for OpenCode
- `.opencode/command/` — Slash command definitions

**Expected output**: Success message indicating files were created.

**Options** (if needed):
- `ch init --force` — Overwrite existing files
- `ch init --target ./path` — Install in a specific directory

---

## Step 6: Success Confirmation

If all steps completed successfully, tell the user:

> **ContextHarness installed successfully!**
> 
> - CLI version: [version from step 4]
> - Project initialized: `.context-harness/` directory created
> 
> **Next steps:**
> 1. Run `/baseline` in OpenCode to analyze your project
> 2. Run `/ctx my-feature` to start your first session
> 
> See the [documentation](https://co-labs-co.github.io/context-harness/) for more details.

---

## Troubleshooting

### "command not found: ch"

The uv tool bin directory is not in PATH. Fix with:

```bash
# Add to PATH (add this to your shell profile for persistence)
export PATH="$HOME/.local/bin:$PATH"

# Then verify
ch --version
```

### "Python version too old"

Install a newer Python version:
- **macOS**: `brew install python@3.12`
- **Ubuntu/Debian**: `sudo apt install python3.12`
- **Windows**: Download from https://python.org

### "Permission denied" errors

Ensure you're not running as root. uv tools install to the user's home directory.

### "uv: command not found" after installation

The installer may have added uv to a PATH that isn't loaded. Try:
```bash
source ~/.bashrc  # or ~/.zshrc, ~/.profile
```

Or restart your terminal/shell.

### Already have context-harness installed?

To upgrade to the latest version:
```bash
uv tool upgrade context-harness
```

To uninstall:
```bash
uv tool uninstall context-harness
```

---

## Optional: Add MCP Servers

For enhanced documentation lookup features, add Context7:

```bash
ch mcp add context7
```

For higher rate limits, add with an API key:
```bash
ch mcp add context7 -k YOUR_API_KEY
```

---

## Optional: Verify GitHub Integration

If the user wants GitHub features (`/issue`, `/pr`, `/ctx` branch creation), verify `gh` CLI:

```bash
gh auth status
```

- If **authenticated**: GitHub features will work
- If **not authenticated**: Run `gh auth login` or inform user that GitHub features require authentication

---

EXECUTE NOW: Complete the TODO list above. Goal: `ch --version` outputs a version AND `ch init` succeeds in the user's project directory.
