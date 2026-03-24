# Contributing to co-labs-co/context-harness

## Adding a New Skill

1. **Create the skill directory**:
   ```bash
   mkdir -p skill/my-skill
   ```

2. **Create SKILL.md** with frontmatter (no version field!):
   ```markdown
   ---
   name: my-skill
   description: Brief description of what this skill does
   author: your-name
   tags:
     - category
   ---

   # My Skill

   Your skill content here...
   ```

3. **Create version.txt** (bootstrapped at 0.1.0):
   ```bash
   echo "0.1.0" > skill/my-skill/version.txt
   ```

4. **Register with release-please** — add to `release-please-config.json`:
   ```json
   {
     "packages": {
       "skill/my-skill": {
         "release-type": "simple",
         "component": "my-skill"
       }
     }
   }
   ```

   And to `.release-please-manifest.json`:
   ```json
   {
     "skill/my-skill": "0.1.0"
   }
   ```

5. **Commit and push**:
   ```bash
   git add skill/my-skill/ release-please-config.json .release-please-manifest.json
   git commit -m "feat: add my-skill"
   git push origin main
   ```

## Updating a Skill

1. Edit the skill's `SKILL.md` file
2. Commit with a conventional commit message:
   - `fix: correct typo in examples` → patch bump
   - `feat: add new section on error handling` → minor bump
   - `feat!: restructure skill format` → major bump
3. Push and merge your PR
4. release-please will automatically create a release PR

## Important Notes

- **Never edit `version.txt` manually** — release-please manages it
- **Never edit `skills.json` manually** — CI rebuilds it after releases
- **Never add `version` to SKILL.md frontmatter** — it lives in `version.txt`
- The `name` field in SKILL.md **must match** the directory name
