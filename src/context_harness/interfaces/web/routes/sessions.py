"""Sessions API routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from context_harness.interfaces.web.deps import get_working_dir

router = APIRouter()


# Pydantic models for API requests/responses
class SessionResponse(BaseModel):
    """Session data response."""

    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    compaction_cycle: int
    active_work: Optional[str] = None
    key_files_count: int = 0
    decisions_count: int = 0

    class Config:
        """Pydantic config."""

        from_attributes = True


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: List[SessionResponse]
    total: int


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    name: str
    description: Optional[str] = None


class SessionDetailResponse(BaseModel):
    """Detailed session response."""

    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    compaction_cycle: int
    active_work: Optional[str] = None
    key_files: List[Dict[str, Any]]
    decisions: List[Dict[str, Any]]
    documentation_refs: List[Dict[str, Any]]
    next_steps: List[str]
    notes: Optional[str] = None


def get_sessions_dir(working_dir: Path) -> Path:
    """Get the sessions directory path."""
    return working_dir / ".context-harness" / "sessions"


def parse_session_md(session_path: Path) -> Dict[str, Any]:
    """Parse a SESSION.md file into a dictionary.

    This is a simplified parser that extracts key information
    from the markdown structure.
    """
    if not session_path.exists():
        return {}

    content = session_path.read_text()
    lines = content.split("\n")

    result: Dict[str, Any] = {
        "id": session_path.parent.name,
        "name": session_path.parent.name,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "compaction_cycle": 0,
        "active_work": None,
        "key_files": [],
        "decisions": [],
        "documentation_refs": [],
        "next_steps": [],
        "notes": None,
    }

    # Simple parsing - look for key patterns
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Parse metadata
        if line_stripped.startswith("**Session**:"):
            result["name"] = line_stripped.replace("**Session**:", "").strip()
        elif line_stripped.startswith("**Last Updated**:"):
            result["updated_at"] = line_stripped.replace(
                "**Last Updated**:", ""
            ).strip()
        elif line_stripped.startswith("**Compaction Cycle**:"):
            try:
                cycle_str = line_stripped.replace("**Compaction Cycle**:", "").strip()
                result["compaction_cycle"] = int(cycle_str.replace("#", ""))
            except ValueError:
                pass
        elif line_stripped.startswith("**Session Started**:"):
            result["created_at"] = line_stripped.replace(
                "**Session Started**:", ""
            ).strip()
        elif line_stripped.startswith("**Current Task**:"):
            result["active_work"] = line_stripped.replace(
                "**Current Task**:", ""
            ).strip()
        elif line_stripped.startswith("**Status**:"):
            status_val = line_stripped.replace("**Status**:", "").strip().lower()
            if status_val in ["active", "completed", "blocked", "archived"]:
                result["status"] = status_val

    return result


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    working_dir: Path = Depends(get_working_dir),
) -> SessionListResponse:
    """List all available sessions.

    Returns:
        List of sessions with summary information
    """
    sessions_dir = get_sessions_dir(working_dir)

    if not sessions_dir.exists():
        return SessionListResponse(sessions=[], total=0)

    sessions = []
    for session_path in sessions_dir.iterdir():
        if session_path.is_dir():
            session_md = session_path / "SESSION.md"
            if session_md.exists():
                data = parse_session_md(session_md)
                sessions.append(
                    SessionResponse(
                        id=data["id"],
                        name=data["name"],
                        status=data["status"],
                        created_at=data["created_at"],
                        updated_at=data["updated_at"],
                        compaction_cycle=data["compaction_cycle"],
                        active_work=data["active_work"],
                        key_files_count=len(data["key_files"]),
                        decisions_count=len(data["decisions"]),
                    )
                )

    # Sort by updated_at (most recent first)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)

    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    working_dir: Path = Depends(get_working_dir),
) -> SessionDetailResponse:
    """Get detailed information about a specific session.

    Args:
        session_id: The session identifier

    Returns:
        Detailed session information
    """
    sessions_dir = get_sessions_dir(working_dir)
    session_path = sessions_dir / session_id / "SESSION.md"

    if not session_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    data = parse_session_md(session_path)

    return SessionDetailResponse(
        id=data["id"],
        name=data["name"],
        status=data["status"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        compaction_cycle=data["compaction_cycle"],
        active_work=data["active_work"],
        key_files=data["key_files"],
        decisions=data["decisions"],
        documentation_refs=data["documentation_refs"],
        next_steps=data["next_steps"],
        notes=data["notes"],
    )


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    working_dir: Path = Depends(get_working_dir),
) -> SessionResponse:
    """Create a new session.

    Args:
        request: Session creation request

    Returns:
        Created session information
    """
    sessions_dir = get_sessions_dir(working_dir)
    session_id = request.name.lower().replace(" ", "-")
    session_path = sessions_dir / session_id

    if session_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session '{session_id}' already exists",
        )

    # Create session directory
    session_path.mkdir(parents=True, exist_ok=True)

    # Create SESSION.md from template
    now = datetime.now().isoformat()
    session_md_content = f"""# ContextHarness Session

**Session**: {request.name}
**Last Updated**: {now}
**Compaction Cycle**: #0
**Session Started**: {now}

---

## Active Work

**Current Task**: {request.description or "None yet"}
**Status**: Active
**Description**: {request.description or "Session just started"}
**Blockers**: None

---

## Key Files

No files modified yet.

| File | Purpose | Status |
|------|---------|--------|
| - | - | - |

---

## Decisions Made

No decisions recorded yet.

| Decision | Choice | Rationale | Date |
|----------|--------|-----------|------|
| - | - | - | - |

---

## Documentation References

No documentation referenced yet.

| Title | URL | Relevance |
|-------|-----|-----------|
| - | - | - |

---

## Next Steps

1. Define initial task or feature
2. Begin work

---

## Completed This Session

<details>
<summary>Archived Work (Expand to view)</summary>

No completed work yet.

</details>

---

## Notes

Session `{request.name}` created via Web UI.

---

_Auto-updated by ContextHarness_
"""

    session_md_path = session_path / "SESSION.md"
    session_md_path.write_text(session_md_content)

    return SessionResponse(
        id=session_id,
        name=request.name,
        status="active",
        created_at=now,
        updated_at=now,
        compaction_cycle=0,
        active_work=request.description,
        key_files_count=0,
        decisions_count=0,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    working_dir: Path = Depends(get_working_dir),
) -> None:
    """Delete a session (archives it).

    Args:
        session_id: The session identifier
    """
    sessions_dir = get_sessions_dir(working_dir)
    session_path = sessions_dir / session_id

    if not session_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    # For now, we actually delete. In the future, we might archive instead.
    import shutil

    shutil.rmtree(session_path)
