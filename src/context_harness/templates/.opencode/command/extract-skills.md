---
description: Extract a local skill and create a PR to the central skills repository
agent: context-harness
---

Extract skill: $ARGUMENTS

## Instructions

### Parse Arguments

Extract the skill name from `$ARGUMENTS`. The skill name should be:
- Lowercase with hyphens (kebab-case)
- A valid directory name under `.opencode/skill/`

Examples:
- `/extract-skills my-custom-skill`
- `/extract-skills react-forms`

### Prerequisites

1. **Check skill exists locally**:
   - Look for `.opencode/skill/$SKILL_NAME/SKILL.md`
   - If not found, error: "Skill '$SKILL_NAME' not found at .opencode/skill/$SKILL_NAME/"

2. **Check GitHub authentication**:
   - Run `gh auth status`
   - If not authenticated, error: "GitHub CLI not authenticated. Run 'gh auth login' first."

3. **Check skills repository access**:
   - Run `gh api /repos/cmtzco/context-harness-skills --silent`
   - If access denied, error: "Cannot access skills repository. Contact the maintainers for access."

### Validation

Before extraction, validate the skill:

1. **SKILL.md exists** with valid frontmatter:
   - Must have `name:` field
   - Must have `description:` field

2. **Skill structure is valid**:
   - Optional: `references/` directory
   - Optional: `scripts/` directory  
   - Optional: `assets/` directory

### Extraction Process

1. **Clone skills repository** (shallow):
   ```bash
   gh repo clone cmtzco/context-harness-skills /tmp/skills-extract -- --depth=1
   ```

2. **Create feature branch**:
   ```bash
   git -C /tmp/skills-extract checkout -b skill/$SKILL_NAME-$(date +%Y%m%d-%H%M%S)
   ```

3. **Copy skill files**:
   - Source: `.opencode/skill/$SKILL_NAME/`
   - Destination: `/tmp/skills-extract/skill/$SKILL_NAME/`

4. **Update skills.json registry**:
   - Add or update entry for the skill
   - Include: name, description, version, author, tags, path

5. **Commit and push**:
   ```bash
   git -C /tmp/skills-extract add .
   git -C /tmp/skills-extract commit -m "feat(skill): add $SKILL_NAME"
   git -C /tmp/skills-extract push -u origin HEAD
   ```

6. **Create pull request**:
   ```bash
   gh pr create --repo cmtzco/context-harness-skills \
     --title "Add skill: $SKILL_NAME" \
     --body "[PR body with skill details]"
   ```

### Output

On success:
```
✅ Pull request created successfully!

🔗 [PR URL]

The PR includes:
- skill/$SKILL_NAME/SKILL.md
- [list of other files]

Review and merge the PR to publish your skill to the central repository.
```

On error:
```
❌ Failed to extract skill: [reason]

[Troubleshooting guidance based on error type]
```

### Alternative: CLI Command

Users can also extract skills via the CLI:

```bash
context-harness skill extract $SKILL_NAME
context-harness skill extract $SKILL_NAME --source ./path/to/project
```

## Related Commands

- `/ctx` - Start or switch sessions
- `context-harness skill list` - List available skills
- `context-harness skill install` - Install skills from repository
