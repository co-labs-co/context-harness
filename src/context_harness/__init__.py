"""ContextHarness CLI - Initialize agent frameworks in your project."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("context-harness")
except PackageNotFoundError:
    # Package is not installed (running from source without install)
    __version__ = "0.0.0+unknown"
