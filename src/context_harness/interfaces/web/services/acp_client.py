"""ACP (Agent Client Protocol) client for OpenCode integration.

This module provides a Python client for communicating with OpenCode via the
Agent Client Protocol (ACP). ACP uses JSON-RPC 2.0 over stdio for communication
between code editors/clients and AI coding agents.

Protocol reference: https://agentclientprotocol.com

Protocol flow:
1. Initialize connection (negotiate version and capabilities)
2. Create session with working directory and MCP servers
3. Send prompts and receive streamed updates via notifications
4. Handle tool calls and permission requests
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class ACPError(Exception):
    """Base exception for ACP errors."""

    def __init__(
        self, message: str, code: Optional[int] = None, data: Optional[Any] = None
    ):
        super().__init__(message)
        self.code = code
        self.data = data


class ACPConnectionError(ACPError):
    """Error connecting to or communicating with the ACP agent."""

    pass


class ACPTimeoutError(ACPError):
    """Timeout waiting for ACP response."""

    pass


class ACPProtocolError(ACPError):
    """Protocol-level error (invalid JSON-RPC, version mismatch, etc.)."""

    pass


# =============================================================================
# Protocol Types
# =============================================================================


class StopReason(str, Enum):
    """Reasons why an agent turn may stop."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    MAX_TURN_REQUESTS = "max_turn_requests"
    REFUSAL = "refusal"
    CANCELLED = "cancelled"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolKind(str, Enum):
    """Categories of tools that can be invoked."""

    READ = "read"
    EDIT = "edit"
    DELETE = "delete"
    MOVE = "move"
    SEARCH = "search"
    EXECUTE = "execute"
    THINK = "think"
    FETCH = "fetch"
    SWITCH_MODE = "switch_mode"
    OTHER = "other"


class SessionUpdateType(str, Enum):
    """Types of session updates sent by the agent."""

    USER_MESSAGE_CHUNK = "user_message_chunk"
    AGENT_MESSAGE_CHUNK = "agent_message_chunk"
    AGENT_THOUGHT_CHUNK = "agent_thought_chunk"
    TOOL_CALL = "tool_call"
    TOOL_CALL_UPDATE = "tool_call_update"
    PLAN = "plan"
    AVAILABLE_COMMANDS_UPDATE = "available_commands_update"
    CURRENT_MODE_UPDATE = "current_mode_update"


@dataclass
class ContentBlock:
    """A block of content in a message."""

    type: str  # "text", "image", "audio", "resource", "resource_link"
    text: Optional[str] = None
    data: Optional[str] = None  # base64 for binary content
    mime_type: Optional[str] = None
    uri: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {"type": self.type}
        if self.text is not None:
            result["text"] = self.text
        if self.data is not None:
            result["data"] = self.data
        if self.mime_type is not None:
            result["mimeType"] = self.mime_type
        if self.uri is not None:
            result["uri"] = self.uri
        return result


@dataclass
class ToolCallLocation:
    """A file location being accessed or modified by a tool."""

    path: str
    line: Optional[int] = None


@dataclass
class ToolCall:
    """A tool call from the agent."""

    tool_call_id: str
    title: str
    kind: Optional[ToolKind] = None
    status: ToolCallStatus = ToolCallStatus.PENDING
    content: Optional[List[Any]] = None  # ToolCallContent[]
    locations: Optional[List[ToolCallLocation]] = None
    raw_input: Optional[Dict[str, Any]] = None
    raw_output: Optional[Dict[str, Any]] = None


@dataclass
class PlanEntry:
    """An entry in the agent's plan."""

    content: str
    priority: str  # "high", "medium", "low"
    status: str  # "pending", "in_progress", "completed"


@dataclass
class SessionMode:
    """A mode the agent can operate in."""

    id: str
    name: str
    description: Optional[str] = None


@dataclass
class SessionUpdate:
    """An update notification from the agent."""

    session_id: str
    update_type: SessionUpdateType
    # For message chunks
    content: Optional[ContentBlock] = None
    # For tool calls
    tool_call: Optional[ToolCall] = None
    # For tool call updates
    tool_call_id: Optional[str] = None
    tool_call_status: Optional[ToolCallStatus] = None
    tool_call_content: Optional[List[Any]] = None
    tool_call_title: Optional[str] = None
    # For plans
    plan: Optional[List[PlanEntry]] = None
    # For commands
    commands: Optional[List[Dict[str, Any]]] = None
    # For mode changes
    mode_id: Optional[str] = None


@dataclass
class ClientCapabilities:
    """Capabilities of the ACP client."""

    fs_read_text_file: bool = True
    fs_write_text_file: bool = True
    terminal: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fs": {
                "readTextFile": self.fs_read_text_file,
                "writeTextFile": self.fs_write_text_file,
            },
            "terminal": self.terminal,
        }


@dataclass
class AgentCapabilities:
    """Capabilities of the ACP agent."""

    load_session: bool = False
    prompt_image: bool = False
    prompt_audio: bool = False
    prompt_embedded_context: bool = False
    mcp_http: bool = False
    mcp_sse: bool = False


@dataclass
class MCPServerStdio:
    """Stdio transport configuration for MCP."""

    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "command": self.command,
            "args": self.args,
            "env": self.env,
        }


@dataclass
class ACPSession:
    """Represents an ACP session with the agent."""

    session_id: str
    modes: Optional[List[SessionMode]] = None
    current_mode_id: Optional[str] = None


# =============================================================================
# JSON-RPC Helpers
# =============================================================================


def create_request(
    method: str, params: Optional[Dict[str, Any]] = None
) -> tuple[str, Dict[str, Any]]:
    """Create a JSON-RPC 2.0 request. Returns (request_id, request_dict)."""
    request_id = str(uuid.uuid4())
    request: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params:
        request["params"] = params
    return request_id, request


def create_notification(
    method: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a JSON-RPC 2.0 notification (no id, no response expected)."""
    notification: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params:
        notification["params"] = params
    return notification


def parse_response(data: Dict[str, Any]) -> Any:
    """Parse a JSON-RPC 2.0 response."""
    if "error" in data:
        error = data["error"]
        raise ACPError(
            message=error.get("message", "Unknown error"),
            code=error.get("code"),
            data=error.get("data"),
        )
    return data.get("result")


def parse_notification(data: Dict[str, Any]) -> Optional[SessionUpdate]:
    """Parse a JSON-RPC 2.0 notification into a SessionUpdate."""
    method = data.get("method")
    params = data.get("params", {})

    if method != "session/update":
        logger.debug(f"Ignoring notification with method: {method}")
        return None

    session_id = params.get("sessionId", "")
    update = params.get("update", {})
    update_type_str = update.get("sessionUpdate", "")

    try:
        update_type = SessionUpdateType(update_type_str)
    except ValueError:
        logger.warning(f"Unknown session update type: {update_type_str}")
        return None

    session_update = SessionUpdate(
        session_id=session_id,
        update_type=update_type,
    )

    # Parse content based on update type
    if update_type in (
        SessionUpdateType.USER_MESSAGE_CHUNK,
        SessionUpdateType.AGENT_MESSAGE_CHUNK,
        SessionUpdateType.AGENT_THOUGHT_CHUNK,
    ):
        content_data = update.get("content", {})
        session_update.content = ContentBlock(
            type=content_data.get("type", "text"),
            text=content_data.get("text"),
        )

    elif update_type == SessionUpdateType.TOOL_CALL:
        kind_str = update.get("kind")
        kind = None
        if kind_str:
            try:
                kind = ToolKind(kind_str)
            except ValueError:
                kind = ToolKind.OTHER

        status_str = update.get("status", "pending")
        try:
            status = ToolCallStatus(status_str)
        except ValueError:
            status = ToolCallStatus.PENDING

        session_update.tool_call = ToolCall(
            tool_call_id=update.get("toolCallId", ""),
            title=update.get("title", ""),
            kind=kind,
            status=status,
            content=update.get("content"),
            raw_input=update.get("rawInput"),
            raw_output=update.get("rawOutput"),
        )

    elif update_type == SessionUpdateType.TOOL_CALL_UPDATE:
        session_update.tool_call_id = update.get("toolCallId")
        session_update.tool_call_title = update.get("title")

        status_str = update.get("status")
        if status_str:
            try:
                session_update.tool_call_status = ToolCallStatus(status_str)
            except ValueError:
                pass

        session_update.tool_call_content = update.get("content")

    elif update_type == SessionUpdateType.PLAN:
        entries = update.get("entries", [])
        session_update.plan = [
            PlanEntry(
                content=e.get("content", ""),
                priority=e.get("priority", "medium"),
                status=e.get("status", "pending"),
            )
            for e in entries
        ]

    elif update_type == SessionUpdateType.AVAILABLE_COMMANDS_UPDATE:
        session_update.commands = update.get("availableCommands", [])

    elif update_type == SessionUpdateType.CURRENT_MODE_UPDATE:
        session_update.mode_id = update.get("currentModeId")

    return session_update


# =============================================================================
# ACP Client
# =============================================================================


class ACPClient:
    """Client for communicating with OpenCode via ACP (Agent Client Protocol).

    This client spawns OpenCode as a subprocess running in ACP mode and
    communicates via JSON-RPC 2.0 over stdio.

    Usage:
        async with ACPClient(working_dir="/path/to/project") as client:
            session = await client.create_session()
            async for update in client.prompt(session.session_id, "Hello!"):
                print(update)
    """

    PROTOCOL_VERSION = 1

    def __init__(
        self,
        working_dir: Optional[Union[str, Path]] = None,
        opencode_path: str = "opencode",
        timeout: float = 30.0,
        capabilities: Optional[ClientCapabilities] = None,
    ):
        """Initialize the ACP client.

        Args:
            working_dir: Working directory for OpenCode (defaults to cwd)
            opencode_path: Path to opencode executable
            timeout: Default timeout for requests in seconds
            capabilities: Client capabilities to advertise
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.opencode_path = opencode_path
        self.timeout = timeout
        self.capabilities = capabilities or ClientCapabilities()

        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[str, asyncio.Future[Any]] = {}
        self._notification_handlers: List[Callable[[SessionUpdate], None]] = []
        self._initialized = False
        self._agent_capabilities: Optional[AgentCapabilities] = None
        self._agent_info: Optional[Dict[str, str]] = None
        self._write_lock = asyncio.Lock()

    async def __aenter__(self) -> "ACPClient":
        """Start the OpenCode subprocess and initialize the connection."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close the connection and terminate the subprocess."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if the client is connected and initialized."""
        return self._initialized and self._process is not None

    @property
    def agent_capabilities(self) -> Optional[AgentCapabilities]:
        """Get the agent's capabilities (available after connection)."""
        return self._agent_capabilities

    async def connect(self) -> None:
        """Start OpenCode and initialize the ACP connection."""
        if self._process is not None:
            raise ACPConnectionError("Already connected")

        logger.info(f"Starting OpenCode ACP at {self.working_dir}")

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.opencode_path,
                "acp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
            )
        except FileNotFoundError:
            raise ACPConnectionError(
                f"OpenCode not found at '{self.opencode_path}'. "
                "Please install OpenCode: https://opencode.ai/docs/"
            )
        except Exception as e:
            raise ACPConnectionError(f"Failed to start OpenCode: {e}")

        # Start background reader
        self._reader_task = asyncio.create_task(self._read_loop())

        # Initialize the connection
        await self._initialize()

    async def disconnect(self) -> None:
        """Close the connection and terminate the subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

        self._initialized = False
        self._pending_requests.clear()

    async def _initialize(self) -> None:
        """Send the initialize request to negotiate capabilities."""
        params = {
            "protocolVersion": self.PROTOCOL_VERSION,
            "clientCapabilities": self.capabilities.to_dict(),
            "clientInfo": {
                "name": "context-harness",
                "title": "ContextHarness Web UI",
                "version": "0.1.0",
            },
        }

        result = await self._send_request("initialize", params)

        # Check protocol version
        agent_version = result.get("protocolVersion", 0)
        if agent_version != self.PROTOCOL_VERSION:
            raise ACPProtocolError(
                f"Protocol version mismatch: client={self.PROTOCOL_VERSION}, "
                f"agent={agent_version}"
            )

        # Parse agent capabilities
        agent_caps = result.get("agentCapabilities", {})
        prompt_caps = agent_caps.get("promptCapabilities", {})
        mcp_caps = agent_caps.get("mcpCapabilities", {})

        self._agent_capabilities = AgentCapabilities(
            load_session=agent_caps.get("loadSession", False),
            prompt_image=prompt_caps.get("image", False),
            prompt_audio=prompt_caps.get("audio", False),
            prompt_embedded_context=prompt_caps.get("embeddedContext", False),
            mcp_http=mcp_caps.get("http", False),
            mcp_sse=mcp_caps.get("sse", False),
        )

        self._agent_info = result.get("agentInfo", {})
        self._initialized = True

        agent_name = (
            self._agent_info.get("name", "unknown") if self._agent_info else "unknown"
        )
        agent_version = (
            self._agent_info.get("version", "?") if self._agent_info else "?"
        )
        logger.info(f"ACP initialized: agent={agent_name} v{agent_version}")

    async def _send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self._process or not self._process.stdin:
            raise ACPConnectionError("Not connected")

        request_id, request = create_request(method, params)

        # Create a future for the response
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending_requests[request_id] = future

        # Calculate timeout upfront
        timeout_val = timeout if timeout is not None else self.timeout

        try:
            # Send the request
            async with self._write_lock:
                data = json.dumps(request) + "\n"
                self._process.stdin.write(data.encode())
                await self._process.stdin.drain()

            logger.debug(f"Sent request: {method} (id={request_id})")

            # Wait for the response
            result = await asyncio.wait_for(future, timeout=timeout_val)
            return result

        except asyncio.TimeoutError:
            raise ACPTimeoutError(f"Request '{method}' timed out after {timeout_val}s")

        finally:
            self._pending_requests.pop(request_id, None)

    async def _send_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            raise ACPConnectionError("Not connected")

        notification = create_notification(method, params)

        async with self._write_lock:
            data = json.dumps(notification) + "\n"
            self._process.stdin.write(data.encode())
            await self._process.stdin.drain()

        logger.debug(f"Sent notification: {method}")

    async def _read_loop(self) -> None:
        """Background task to read responses and notifications from stdout."""
        if not self._process or not self._process.stdout:
            return

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode())
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from agent: {line}")
                    continue

                # Check if it's a response or notification
                if "id" in data:
                    # It's a response
                    request_id = data["id"]
                    future = self._pending_requests.get(request_id)
                    if future and not future.done():
                        try:
                            result = parse_response(data)
                            future.set_result(result)
                        except ACPError as e:
                            future.set_exception(e)
                else:
                    # It's a notification
                    update = parse_notification(data)
                    if update:
                        for handler in self._notification_handlers:
                            try:
                                handler(update)
                            except Exception as e:
                                logger.error(f"Notification handler error: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Read loop error: {e}")

    def add_notification_handler(
        self, handler: Callable[[SessionUpdate], None]
    ) -> None:
        """Add a handler for session update notifications."""
        self._notification_handlers.append(handler)

    def remove_notification_handler(
        self, handler: Callable[[SessionUpdate], None]
    ) -> None:
        """Remove a notification handler."""
        if handler in self._notification_handlers:
            self._notification_handlers.remove(handler)

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        mcp_servers: Optional[List[MCPServerStdio]] = None,
        working_dir: Optional[Union[str, Path]] = None,
    ) -> ACPSession:
        """Create a new ACP session.

        Args:
            mcp_servers: List of MCP servers to connect to (optional)
            working_dir: Working directory for the session (defaults to client's)

        Returns:
            The created session
        """
        cwd = str(working_dir or self.working_dir)

        params: Dict[str, Any] = {
            "cwd": cwd,
            "mcpServers": [s.to_dict() for s in mcp_servers] if mcp_servers else [],
        }

        result = await self._send_request("session/new", params)

        session_id = result.get("sessionId", "")
        modes_data = result.get("modes")

        modes: Optional[List[SessionMode]] = None
        current_mode_id: Optional[str] = None
        if modes_data is not None:
            modes = [
                SessionMode(
                    id=m.get("id", ""),
                    name=m.get("name", ""),
                    description=m.get("description"),
                )
                for m in modes_data.get("availableModes", [])
            ]
            current_mode_id = modes_data.get("currentModeId")

        return ACPSession(
            session_id=session_id,
            modes=modes,
            current_mode_id=current_mode_id,
        )

    async def load_session(
        self,
        session_id: str,
        working_dir: Optional[Union[str, Path]] = None,
        mcp_servers: Optional[List[MCPServerStdio]] = None,
    ) -> ACPSession:
        """Load an existing session.

        Args:
            session_id: The ID of the session to load
            working_dir: Working directory for the session
            mcp_servers: List of MCP servers to connect to

        Returns:
            The loaded session

        Raises:
            ACPError: If session loading is not supported or session not found
        """
        if not self._agent_capabilities or not self._agent_capabilities.load_session:
            raise ACPError("Agent does not support loading sessions")

        cwd = str(working_dir or self.working_dir)

        params: Dict[str, Any] = {
            "sessionId": session_id,
            "cwd": cwd,
            "mcpServers": [s.to_dict() for s in mcp_servers] if mcp_servers else [],
        }

        result = await self._send_request("session/load", params)

        modes_data = result.get("modes") if result else None

        modes: Optional[List[SessionMode]] = None
        current_mode_id: Optional[str] = None
        if modes_data is not None:
            modes = [
                SessionMode(
                    id=m.get("id", ""),
                    name=m.get("name", ""),
                    description=m.get("description"),
                )
                for m in modes_data.get("availableModes", [])
            ]
            current_mode_id = modes_data.get("currentModeId")

        return ACPSession(
            session_id=session_id,
            modes=modes,
            current_mode_id=current_mode_id,
        )

    # =========================================================================
    # Prompting
    # =========================================================================

    async def prompt(
        self,
        session_id: str,
        content: Union[str, List[ContentBlock]],
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[SessionUpdate, None]:
        """Send a prompt and stream updates.

        This method sends a prompt to the agent and yields session updates
        as they are received. The generator completes when the agent finishes
        processing (returns a stop reason).

        Args:
            session_id: The session to send the prompt to
            content: The prompt content (text string or list of content blocks)
            timeout: Optional timeout for the entire prompt turn

        Yields:
            SessionUpdate objects as the agent processes the prompt

        Example:
            async for update in client.prompt(session_id, "Write hello world"):
                if update.content:
                    print(update.content.text, end="")
        """
        # Convert string to content blocks
        if isinstance(content, str):
            prompt_content = [{"type": "text", "text": content}]
        else:
            prompt_content = [block.to_dict() for block in content]

        params = {
            "sessionId": session_id,
            "prompt": prompt_content,
        }

        # Queue to receive notifications
        update_queue: asyncio.Queue[Optional[SessionUpdate]] = asyncio.Queue()

        def handle_update(update: SessionUpdate) -> None:
            if update.session_id == session_id:
                update_queue.put_nowait(update)

        self.add_notification_handler(handle_update)

        request_id: Optional[str] = None
        try:
            # Send the prompt request
            request_id, request = create_request("session/prompt", params)
            future: asyncio.Future[Any] = asyncio.Future()
            self._pending_requests[request_id] = future

            async with self._write_lock:
                data = json.dumps(request) + "\n"
                if self._process and self._process.stdin:
                    self._process.stdin.write(data.encode())
                    await self._process.stdin.drain()

            logger.debug(f"Sent prompt request: id={request_id}")

            # Yield updates while waiting for the response
            while True:
                # Check if the request is done
                if future.done():
                    break

                # Get next update with short timeout
                try:
                    update = await asyncio.wait_for(
                        update_queue.get(),
                        timeout=0.1,
                    )
                    if update:
                        yield update
                except asyncio.TimeoutError:
                    continue

            # Drain any remaining updates
            while not update_queue.empty():
                update = update_queue.get_nowait()
                if update:
                    yield update

            # Get the final result (check for errors)
            try:
                result = future.result()
                stop_reason = (
                    result.get("stopReason", "end_turn") if result else "end_turn"
                )
                logger.debug(f"Prompt completed: stop_reason={stop_reason}")
            except ACPError:
                raise

        except asyncio.CancelledError:
            # Send cancellation notification
            await self.cancel_session(session_id)
            raise

        finally:
            self.remove_notification_handler(handle_update)
            if request_id:
                self._pending_requests.pop(request_id, None)

    async def cancel_session(self, session_id: str) -> None:
        """Cancel an ongoing prompt turn.

        Args:
            session_id: The session to cancel
        """
        await self._send_notification("session/cancel", {"sessionId": session_id})
        logger.debug(f"Cancelled session: {session_id}")

    async def set_mode(self, session_id: str, mode_id: str) -> None:
        """Set the current mode for a session.

        Args:
            session_id: The session to set the mode for
            mode_id: The ID of the mode to set
        """
        params = {
            "sessionId": session_id,
            "modeId": mode_id,
        }
        await self._send_request("session/set_mode", params)
        logger.debug(f"Set session mode: session={session_id}, mode={mode_id}")


# =============================================================================
# Singleton Client Management
# =============================================================================

_global_client: Optional[ACPClient] = None
_client_lock = asyncio.Lock()


async def get_acp_client(
    working_dir: Optional[Union[str, Path]] = None,
) -> ACPClient:
    """Get or create a global ACP client instance.

    This provides a singleton pattern for sharing a single ACP connection
    across the application.

    Args:
        working_dir: Working directory for OpenCode

    Returns:
        The global ACP client instance
    """
    global _global_client

    async with _client_lock:
        if _global_client is None or not _global_client.is_connected:
            _global_client = ACPClient(working_dir=working_dir)
            await _global_client.connect()
        return _global_client


async def close_acp_client() -> None:
    """Close the global ACP client if it exists."""
    global _global_client

    async with _client_lock:
        if _global_client is not None:
            await _global_client.disconnect()
            _global_client = None
