"""ContextHarness Services.

This package contains business logic services that operate on primitives.
Services:
- Accept primitives as input
- Return Result[Primitive] types
- Handle I/O through injected storage adapters
- Never import CLI or web framework code

Services are the bridge between primitives (pure data) and interfaces (CLI, Web, SDK).
"""

from context_harness.services.config_service import ConfigService
from context_harness.services.mcp_service import MCPService
from context_harness.services.oauth_service import (
    FileTokenStorage,
    MemoryTokenStorage,
    OAuthService,
)
from context_harness.services.project_harness_config_service import (
    ProjectHarnessConfigService,
)
from context_harness.services.skill_service import (
    DefaultGitHubClient,
    SkillService,
)
from context_harness.services.worktree_service import (
    SubprocessGitRunner,
    WorktreeService,
)
from context_harness.services.ignore_service import (
    IgnoreService,
    PathSpecMatcher,
    FnmatchMatcher,
)

__all__ = [
    # Config
    "ConfigService",
    "ProjectHarnessConfigService",
    # MCP
    "MCPService",
    # OAuth
    "FileTokenStorage",
    "MemoryTokenStorage",
    "OAuthService",
    # Skill
    "DefaultGitHubClient",
    "SkillService",
    # Worktree
    "SubprocessGitRunner",
    "WorktreeService",
    # Ignore
    "IgnoreService",
    "PathSpecMatcher",
    "FnmatchMatcher",
]
