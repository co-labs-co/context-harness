"""Message primitives for ContextHarness chat interface.

Messages represent the communication between users and agents,
including tool calls and their results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
import uuid


class MessageRole(Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(Enum):
    """Status of a message in the conversation."""

    PENDING = "pending"  # Message being processed
    STREAMING = "streaming"  # Response is streaming
    COMPLETE = "complete"  # Message complete
    ERROR = "error"  # Error occurred


@dataclass
class ToolCall:
    """A tool invocation requested by the agent.

    Attributes:
        id: Unique identifier for the tool call
        name: Name of the tool being called
        arguments: Arguments passed to the tool
        timestamp: When the tool was called
    """

    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, name: str, arguments: Dict[str, Any]) -> "ToolCall":
        """Create a new tool call with auto-generated ID."""
        return cls(
            id=f"call_{uuid.uuid4().hex[:12]}",
            name=name,
            arguments=arguments,
        )


@dataclass
class ToolResult:
    """Result of a tool call execution.

    Attributes:
        tool_call_id: ID of the tool call this result belongs to
        output: The output from the tool
        is_error: Whether the tool execution resulted in an error
        duration_ms: How long the tool took to execute
        timestamp: When the result was received
    """

    tool_call_id: str
    output: str
    is_error: bool = False
    duration_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MessagePart:
    """A part of a message content.

    Messages can have multiple parts (text, images, tool calls, etc.)

    Attributes:
        type: The type of content
        content: The actual content (text, base64 image, etc.)
        metadata: Additional metadata for this part
    """

    type: Literal["text", "image", "code", "tool_call", "tool_result"]
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Message:
    """A chat message in a session.

    Messages are the fundamental unit of conversation between
    users and the ContextHarness agent.

    Attributes:
        id: Unique message identifier
        session_id: ID of the session this message belongs to
        role: Who sent the message (user, assistant, system)
        content: The message content (text)
        parts: Optional structured message parts
        status: Current status of the message
        timestamp: When the message was created
        tool_calls: Tool calls made by the agent (for assistant messages)
        tool_results: Results of tool calls
        parent_id: Optional parent message ID (for threading)
        metadata: Additional message metadata
    """

    id: str
    session_id: str
    role: MessageRole
    content: str
    parts: List[MessagePart] = field(default_factory=list)
    status: MessageStatus = MessageStatus.COMPLETE
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_user_message(
        cls,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Message":
        """Create a new user message.

        Args:
            session_id: Session this message belongs to
            content: Message content
            metadata: Optional metadata

        Returns:
            A new Message instance
        """
        return cls(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            role=MessageRole.USER,
            content=content,
            status=MessageStatus.COMPLETE,
            metadata=metadata or {},
        )

    @classmethod
    def create_assistant_message(
        cls,
        session_id: str,
        content: str = "",
        status: MessageStatus = MessageStatus.PENDING,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Message":
        """Create a new assistant message.

        Args:
            session_id: Session this message belongs to
            content: Initial content (can be empty for streaming)
            status: Message status
            metadata: Optional metadata

        Returns:
            A new Message instance
        """
        return cls(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=content,
            status=status,
            metadata=metadata or {},
        )

    @classmethod
    def create_system_message(
        cls,
        session_id: str,
        content: str,
    ) -> "Message":
        """Create a new system message.

        Args:
            session_id: Session this message belongs to
            content: System message content

        Returns:
            A new Message instance
        """
        return cls(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            role=MessageRole.SYSTEM,
            content=content,
            status=MessageStatus.COMPLETE,
        )

    def append_content(self, chunk: str) -> None:
        """Append content to the message (for streaming).

        Args:
            chunk: Content chunk to append
        """
        self.content += chunk
        self.status = MessageStatus.STREAMING

    def complete(self) -> None:
        """Mark the message as complete."""
        self.status = MessageStatus.COMPLETE

    def mark_error(self, error: str) -> None:
        """Mark the message as errored.

        Args:
            error: Error message
        """
        self.status = MessageStatus.ERROR
        self.metadata["error"] = error

    def add_tool_call(self, name: str, arguments: Dict[str, Any]) -> ToolCall:
        """Add a tool call to this message.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            The created ToolCall
        """
        tool_call = ToolCall.create(name, arguments)
        self.tool_calls.append(tool_call)
        return tool_call

    def add_tool_result(
        self,
        tool_call_id: str,
        output: str,
        is_error: bool = False,
        duration_ms: Optional[int] = None,
    ) -> ToolResult:
        """Add a tool result to this message.

        Args:
            tool_call_id: ID of the tool call
            output: Tool output
            is_error: Whether it was an error
            duration_ms: Execution duration

        Returns:
            The created ToolResult
        """
        result = ToolResult(
            tool_call_id=tool_call_id,
            output=output,
            is_error=is_error,
            duration_ms=duration_ms,
        )
        self.tool_results.append(result)
        return result


@dataclass
class Conversation:
    """A conversation thread within a session.

    Conversations track the message history and provide
    utilities for managing chat state.

    Attributes:
        session_id: ID of the session this conversation belongs to
        messages: List of messages in order
        created_at: When the conversation started
        updated_at: Last update timestamp
    """

    session_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation.

        Args:
            message: Message to add
        """
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_last_message(self) -> Optional[Message]:
        """Get the last message in the conversation."""
        return self.messages[-1] if self.messages else None

    def get_messages_by_role(self, role: MessageRole) -> List[Message]:
        """Get all messages with a specific role.

        Args:
            role: Role to filter by

        Returns:
            List of matching messages
        """
        return [m for m in self.messages if m.role == role]

    def to_prompt_format(self) -> List[Dict[str, str]]:
        """Convert conversation to a format suitable for LLM prompts.

        Returns:
            List of role/content dicts
        """
        return [
            {"role": m.role.value, "content": m.content}
            for m in self.messages
            if m.status == MessageStatus.COMPLETE
        ]
