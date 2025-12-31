"""FastAPI application for ContextHarness Web UI.

This module creates and configures the FastAPI application that serves
as the backend for the ContextHarness web interface.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from context_harness.interfaces.web.routes import chat, health, sessions


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    print("🚀 ContextHarness Web UI starting...")
    yield
    # Shutdown
    print("👋 ContextHarness Web UI shutting down...")


def create_app(
    working_dir: Optional[Path] = None,
    debug: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        working_dir: Working directory for ContextHarness operations.
                    Defaults to current working directory.
        debug: Enable debug mode with additional logging.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="ContextHarness Web UI",
        description="Web interface for managing ContextHarness sessions and agents",
        version="0.1.0",
        lifespan=lifespan,
        debug=debug,
    )

    # Store working directory in app state
    app.state.working_dir = working_dir or Path.cwd()

    # Configure CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Next.js dev server
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

    return app


# Create default app instance for uvicorn
app = create_app()
