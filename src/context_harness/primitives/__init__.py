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
    VersionComparison,
    VersionStatus,
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
    DEFAULT_SKILLS_REPO,
    OpenCodeConfig,
    ProjectConfig,
    SKILLS_REPO_ENV_VAR,
    SkillsRegistryConfig,
    UserConfig,
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
from context_harness.primitives.worktree import (
    WorktreeInfo,
    WorktreeList,
    WorktreeSessionId,
)
from context_harness.primitives.ignore import (
    IgnoreConfig,
    IgnoreMatch,
    IgnorePattern,
    IgnoreSource,
)
from context_harness.primitives.tool_detector import (
    DetectedTools,
    ToolDetector,
    ToolPaths,
    ToolTarget,
    ToolType,
    detect_tools,
    get_all_skills_dirs,
    get_skills_dir,
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
    "VersionComparison",
    "VersionStatus",
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
    "DEFAULT_SKILLS_REPO",
    "OpenCodeConfig",
    "ProjectConfig",
    "SKILLS_REPO_ENV_VAR",
    "SkillsRegistryConfig",
    "UserConfig",
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
    # Worktree types
    "WorktreeInfo",
    "WorktreeList",
    "WorktreeSessionId",
    # Ignore types
    "IgnoreConfig",
    "IgnoreMatch",
    "IgnorePattern",
    "IgnoreSource",
    # Tool detection types
    "DetectedTools",
    "ToolDetector",
    "ToolPaths",
    "ToolTarget",
    "ToolType",
    "detect_tools",
    "get_all_skills_dirs",
    "get_skills_dir",
]
