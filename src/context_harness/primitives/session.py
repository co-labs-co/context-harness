"""Session primitives for ContextHarness.

A Session represents a unit of work context that persists across
interactions and compaction cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SessionStatus(Enum):
    """Status of a session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


@dataclass
class KeyFile:
    """A file that has been modified during the session.

    Attributes:
        path: Relative path to the file
        purpose: Description of changes/purpose
        last_modified: When the file was last modified
    """

    path: str
    purpose: str
    last_modified: Optional[datetime] = None


@dataclass
class Decision:
    """A technical decision made during the session.

    Attributes:
        summary: Brief description of the decision
        rationale: Why this decision was made
        timestamp: When the decision was made
        context: Additional context or alternatives considered
    """

    summary: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Optional[str] = None


@dataclass
class DocRef:
    """A documentation reference used during the session.

    Attributes:
        url: URL to the documentation
        title: Title or description
        usage: How the documentation was used
    """

    url: str
    title: str
    usage: Optional[str] = None


@dataclass
class CompactionCycle:
    """Record of a compaction event.

    Compaction happens every N user interactions to preserve
    context continuity across context window limits.

    Attributes:
        cycle_number: Sequential cycle number
        timestamp: When compaction occurred
        user_interaction_count: Interaction count at compaction
        preserved_items: Summary of what was preserved
    """

    cycle_number: int
    timestamp: datetime
    user_interaction_count: int
    preserved_items: List[str] = field(default_factory=list)


@dataclass
class Session:
    """A ContextHarness session representing a unit of work.

    Sessions persist context across interactions and compaction cycles.
    They are stored as SESSION.md files in the .context-harness/sessions/
    directory.

    Attributes:
        id: Unique identifier (directory name, e.g., "login-feature")
        name: Human-readable name
        status: Current session status
        created_at: When the session was created
        updated_at: Last update timestamp
        compaction_cycle: Current cycle number
        active_work: Current task description
        key_files: Modified files with descriptions
        decisions: Technical decisions made
        documentation_refs: Documentation links used
        next_steps: Action items
        notes: Additional session notes
    """

    id: str
    name: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    compaction_cycle: int = 0
    active_work: Optional[str] = None
    key_files: List[KeyFile] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    documentation_refs: List[DocRef] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def increment_cycle(self) -> int:
        """Increment the compaction cycle and return the new number."""
        self.compaction_cycle += 1
        self.touch()
        return self.compaction_cycle

    def add_key_file(self, path: str, purpose: str) -> KeyFile:
        """Add a key file to the session.

        Args:
            path: File path
            purpose: Description of changes

        Returns:
            The created KeyFile
        """
        key_file = KeyFile(path=path, purpose=purpose, last_modified=datetime.now())
        self.key_files.append(key_file)
        self.touch()
        return key_file

    def add_decision(
        self, summary: str, rationale: str, context: Optional[str] = None
    ) -> Decision:
        """Add a decision to the session.

        Args:
            summary: Brief decision summary
            rationale: Why the decision was made
            context: Additional context

        Returns:
            The created Decision
        """
        decision = Decision(summary=summary, rationale=rationale, context=context)
        self.decisions.append(decision)
        self.touch()
        return decision

    def add_doc_ref(self, url: str, title: str, usage: Optional[str] = None) -> DocRef:
        """Add a documentation reference.

        Args:
            url: Documentation URL
            title: Title or description
            usage: How it was used

        Returns:
            The created DocRef
        """
        doc_ref = DocRef(url=url, title=title, usage=usage)
        self.documentation_refs.append(doc_ref)
        self.touch()
        return doc_ref
