"""Web interface for ContextHarness.

This package provides a FastAPI-based web interface for managing
ContextHarness sessions, chatting with agents, and voice input.
"""

from context_harness.interfaces.web.app import create_app

__all__ = ["create_app"]
