"""Storage package for ContextHarness.

This package provides storage abstractions for file operations,
enabling dependency injection and testability across all services.

Architecture:
    StorageProtocol (Protocol) - Abstract interface for storage operations
    FileStorage - Real filesystem implementation
    MemoryStorage - In-memory implementation for testing

Example:
    from context_harness.storage import StorageProtocol, FileStorage, MemoryStorage

    # Production code
    storage = FileStorage()
    storage.write("config.json", '{"key": "value"}')

    # Test code
    storage = MemoryStorage()
    storage.write("config.json", '{"key": "value"}')
    assert storage.read("config.json") == '{"key": "value"}'
"""

from context_harness.storage.protocol import StorageProtocol
from context_harness.storage.file_storage import FileStorage
from context_harness.storage.memory_storage import MemoryStorage

__all__ = [
    "StorageProtocol",
    "FileStorage",
    "MemoryStorage",
]
