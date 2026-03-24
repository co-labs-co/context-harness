#!/usr/bin/env python3
"""Validate skill directories for CI checks.

Checks:
- SKILL.md exists and has valid frontmatter
- name field matches directory name
- No version field in frontmatter (managed by release-please)
- version.txt exists
- No duplicate skill names
- Tags are a list of strings

Writes validation-report.md for PR comment integration.

Usage:
    python scripts/validate_skills.py
"""

import sys
from pathlib import Path
from typing import List

import frontmatter
from pydantic import BaseModel, field_validator


class SkillFrontmatter(BaseModel):
    """Expected SKILL.md frontmatter schema."""

    name: str
    description: str
    author: str = ""
    tags: List[str] = []
    min_context_harness_version: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: object) -> List[str]:
        """Ensure tags is a list of strings."""
        if not isinstance(v, list):
            msg = "tags must be a list"
            raise ValueError(msg)
        for tag in v:
            if not isinstance(tag, str):
                msg = f"tag must be a string, got {type(tag).__name__}"
                raise ValueError(msg)
        return v


def validate_skill(skill_dir: Path) -> List[str]:
    """Validate a single skill directory. Returns list of errors."""
    errors: List[str] = []
    skill_name = skill_dir.name

    # Check SKILL.md exists
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{skill_name}: missing SKILL.md")
        return errors

    # Parse frontmatter
    try:
        post = frontmatter.load(str(skill_md))
        metadata = post.metadata
    except Exception as e:
        errors.append(f"{skill_name}: failed to parse frontmatter: {e}")
        return errors

    # Validate schema
    try:
        parsed = SkillFrontmatter(**metadata)
    except Exception as e:
        errors.append(f"{skill_name}: invalid frontmatter: {e}")
        return errors

    # Name must match directory
    if parsed.name != skill_name:
        errors.append(
            f"{skill_name}: name '{parsed.name}' does not match "
            f"directory '{skill_name}'"
        )

    # Version must NOT be in frontmatter
    if "version" in metadata:
        errors.append(
            f"{skill_name}: remove 'version' from frontmatter "
            f"(managed by release-please via version.txt)"
        )

    # version.txt must exist
    version_txt = skill_dir / "version.txt"
    if not version_txt.exists():
        errors.append(f"{skill_name}: missing version.txt (bootstrap with '0.1.0')")

    return errors


def main() -> None:
    """Validate all skills and write report."""
    skills_dir = Path("skill")
    all_errors: List[str] = []
    validated_count = 0
    skill_names: List[str] = []

    if not skills_dir.exists():
        print("No skill/ directory found")
        sys.exit(0)

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        validated_count += 1
        skill_names.append(skill_dir.name)
        errors = validate_skill(skill_dir)
        all_errors.extend(errors)

    # Check for duplicate names
    seen = set()
    for name in skill_names:
        if name in seen:
            all_errors.append(f"Duplicate skill directory: {name}")
        seen.add(name)

    # Write report
    report_lines = ["## Skill Validation Report\n"]

    if all_errors:
        report_lines.append(f"**{len(all_errors)} error(s)** "
                          f"found in {validated_count} skill(s):\n")
        for error in all_errors:
            report_lines.append(f"- ❌ {error}")
    else:
        report_lines.append(
            f"✅ **All {validated_count} skill(s) passed validation**"
        )

    report = "\n".join(report_lines) + "\n"

    Path("validation-report.md").write_text(report, encoding="utf-8")

    print(report)

    if all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
