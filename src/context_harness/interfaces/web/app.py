"""FastAPI application for ContextHarness Web UI.

This module creates and configures the FastAPI application that serves
as the backend for the ContextHarness web interface, including static
file serving for the frontend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from context_harness.installer import (
    install_framework,
    InstallResult,
    verify_installation,
)
from context_harness.interfaces.web.routes import chat, health, sessions, themes
from context_harness.services.theme_service import ThemeService

logger = logging.getLogger(__name__)


def get_static_dir() -> Optional[Path]:
    """Get the path to the static frontend files.

    Returns the path to the built Next.js static export, or None if not found.
    Checks multiple locations in order of preference:
    1. Package directory (for installed packages)
    2. web/out in repo root (for development)
    """
    package_dir = Path(__file__).parent

    # Check for static files in package directory (installed package)
    static_dir = package_dir / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        return static_dir

    # Fallback: check for static files in web/out (development from repo)
    # Walk up to find repo root (look for pyproject.toml)
    current = package_dir
    for _ in range(10):  # Limit search depth
        if (current / "pyproject.toml").exists():
            dev_static_dir = current / "web" / "out"
            if dev_static_dir.exists() and (dev_static_dir / "index.html").exists():
                return dev_static_dir
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def ensure_context_harness_initialized(working_dir: Path) -> bool:
    """Ensure ContextHarness framework files are installed in the working directory.

    This runs `context-harness init` logic to ensure the .context-harness/ and
    .opencode/agent/ directories exist with all necessary files.

    Args:
        working_dir: The working directory to initialize

    Returns:
        True if initialization succeeded or already exists, False on error
    """
    # Check if already installed
    if verify_installation(str(working_dir)):
        logger.debug(f"ContextHarness already initialized in {working_dir}")
        return True

    # Run initialization
    logger.info(f"Initializing ContextHarness in {working_dir}...")
    result = install_framework(str(working_dir), force=False, quiet=True)

    if result == InstallResult.SUCCESS:
        logger.info("ContextHarness initialized successfully")
        return True
    elif result == InstallResult.ALREADY_EXISTS:
        # Partial installation exists, try with force to update
        logger.info("Updating existing ContextHarness installation...")
        result = install_framework(str(working_dir), force=True, quiet=True)
        return result == InstallResult.SUCCESS
    else:
        logger.error("Failed to initialize ContextHarness")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    working_dir = getattr(app.state, "working_dir", Path.cwd())

    # Ensure ContextHarness is initialized in the working directory
    if not ensure_context_harness_initialized(working_dir):
        print("⚠️  Warning: Could not initialize ContextHarness framework files")
        print("   Run 'context-harness init' manually to set up the framework")

    static_dir = get_static_dir()
    if static_dir:
        print(
            f"🚀 ContextHarness Web UI starting (serving frontend from {static_dir})..."
        )
    else:
        print("🚀 ContextHarness Web UI starting (API only, no frontend found)...")
        print("   Run 'cd web && npm run build' to build the frontend.")
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

    # Initialize theme service
    theme_service = ThemeService()
    app.state.theme_service = theme_service

    # Include API routers FIRST (before static files catch-all)
    app.include_router(health.router, tags=["health"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(themes.create_theme_router(theme_service), tags=["themes"])

    # Serve static frontend files
    static_dir = get_static_dir()
    if static_dir:
        # Mount static assets (JS, CSS, images)
        next_static = static_dir / "_next"
        if next_static.exists():
            app.mount(
                "/_next", StaticFiles(directory=str(next_static)), name="next-static"
            )

        # Serve index.html for the root path
        @app.get("/", response_class=HTMLResponse)
        async def serve_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path, media_type="text/html")
            return HTMLResponse(
                "<h1>Frontend not built</h1><p>Run: cd web && npm run build</p>"
            )

        # Catch-all for SPA routing - serve index.html for non-API routes
        @app.get("/{path:path}")
        async def serve_spa(request: Request, path: str):
            # Don't intercept API routes or health checks
            if (
                path.startswith("api/")
                or path == "health"
                or path == "docs"
                or path == "openapi.json"
            ):
                return None

            # Check if it's a static file request
            static_file = static_dir / path
            if static_file.exists() and static_file.is_file():
                return FileResponse(static_file)

            # Check for path with .html extension (Next.js static export)
            html_file = static_dir / f"{path}.html"
            if html_file.exists():
                return FileResponse(html_file, media_type="text/html")

            # Check for path/index.html (Next.js static export with trailingSlash)
            index_file = static_dir / path / "index.html"
            if index_file.exists():
                return FileResponse(index_file, media_type="text/html")

            # Fallback to index.html for SPA routing
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path, media_type="text/html")

            return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    return app


# Create default app instance for uvicorn
app = create_app()
