"""Unit tests for SDK client."""

from pathlib import Path
from tempfile import TemporaryDirectory

from context_harness.interfaces.sdk import Client, create_client
from context_harness.interfaces.sdk.client import (
    ConfigClient,
    MCPClient,
    OAuthClient,
    SkillClient,
)
from context_harness.primitives import Failure, OpenCodeConfig, Success
from context_harness.storage import FileStorage, MemoryStorage


class TestClient:
    """Tests for the main SDK Client class."""

    def test_client_initialization_defaults(self) -> None:
        """Test Client initializes with defaults."""
        client = Client()
        assert client.working_dir == Path.cwd()
        assert isinstance(client.storage, FileStorage)

    def test_client_initialization_custom_working_dir(self) -> None:
        """Test Client initializes with custom working directory."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            assert client.working_dir == working_dir

    def test_client_initialization_with_memory_storage(self) -> None:
        """Test Client initializes with memory storage."""
        storage = MemoryStorage()
        client = Client(storage=storage)
        assert client.storage is storage

    def test_client_has_sub_clients(self) -> None:
        """Test Client has all sub-clients."""
        client = Client()
        assert isinstance(client.config, ConfigClient)
        assert isinstance(client.mcp, MCPClient)
        assert isinstance(client.oauth, OAuthClient)
        assert isinstance(client.skills, SkillClient)

    def test_client_create_classmethod(self) -> None:
        """Test Client.create() classmethod."""
        client = Client.create()
        assert isinstance(client, Client)

    def test_client_create_with_memory_storage(self) -> None:
        """Test Client.create() with memory storage."""
        client = Client.create(use_memory_storage=True)
        assert isinstance(client.storage, MemoryStorage)

    def test_client_create_with_working_dir(self) -> None:
        """Test Client.create() with custom working directory."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client.create(working_dir=working_dir)
            assert client.working_dir == working_dir


class TestCreateClient:
    """Tests for the create_client convenience function."""

    def test_create_client_defaults(self) -> None:
        """Test create_client with defaults."""
        client = create_client()
        assert isinstance(client, Client)
        assert client.working_dir == Path.cwd()

    def test_create_client_with_memory_storage(self) -> None:
        """Test create_client with memory storage."""
        client = create_client(use_memory_storage=True)
        assert isinstance(client.storage, MemoryStorage)

    def test_create_client_with_working_dir(self) -> None:
        """Test create_client with custom working directory."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = create_client(working_dir=working_dir)
            assert client.working_dir == working_dir


class TestConfigClient:
    """Tests for ConfigClient."""

    def test_config_path(self) -> None:
        """Test config_path property."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            expected = working_dir / "opencode.json"
            assert client.config.config_path == expected

    def test_exists_returns_false_when_missing(self) -> None:
        """Test exists returns False when config doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            assert client.config.exists() is False

    def test_load_returns_failure_when_missing(self) -> None:
        """Test load returns Failure when config doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            result = client.config.load()
            assert isinstance(result, Failure)

    def test_save_and_load_roundtrip(self) -> None:
        """Test save and load work together."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)

            # Create and save config
            config = OpenCodeConfig()
            save_result = client.config.save(config)
            assert isinstance(save_result, Success)

            # Verify exists
            assert client.config.exists() is True

            # Load and verify
            load_result = client.config.load()
            assert isinstance(load_result, Success)
            assert isinstance(load_result.value, OpenCodeConfig)

    def test_exists_returns_true_after_save(self) -> None:
        """Test exists returns True after save."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)

            # Save config
            config = OpenCodeConfig()
            client.config.save(config)

            # Verify exists
            assert client.config.exists() is True


class TestMCPClient:
    """Tests for MCPClient."""

    def test_list_available_returns_result(self) -> None:
        """Test list_available returns a Result."""
        client = Client()
        result = client.mcp.list_available()
        # Should return Success with list of servers from mock registry
        assert isinstance(result, (Success, Failure))

    def test_search_returns_result(self) -> None:
        """Test search returns a Result."""
        client = Client()
        result = client.mcp.search("context7")
        assert isinstance(result, (Success, Failure))

    def test_get_returns_result(self) -> None:
        """Test get returns a Result."""
        client = Client()
        result = client.mcp.get("context7")
        # Could be Success or Failure depending on mock registry
        assert isinstance(result, (Success, Failure))


class TestOAuthClient:
    """Tests for OAuthClient."""

    def test_get_status_returns_result(self) -> None:
        """Test get_status returns a Result."""
        client = Client()
        result = client.oauth.get_status("atlassian")
        assert isinstance(result, (Success, Failure))

    def test_logout_returns_result(self) -> None:
        """Test logout returns a Result."""
        client = Client()
        result = client.oauth.logout("atlassian")
        assert isinstance(result, (Success, Failure))


class TestSkillClient:
    """Tests for SkillClient."""

    def test_skills_dir_property(self) -> None:
        """Test skills_dir property."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            expected = working_dir / ".opencode" / "skill"
            assert client.skills.skills_dir == expected

    def test_list_local_returns_result(self) -> None:
        """Test list_local returns a Result."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)
            result = client.skills.list_local()
            assert isinstance(result, (Success, Failure))

    def test_list_remote_returns_result(self) -> None:
        """Test list_remote returns a Result."""
        client = Client()
        result = client.skills.list_remote()
        # Will fail without gh auth, but should return Result
        assert isinstance(result, (Success, Failure))

    def test_get_returns_result(self) -> None:
        """Test get returns a Result."""
        client = Client()
        result = client.skills.get("nonexistent")
        # Will fail without gh auth, but should return Result
        assert isinstance(result, (Success, Failure))


class TestClientIntegration:
    """Integration tests for SDK Client."""

    def test_full_workflow_with_temp_dir(self) -> None:
        """Test full workflow with temporary directory."""
        with TemporaryDirectory() as tmpdir:
            working_dir = Path(tmpdir)
            client = Client(working_dir=working_dir)

            # 1. Config doesn't exist initially
            assert client.config.exists() is False

            # 2. Create and save config
            config = OpenCodeConfig()
            save_result = client.config.save(config)
            assert isinstance(save_result, Success)

            # 3. Config exists now
            assert client.config.exists() is True

            # 4. Load config
            load_result = client.config.load()
            assert isinstance(load_result, Success)

    def test_client_with_memory_storage_for_testing(self) -> None:
        """Test client with memory storage is suitable for testing."""
        # Create client with memory storage
        client = Client.create(use_memory_storage=True)

        # Memory storage should work for client operations
        assert isinstance(client.storage, MemoryStorage)
        assert client.config is not None
        assert client.mcp is not None
        assert client.oauth is not None
        assert client.skills is not None
