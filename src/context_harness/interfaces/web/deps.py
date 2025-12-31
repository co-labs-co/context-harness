"""Dependency injection for web routes."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from fastapi import Depends, Request

from context_harness.interfaces.sdk import Client


def get_working_dir(request: Request) -> Path:
    """Get the working directory from app state.

    Args:
        request: FastAPI request object

    Returns:
        Working directory path
    """
    return request.app.state.working_dir


def get_client(
    working_dir: Path = Depends(get_working_dir),
) -> Generator[Client, None, None]:
    """Get a ContextHarness SDK client.

    Args:
        working_dir: Working directory for the client

    Yields:
        Configured Client instance
    """
    client = Client(working_dir=working_dir)
    yield client
