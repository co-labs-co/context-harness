"""Chat API routes with SSE streaming via OpenCode ACP.

This module provides chat endpoints that communicate with OpenCode via the
Agent Client Protocol (ACP) for real AI agent responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from context_harness.interfaces.web.deps import get_working_dir
from context_harness.interfaces.web.services import (
    ACPClient,
    ACPConnectionError,
    ACPError,
    ACPTimeoutError,
    get_acp_client,
)
from context_harness.interfaces.web.services.acp_client import (
    SessionUpdate,
    SessionUpdateType,
    ToolCallStatus,
)
from context_harness.primitives import (
    Message,
    MessageRole,
    MessageStatus,
    ToolCall as PrimitiveToolCall,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Pydantic Models for API
# =============================================================================


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""

    session_id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ToolCallResponse(BaseModel):
    """Tool call information in response."""

    id: str
    title: str
    kind: Optional[str] = None
    status: str


class ChatMessageResponse(BaseModel):
    """Response for a chat message."""

    id: str
    session_id: str
    role: str
    content: str
    status: str
    timestamp: str
    tool_calls: List[ToolCallResponse] = []


class ConversationResponse(BaseModel):
    """Response for conversation history."""

    session_id: str
    messages: List[ChatMessageResponse]
    total: int


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str  # Full model ID (e.g., "github-copilot/claude-opus-4.5")
    provider: str  # Provider name (e.g., "github-copilot")
    name: str  # Model name (e.g., "claude-opus-4.5")
    display_name: str  # Human-friendly name


class ModelsResponse(BaseModel):
    """Response containing available models."""

    models: List[ModelInfo]
    current_model: Optional[str] = None


class SetModelRequest(BaseModel):
    """Request to set the model for a session."""

    model_id: str


class SetModelResponse(BaseModel):
    """Response after setting the model."""

    session_id: str
    model_id: str
    success: bool
    message: str


# =============================================================================
# In-Memory Storage (will be replaced with persistent storage)
# =============================================================================

# Conversations per ContextHarness session
_conversations: Dict[str, List[Message]] = {}

# ACP sessions per ContextHarness session
# Maps ContextHarness session_id -> (ACP session_id, is_initialized, model_set)
_acp_sessions: Dict[str, tuple[str, bool, bool]] = {}

# Model selection per ContextHarness session
# Maps session_id -> model_id
_session_models: Dict[str, str] = {}

# Default model for new sessions
DEFAULT_MODEL = "github-copilot/claude-opus-4.5"


def get_conversation(session_id: str) -> List[Message]:
    """Get or create a conversation for a session."""
    if session_id not in _conversations:
        _conversations[session_id] = []
    return _conversations[session_id]


# Default agent mode for ContextHarness
DEFAULT_AGENT_MODE = "context-harness"


async def get_or_create_acp_session(
    client: ACPClient, session_id: str
) -> tuple[str, bool, bool]:
    """Get existing ACP session or create a new one.

    Creates a new ACP session and sets it to use the context-harness agent mode.

    Args:
        client: The ACP client
        session_id: ContextHarness session ID

    Returns:
        Tuple of (ACP session ID, needs_context_init, needs_model_set)
        needs_context_init is True if this is a fresh session that needs /ctx
        needs_model_set is True if the model hasn't been set yet
    """
    if session_id not in _acp_sessions:
        acp_session = await client.create_session()
        acp_session_id = acp_session.session_id

        # Set the agent mode to context-harness
        try:
            await client.set_mode(acp_session_id, DEFAULT_AGENT_MODE)
            logger.info(
                f"Set agent mode to '{DEFAULT_AGENT_MODE}' for session {acp_session_id}"
            )
        except Exception as e:
            logger.warning(f"Could not set agent mode to '{DEFAULT_AGENT_MODE}': {e}")
            # Continue anyway - the /ctx command will still work

        _acp_sessions[session_id] = (acp_session_id, True, True)
        logger.info(f"Created ACP session {acp_session_id} for {session_id}")
        return acp_session_id, True, True

    acp_session_id, needs_init, needs_model = _acp_sessions[session_id]
    return acp_session_id, needs_init, needs_model


def mark_acp_session_initialized(session_id: str) -> None:
    """Mark an ACP session as initialized (context has been set)."""
    if session_id in _acp_sessions:
        acp_session_id, _, needs_model = _acp_sessions[session_id]
        _acp_sessions[session_id] = (acp_session_id, False, needs_model)


def mark_acp_session_model_set(session_id: str) -> None:
    """Mark an ACP session as having its model set."""
    if session_id in _acp_sessions:
        acp_session_id, needs_init, _ = _acp_sessions[session_id]
        _acp_sessions[session_id] = (acp_session_id, needs_init, False)


async def initialize_session_context(
    client: "ACPClient", acp_session_id: str, session_id: str
) -> None:
    """Send /ctx command to initialize session context.

    This sends the /ctx command as a separate prompt to ensure it's parsed
    correctly and doesn't get confused with the user's actual message.

    Args:
        client: The ACP client
        acp_session_id: The ACP session ID
        session_id: The ContextHarness session ID to switch to
    """
    ctx_command = f"/ctx {session_id}"
    logger.info(f"Initializing session context with: {ctx_command}")

    # Consume all updates from the /ctx command (we don't need to display them)
    async for update in client.prompt(acp_session_id, ctx_command):
        # Just drain the updates - the /ctx command's response is internal
        pass

    logger.info(f"Session context initialized for: {session_id}")


# =============================================================================
# API Endpoints
# =============================================================================


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
                    ToolCallResponse(
                        id=tc.id,
                        title=tc.name,
                        kind=None,
                        status="completed",
                    )
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
    working_dir: Path = Depends(get_working_dir),
) -> ChatMessageResponse:
    """Send a message and get a response.

    This is a non-streaming endpoint that returns the complete response.
    For streaming responses, use the /stream endpoint.

    Args:
        session_id: The session identifier
        request: The message request
        working_dir: The working directory for OpenCode

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

    # Try to use ACP for real agent response
    response_content = ""
    tool_calls: List[ToolCallResponse] = []

    try:
        client = await get_acp_client(working_dir)
        acp_session_id, needs_context, needs_model = await get_or_create_acp_session(
            client, session_id
        )

        # Initialize session context if needed (separate /ctx command)
        if needs_context:
            await initialize_session_context(client, acp_session_id, session_id)

        # Collect the full response from streaming
        async for update in client.prompt(acp_session_id, request.content):
            if update.update_type == SessionUpdateType.AGENT_MESSAGE_CHUNK:
                if update.content and update.content.text:
                    response_content += update.content.text
            elif update.update_type == SessionUpdateType.TOOL_CALL:
                if update.tool_call:
                    tool_calls.append(
                        ToolCallResponse(
                            id=update.tool_call.tool_call_id,
                            title=update.tool_call.title,
                            kind=update.tool_call.kind.value
                            if update.tool_call.kind
                            else None,
                            status=update.tool_call.status.value,
                        )
                    )

        # Mark session as initialized after successful prompt
        mark_acp_session_initialized(session_id)

    except ACPConnectionError as e:
        logger.warning(f"OpenCode not available: {e}")
        response_content = (
            f"I received your message: '{request.content}'. "
            "OpenCode is not currently running. Please start OpenCode with `opencode acp` "
            "to enable AI agent responses."
        )
    except ACPError as e:
        logger.error(f"ACP error: {e}")
        response_content = f"An error occurred communicating with the agent: {e}"

    # Create assistant response
    assistant_message = Message.create_assistant_message(
        session_id=session_id,
        content=response_content,
        status=MessageStatus.COMPLETE,
    )

    # Add tool calls to message
    for tc in tool_calls:
        assistant_message.tool_calls.append(
            PrimitiveToolCall(
                id=tc.id,
                name=tc.title,
                arguments={},
            )
        )

    conversation.append(assistant_message)

    return ChatMessageResponse(
        id=assistant_message.id,
        session_id=assistant_message.session_id,
        role=assistant_message.role.value,
        content=assistant_message.content,
        status=assistant_message.status.value,
        timestamp=assistant_message.timestamp.isoformat(),
        tool_calls=tool_calls,
    )


async def generate_sse_response(
    session_id: str,
    content: str,
    working_dir: Path,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events for streaming responses via ACP.

    This function bridges ACP session/update notifications to SSE events
    that the frontend can consume.

    Args:
        session_id: The session identifier
        content: The user's message content
        working_dir: The working directory for OpenCode

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

    try:
        # Connect to OpenCode via ACP
        client = await get_acp_client(working_dir)
        acp_session_id, needs_context, needs_model = await get_or_create_acp_session(
            client, session_id
        )

        # Initialize session context if needed (separate /ctx command)
        if needs_context:
            await initialize_session_context(client, acp_session_id, session_id)

        # Stream updates from ACP to SSE
        async for update in client.prompt(acp_session_id, content):
            sse_event = convert_acp_update_to_sse(update, assistant_message)
            if sse_event:
                yield sse_event

        # Mark session as initialized after successful prompt
        mark_acp_session_initialized(session_id)

    except ACPConnectionError as e:
        # Fallback: OpenCode not available
        logger.warning(f"OpenCode not available, using fallback: {e}")

        fallback_text = (
            f"I received your message: '{content}'. "
            "OpenCode is not currently running. "
            "Please start OpenCode with `opencode acp` to enable AI agent responses. "
            "In the meantime, I'm showing this placeholder response."
        )

        # Stream fallback response word by word
        words = fallback_text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            assistant_message.append_content(chunk)
            yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
            await asyncio.sleep(0.03)

    except ACPError as e:
        logger.error(f"ACP error during streaming: {e}")
        error_msg = f" [Error: {e}]"
        assistant_message.append_content(error_msg)
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    # Mark complete
    assistant_message.complete()

    # Send completion event
    yield f"event: complete\ndata: {json.dumps({'id': assistant_message.id, 'content': assistant_message.content})}\n\n"


def convert_acp_update_to_sse(
    update: SessionUpdate,
    assistant_message: Message,
) -> Optional[str]:
    """Convert an ACP SessionUpdate to an SSE event string.

    Args:
        update: The ACP session update
        assistant_message: The message being built (for content accumulation)

    Returns:
        SSE event string or None if update should be skipped
    """
    if update.update_type == SessionUpdateType.AGENT_MESSAGE_CHUNK:
        if update.content and update.content.text:
            chunk = update.content.text
            assistant_message.append_content(chunk)
            return f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

    elif update.update_type == SessionUpdateType.AGENT_THOUGHT_CHUNK:
        if update.content and update.content.text:
            # Send thoughts as a separate event type
            return f"event: thought\ndata: {json.dumps({'content': update.content.text})}\n\n"

    elif update.update_type == SessionUpdateType.TOOL_CALL:
        if update.tool_call:
            tc = update.tool_call
            # Send tool call event
            tool_data = {
                "id": tc.tool_call_id,
                "title": tc.title,
                "kind": tc.kind.value if tc.kind else None,
                "status": tc.status.value,
            }
            # Add tool call to message
            assistant_message.tool_calls.append(
                PrimitiveToolCall(
                    id=tc.tool_call_id,
                    name=tc.title,
                    arguments=tc.raw_input or {},
                )
            )
            return f"event: tool_call\ndata: {json.dumps(tool_data)}\n\n"

    elif update.update_type == SessionUpdateType.TOOL_CALL_UPDATE:
        # Send tool call status update
        update_data = {
            "id": update.tool_call_id,
            "title": update.tool_call_title,
            "status": update.tool_call_status.value
            if update.tool_call_status
            else None,
        }
        return f"event: tool_call_update\ndata: {json.dumps(update_data)}\n\n"

    elif update.update_type == SessionUpdateType.PLAN:
        if update.plan:
            plan_data = [
                {
                    "content": entry.content,
                    "priority": entry.priority,
                    "status": entry.status,
                }
                for entry in update.plan
            ]
            return f"event: plan\ndata: {json.dumps({'entries': plan_data})}\n\n"

    elif update.update_type == SessionUpdateType.CURRENT_MODE_UPDATE:
        if update.mode_id:
            return f"event: mode_change\ndata: {json.dumps({'modeId': update.mode_id})}\n\n"

    return None


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str,
    request: ChatMessageRequest,
    working_dir: Path = Depends(get_working_dir),
) -> StreamingResponse:
    """Send a message and stream the response via SSE.

    This endpoint connects to OpenCode via ACP and streams agent responses
    in real-time. Events include:

    - `user_message`: User's message was recorded
    - `start`: Agent response started
    - `chunk`: Text chunk from agent
    - `thought`: Agent's internal thought (if visible)
    - `tool_call`: Agent invoked a tool
    - `tool_call_update`: Tool call status changed
    - `plan`: Agent's plan entries
    - `mode_change`: Agent mode changed
    - `error`: An error occurred
    - `complete`: Response finished

    Args:
        session_id: The session identifier
        request: The message request
        working_dir: The working directory for OpenCode

    Returns:
        Streaming response with SSE events
    """
    return StreamingResponse(
        generate_sse_response(session_id, request.content, working_dir),
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

    This also clears the associated ACP session mapping, so the next
    message will re-initialize with /ctx.

    Args:
        session_id: The session identifier

    Returns:
        Confirmation message
    """
    if session_id in _conversations:
        _conversations[session_id] = []

    if session_id in _acp_sessions:
        del _acp_sessions[session_id]

    return {"status": "cleared", "session_id": session_id}


@router.get("/status")
async def get_acp_status(
    working_dir: Path = Depends(get_working_dir),
) -> Dict[str, Any]:
    """Check if OpenCode ACP is available.

    Returns:
        Status information about the ACP connection
    """
    try:
        client = await get_acp_client(working_dir)
        return {
            "available": True,
            "connected": client.is_connected,
            "agent_info": client._agent_info,
            "capabilities": {
                "load_session": client.agent_capabilities.load_session
                if client.agent_capabilities
                else False,
                "prompt_image": client.agent_capabilities.prompt_image
                if client.agent_capabilities
                else False,
                "prompt_audio": client.agent_capabilities.prompt_audio
                if client.agent_capabilities
                else False,
            }
            if client.agent_capabilities
            else None,
        }
    except ACPConnectionError as e:
        return {
            "available": False,
            "connected": False,
            "error": str(e),
            "help": "Start OpenCode with: opencode acp",
        }
    except Exception as e:
        return {
            "available": False,
            "connected": False,
            "error": str(e),
        }


# =============================================================================
# Model Management Endpoints
# =============================================================================


def get_available_models() -> List[ModelInfo]:
    """Get list of available models from OpenCode.

    Runs `opencode models` command and parses the output.
    Models are cached after first call.

    Returns:
        List of available models
    """
    try:
        result = subprocess.run(
            ["opencode", "models"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning(f"opencode models failed: {result.stderr}")
            return []

        models = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or "/" not in line:
                continue

            # Parse provider/model format
            parts = line.split("/", 1)
            if len(parts) == 2:
                provider, name = parts
                # Create human-friendly display name
                display_name = name.replace("-", " ").replace(".", " ").title()
                models.append(
                    ModelInfo(
                        id=line,
                        provider=provider,
                        name=name,
                        display_name=f"{display_name} ({provider})",
                    )
                )

        return models

    except subprocess.TimeoutExpired:
        logger.warning("opencode models command timed out")
        return []
    except FileNotFoundError:
        logger.warning("opencode command not found")
        return []
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return []


def get_session_model(session_id: str) -> str:
    """Get the model for a session, defaulting to DEFAULT_MODEL."""
    return _session_models.get(session_id, DEFAULT_MODEL)


def set_session_model(session_id: str, model_id: str) -> None:
    """Set the model for a session."""
    _session_models[session_id] = model_id


@router.get("/models")
async def list_models() -> ModelsResponse:
    """List all available models.

    Returns:
        List of available models with their metadata
    """
    models = get_available_models()
    return ModelsResponse(models=models, current_model=DEFAULT_MODEL)


@router.get("/{session_id}/model")
async def get_model(session_id: str) -> Dict[str, str]:
    """Get the current model for a session.

    Args:
        session_id: The session identifier

    Returns:
        Current model information
    """
    model_id = get_session_model(session_id)
    return {
        "session_id": session_id,
        "model_id": model_id,
    }


@router.post("/{session_id}/model")
async def set_model(
    session_id: str,
    request: SetModelRequest,
    working_dir: Path = Depends(get_working_dir),
) -> SetModelResponse:
    """Set the model for a session.

    This sends a /model command to OpenCode to switch models.

    Args:
        session_id: The session identifier
        request: The model to set

    Returns:
        Result of the model change
    """
    model_id = request.model_id

    # Validate model exists
    available_models = get_available_models()
    valid_model_ids = [m.id for m in available_models]

    if model_id not in valid_model_ids:
        return SetModelResponse(
            session_id=session_id,
            model_id=model_id,
            success=False,
            message=f"Model '{model_id}' not found. Use /api/chat/models to list available models.",
        )

    # Store the model preference
    set_session_model(session_id, model_id)

    # If we have an active ACP session, send the /model command
    if session_id in _acp_sessions:
        try:
            client = await get_acp_client(working_dir)
            acp_session_id, _, _ = _acp_sessions[session_id]

            # Send /model command
            model_command = f"/model {model_id}"
            logger.info(f"Setting model with: {model_command}")

            async for update in client.prompt(acp_session_id, model_command):
                # Drain updates - we don't need to display them
                pass

            mark_acp_session_model_set(session_id)

            return SetModelResponse(
                session_id=session_id,
                model_id=model_id,
                success=True,
                message=f"Model set to {model_id}",
            )

        except Exception as e:
            logger.error(f"Error setting model: {e}")
            return SetModelResponse(
                session_id=session_id,
                model_id=model_id,
                success=False,
                message=f"Error setting model: {e}",
            )

    # No active session - model will be set on first prompt
    return SetModelResponse(
        session_id=session_id,
        model_id=model_id,
        success=True,
        message=f"Model preference saved. Will be applied on next message.",
    )
