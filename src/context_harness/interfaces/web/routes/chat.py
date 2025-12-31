"""Chat API routes with SSE streaming."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from context_harness.interfaces.web.deps import get_working_dir
from context_harness.primitives import (
    Message,
    MessageRole,
    MessageStatus,
)

router = APIRouter()


# Pydantic models for API
class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""

    session_id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Response for a chat message."""

    id: str
    session_id: str
    role: str
    content: str
    status: str
    timestamp: str
    tool_calls: List[Dict[str, Any]] = []


class ConversationResponse(BaseModel):
    """Response for conversation history."""

    session_id: str
    messages: List[ChatMessageResponse]
    total: int


# In-memory message store (will be replaced with persistent storage)
_conversations: Dict[str, List[Message]] = {}


def get_conversation(session_id: str) -> List[Message]:
    """Get or create a conversation for a session."""
    if session_id not in _conversations:
        _conversations[session_id] = []
    return _conversations[session_id]


@router.get("/{session_id}/messages", response_model=ConversationResponse)
async def get_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
) -> ConversationResponse:
    """Get chat messages for a session.

    Args:
        session_id: The session identifier
        limit: Maximum messages to return
        offset: Number of messages to skip

    Returns:
        Conversation with messages
    """
    messages = get_conversation(session_id)
    paginated = messages[offset : offset + limit]

    return ConversationResponse(
        session_id=session_id,
        messages=[
            ChatMessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role.value,
                content=m.content,
                status=m.status.value,
                timestamp=m.timestamp.isoformat(),
                tool_calls=[
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in m.tool_calls
                ],
            )
            for m in paginated
        ],
        total=len(messages),
    )


@router.post("/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
) -> ChatMessageResponse:
    """Send a message and get a response.

    This is a non-streaming endpoint that returns the complete response.
    For streaming responses, use the /stream endpoint.

    Args:
        session_id: The session identifier
        request: The message request

    Returns:
        The assistant's response message
    """
    conversation = get_conversation(session_id)

    # Create user message
    user_message = Message.create_user_message(
        session_id=session_id,
        content=request.content,
        metadata=request.metadata,
    )
    conversation.append(user_message)

    # Create assistant response (placeholder - will integrate with OpenCode)
    assistant_message = Message.create_assistant_message(
        session_id=session_id,
        content=f"I received your message: '{request.content}'. "
        "Agent integration coming soon!",
        status=MessageStatus.COMPLETE,
    )
    conversation.append(assistant_message)

    return ChatMessageResponse(
        id=assistant_message.id,
        session_id=assistant_message.session_id,
        role=assistant_message.role.value,
        content=assistant_message.content,
        status=assistant_message.status.value,
        timestamp=assistant_message.timestamp.isoformat(),
        tool_calls=[],
    )


async def generate_sse_response(
    session_id: str,
    content: str,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events for streaming responses.

    Args:
        session_id: The session identifier
        content: The user's message content

    Yields:
        SSE formatted events
    """
    conversation = get_conversation(session_id)

    # Create user message
    user_message = Message.create_user_message(
        session_id=session_id,
        content=content,
    )
    conversation.append(user_message)

    # Send user message event
    yield f"event: user_message\ndata: {json.dumps({'id': user_message.id, 'content': content})}\n\n"

    # Create assistant message (streaming)
    assistant_message = Message.create_assistant_message(
        session_id=session_id,
        content="",
        status=MessageStatus.STREAMING,
    )
    conversation.append(assistant_message)

    # Send start event
    yield f"event: start\ndata: {json.dumps({'id': assistant_message.id})}\n\n"

    # Simulate streaming response (will be replaced with actual OpenCode integration)
    response_text = (
        f"I received your message: '{content}'. "
        "This response is being streamed! "
        "Agent integration with OpenCode Server coming soon. "
        "The web UI will support real-time tool calls and responses."
    )

    # Stream the response word by word
    words = response_text.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        assistant_message.append_content(chunk)

        yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
        await asyncio.sleep(0.05)  # Simulate typing delay

    # Mark complete
    assistant_message.complete()

    # Send completion event
    yield f"event: complete\ndata: {json.dumps({'id': assistant_message.id, 'content': assistant_message.content})}\n\n"


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request: ChatMessageRequest,
) -> StreamingResponse:
    """Send a message and stream the response via SSE.

    Args:
        session_id: The session identifier
        request: The message request

    Returns:
        Streaming response with SSE events
    """
    return StreamingResponse(
        generate_sse_response(session_id, request.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{session_id}/messages")
async def clear_messages(session_id: str) -> Dict[str, str]:
    """Clear all messages for a session.

    Args:
        session_id: The session identifier

    Returns:
        Confirmation message
    """
    if session_id in _conversations:
        _conversations[session_id] = []

    return {"status": "cleared", "session_id": session_id}
