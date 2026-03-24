#!/usr/bin/env python3
"""Rebuild skills.json from skill directories.

Parses SKILL.md frontmatter and version.txt for each skill,
then writes the consolidated skills.json registry manifest.
Also generates .listing.json for each skill for frontend file discovery.

Usage:
    python scripts/sync-registry.py
"""

import hashlib
import json
from pathlib import Path

import frontmatter


def build_listing(skill_dir: Path) -> dict:
    """Build .listing.json for a skill directory."""
    listing = {
        "files": [],
        "directories": [],
        "directory_files": {},
    }

    skip_names = {".listing.json", ".gitkeep", ".DS_Store", "__pycache__"}

    for item in skill_dir.iterdir():
        if item.name in skip_names:
            continue

        if item.is_file():
            listing["files"].append(item.name)
        elif item.is_dir():
            listing["directories"].append(item.name)
            dir_files = []
            for subitem in item.iterdir():
                if subitem.name not in skip_names and subitem.is_file():
                    dir_files.append(subitem.name)
            if dir_files:
                listing["directory_files"][item.name] = sorted(dir_files)

    listing["files"] = sorted(listing["files"])
    listing["directories"] = sorted(listing["directories"])

    return listing


def build_registry() -> dict:
    """Scan skill/ directories and build registry manifest."""
    skills_dir = Path("skill")
    skills = []

    if not skills_dir.exists():
        return {"schema_version": "1.0", "skills": []}

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        version_txt = skill_dir / "version.txt"

        if not skill_md.exists():
            continue

        # Parse frontmatter
        post = frontmatter.load(str(skill_md))
        metadata = post.metadata

        # Read version from version.txt (fall back to 0.1.0)
        version = "0.1.0"
        if version_txt.exists():
            version = version_txt.read_text().strip()

        # Compute content hash for change detection
        content_hash = hashlib.sha256(skill_md.read_bytes()).hexdigest()[:16]

        skills.append(
            {
                "name": metadata.get("name", skill_dir.name),
                "description": metadata.get("description", ""),
                "version": version,
                "author": metadata.get("author", ""),
                "tags": metadata.get("tags", []),
                "path": f"skill/{skill_dir.name}",
                "min_context_harness_version": metadata.get(
                    "min_context_harness_version"
                ),
                "content_hash": content_hash,
            }
        )

        # Generate .listing.json for frontend file discovery
        listing = build_listing(skill_dir)
        (skill_dir / ".listing.json").write_text(
            json.dumps(listing, indent=2) + "\n", encoding="utf-8"
        )

    return {"schema_version": "1.0", "skills": skills}


def update_marketplace_json(skills: list) -> None:
    """Update marketplace.json with current skills list.

    The marketplace.json provides a standardized format for plugin
    marketplace discovery, It's regenerated alongside skills.json
    whenever skills are updated.
    """
    import os

    # Determine registry URL from environment or default
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    registry_url = ""
    if repo:
        parts = repo.split("/")
        if len(parts) == 2:
            owner, name = parts
            registry_url = f"https://{owner}.github.io/{name}"

    # Load existing marketplace.json to preserve metadata
    marketplace_path = Path("marketplace.json")
    if marketplace_path.exists():
                try:
                    existing = json.loads(marketplace_path.read_text())
                except json.JSONDecodeError:
                    existing = {}
    else:
        existing = {}

    # Update skills list while preserving other fields
    marketplace = {
        "$schema": "https://context-harness.dev/schemas/marketplace.json",
        "schema_version": existing.get("schema_version", "1.0"),
        "name": existing.get("name", repo),
        "display_name": existing.get("display_name", f"{repo.split('/')[-1]} Skills Registry" if repo else "Skills Registry"),
        "description": existing.get("description", "ContextHarness skills registry with versioned skills"),
        "registry_type": "context-harness",
        "registry_url": existing.get("registry_url", registry_url),
        "skills_endpoint": "/skills.json",
        "skill_base_path": "/skill",
        "website": existing.get("website", f"https://github.com/{repo}" if repo else ""),
        "maintainer": existing.get("maintainer", {}),
        "compatibility": existing.get("compatibility", {
            "context_harness": ">=0.5.0",
            "claude_code": ">=1.0.0",
        }),
        "skills": skills,
    }

    marketplace_path.write_text(
        json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Updated marketplace.json with {len(skills)} skill(s)")


def main() -> None:
    """Rebuild and write skills.json and marketplace.json."""
    registry = build_registry()

    Path("skills.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Updated skills.json with {len(registry['skills'])} skill(s)")
    for skill in registry["skills"]:
        print(f"  - {skill['name']} v{skill['version']}")

    # Also update marketplace.json
    update_marketplace_json(registry["skills"])


if __name__ == "__main__":
    main()
