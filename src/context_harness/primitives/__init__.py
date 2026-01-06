"""ContextHarness Primitives.

This package contains pure domain models (dataclasses) with no I/O dependencies.
These primitives are the foundation for all ContextHarness functionality and
can be used by any interface (CLI, Web, SDK).

Primitives follow these rules:
1. No I/O operations (file, network, etc.)
2. No framework dependencies (click, rich, etc.)
3. Only standard library + typing dependencies
4. Immutable where practical
5. Full type annotations
"""

from context_harness.primitives.result import (
    ErrorCode,
    Failure,
    Result,
    Success,
    is_failure,
    is_success,
)
from context_harness.primitives.session import (
    CompactionCycle,
    Decision,
    DocRef,
    KeyFile,
    Session,
    SessionStatus,
)
from context_harness.primitives.skill import (
    Skill,
    SkillMetadata,
    SkillSource,
)
from context_harness.primitives.oauth import (
    AuthStatus,
    OAuthConfig,
    OAuthProvider,
    OAuthTokens,
    PKCEChallenge,
)
from context_harness.primitives.mcp import (
    MCPAuthType,
    MCPServer,
    MCPServerConfig,
    MCPServerType,
)
from context_harness.primitives.config import (
    AgentConfig,
    CommandConfig,
    OpenCodeConfig,
    ProjectConfig,
)
from context_harness.primitives.message import (
    Conversation,
    Message,
    MessagePart,
    MessageRole,
    MessageStatus,
    ToolCall,
    ToolResult,
)
from context_harness.primitives.voice import (
    TranscriptionStatus,
    VoiceRecordingState,
    VoiceSettings,
    VoiceSource,
    VoiceTranscription,
)
from context_harness.primitives.theme import (
    Theme,
    ThemeCategory,
    ThemeColors,
    ThemeMetadata,
    ThemePreference,
    ThemeType,
    ThemeValidationError,
)

__all__ = [
    # Result types
    "ErrorCode",
    "Failure",
    "Result",
    "Success",
    "is_failure",
    "is_success",
    # Session types
    "CompactionCycle",
    "Decision",
    "DocRef",
    "KeyFile",
    "Session",
    "SessionStatus",
    # Skill types
    "Skill",
    "SkillMetadata",
    "SkillSource",
    # OAuth types
    "AuthStatus",
    "OAuthConfig",
    "OAuthProvider",
    "OAuthTokens",
    "PKCEChallenge",
    # MCP types
    "MCPAuthType",
    "MCPServer",
    "MCPServerConfig",
    "MCPServerType",
    # Config types
    "AgentConfig",
    "CommandConfig",
    "OpenCodeConfig",
    "ProjectConfig",
    # Message types
    "Conversation",
    "Message",
    "MessagePart",
    "MessageRole",
    "MessageStatus",
    "ToolCall",
    "ToolResult",
    # Voice types
    "TranscriptionStatus",
    "VoiceRecordingState",
    "VoiceSettings",
    "VoiceSource",
    "VoiceTranscription",
    # Theme types
    "Theme",
    "ThemeCategory",
    "ThemeColors",
    "ThemeMetadata",
    "ThemePreference",
    "ThemeType",
    "ThemeValidationError",
]
