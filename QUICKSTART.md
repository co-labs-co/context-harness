# Quick Start: Add Your First Skill

This guide walks you through adding a skill to **co-labs-co/context-harness**.

## Prerequisites

- Git installed
- GitHub CLI (`gh`) installed and authenticated
- Repository cloned locally

## ⚠️ Required GitHub Settings

Before using this registry, configure GitHub Actions permissions:

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select **Read and write permissions**
3. Check **Allow GitHub Actions to create and approve pull requests**

Without these settings, release-please cannot create release PRs.

## Steps

### 1. Create the Skill

```bash
# Create skill directory
mkdir -p skill/my-first-skill

# Create SKILL.md
cat > skill/my-first-skill/SKILL.md << 'SKILLEOF'
---
name: my-first-skill
description: My first custom skill
author: your-name
tags:
  - getting-started
---

# My First Skill

Instructions and content for your skill go here.
SKILLEOF

# Bootstrap version (required for release-please)
echo "0.1.0" > skill/my-first-skill/version.txt
```

### 2. Register with Release-Please

Add the skill to `release-please-config.json` under `"packages"`:

```json
"skill/my-first-skill": {
  "release-type": "simple",
  "component": "my-first-skill"
}
```

Add to `.release-please-manifest.json`:

```json
"skill/my-first-skill": "0.1.0"
```

### 3. Commit and Push

```bash
git add .
git commit -m "feat: add my-first-skill"
git push origin main
```

### 4. What Happens Next

1. **release-please** creates a release PR bumping `version.txt`
2. Merge the release PR → tag `my-first-skill@v0.1.0` is created
3. **sync-registry** rebuilds `skills.json` automatically
4. Users can now install: `context-harness skill install my-first-skill`

## Install Your Skill

```bash
# Configure this registry (one time)
context-harness config set skills-repo co-labs-co/context-harness

# Install
context-harness skill install my-first-skill
```
