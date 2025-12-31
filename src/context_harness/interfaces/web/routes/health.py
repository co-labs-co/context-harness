"""Health check routes."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status with timestamp
    """
    return {
        "status": "healthy",
        "service": "context-harness-web",
        "timestamp": datetime.now().isoformat(),
    }
