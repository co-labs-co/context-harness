# ContextHarness Architecture

> **Version**: 3.0 (Primitives Refactor)  
> **Status**: Proposed  
> **Last Updated**: 2025-12-30

## Overview

This document defines the primitive-based architecture for ContextHarness, establishing clear boundaries between domain models, services, and interfaces. The goal is to create a clean foundation that supports multiple interfaces (CLI, Web, SDK) without duplication.

---

## Architectural Principles

### 1. Primitives First
Core domain concepts are modeled as pure Python dataclasses with no I/O or framework dependencies. These primitives are the **source of truth** for the entire system.

### 2. Separation of Concerns
```
┌─────────────────────────────────────────────────────────────┐
│                      INTERFACES                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │   CLI   │  │   Web   │  │   SDK   │  │ Agent Protocol  │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
└───────┼────────────┼───────────┼────────────────┼───────────┘
        │            │           │                │
        ▼            ▼           ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                      SERVICES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ SessionSvc   │  │ SkillSvc     │  │ AuthSvc      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ MCPSvc       │  │ ConfigSvc    │  │ InstallSvc   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
        │            │           │                │
        ▼            ▼           ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                     PRIMITIVES                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Session  │  │ Skill    │  │ OAuth    │  │ MCP      │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Config   │  │ Template │  │ Result   │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 3. Dependency Direction
- **Primitives**: Zero dependencies (pure dataclasses)
- **Services**: Depend only on primitives
- **Interfaces**: Depend on services and primitives

### 4. Interface Agnosticism
Services return primitives, not formatted output. Each interface (CLI, Web, SDK) transforms primitives into appropriate responses.

---

## Module Structure

```
src/context_harness/
├── __init__.py                 # Package metadata and version
├── primitives/                 # Domain models (PURE - no I/O)
│   ├── __init__.py
│   ├── session.py              # Session, CompactionCycle
│   ├── skill.py                # Skill, SkillMetadata
│   ├── oauth.py                # OAuthConfig, OAuthTokens, PKCEChallenge
│   ├── mcp.py                  # MCPServer, MCPConfig
│   ├── config.py               # OpenCodeConfig, ProjectConfig
│   ├── result.py               # Result[T], Error types
│   └── template.py             # Template, TemplateFile
│
├── services/                   # Business logic
│   ├── __init__.py
│   ├── session_service.py      # Session CRUD, compaction
│   ├── skill_service.py        # Skill install, extract, list
│   ├── oauth_service.py        # OAuth flows, token management
│   ├── mcp_service.py          # MCP configuration
│   ├── config_service.py       # opencode.json management
│   └── install_service.py      # Framework installation
│
├── storage/                    # Persistence layer
│   ├── __init__.py
│   ├── file_storage.py         # File-based storage
│   ├── token_storage.py        # Secure token storage (keyring/file)
│   └── cache.py                # Caching utilities
│
├── interfaces/                 # User-facing interfaces
│   ├── __init__.py
│   ├── cli/                    # Click-based CLI
│   │   ├── __init__.py
│   │   ├── main.py             # CLI entry point
│   │   ├── commands/           # Command modules
│   │   │   ├── __init__.py
│   │   │   ├── init.py
│   │   │   ├── mcp.py
│   │   │   └── skill.py
│   │   └── ui.py               # Rich console helpers
│   │
│   └── sdk/                    # Programmatic SDK (for web interface)
│       ├── __init__.py
│       └── client.py           # High-level SDK client
│
├── protocols/                  # Integration protocols
│   ├── __init__.py
│   ├── acp.py                  # Agent Context Protocol
│   └── opencode.py             # OpenCode SDK integration
│
└── templates/                  # Bundled template files
    └── ...
```

---

## Primitives

### Session
The fundamental unit of agent work context.

```python
@dataclass
class Session:
    """A context-harness session representing a unit of work."""
    id: str                           # Unique identifier (e.g., "login-feature")
    name: str                         # Human-readable name
    status: SessionStatus             # ACTIVE, COMPLETED, BLOCKED
    created_at: datetime
    updated_at: datetime
    compaction_cycle: int             # Current cycle number
    active_work: Optional[str]        # Current task description
    key_files: List[KeyFile]          # Modified files
    decisions: List[Decision]         # Recorded decisions
    documentation_refs: List[DocRef]  # Documentation links
    next_steps: List[str]             # Action items


@dataclass
class CompactionCycle:
    """Record of a compaction event."""
    cycle_number: int
    timestamp: datetime
    preserved_items: List[str]
```

### Skill
A reusable agent capability.

```python
@dataclass
class Skill:
    """A skill that extends agent capabilities."""
    name: str
    description: str
    version: str
    author: str
    tags: List[str]
    path: str
    is_local: bool                    # Local vs. remote skill
    is_valid: bool                    # SKILL.md validation status
    min_context_harness_version: Optional[str]


@dataclass
class SkillMetadata:
    """Frontmatter metadata from SKILL.md."""
    name: str
    description: str
    version: str
    author: Optional[str]
    tags: List[str]
```

### OAuth
Authentication primitives.

```python
@dataclass
class OAuthConfig:
    """Configuration for an OAuth provider."""
    service_name: str
    client_id: str
    auth_url: str
    token_url: str
    scopes: List[str]
    audience: Optional[str]
    display_name: Optional[str]
    setup_url: Optional[str]


@dataclass
class OAuthTokens:
    """Stored OAuth tokens."""
    access_token: str
    token_type: str
    expires_in: Optional[int]
    refresh_token: Optional[str]
    scope: Optional[str]
    issued_at: float

    def is_expired(self) -> bool: ...


@dataclass
class PKCEChallenge:
    """PKCE code challenge for OAuth 2.1."""
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"
```

### MCP
Model Context Protocol server configuration.

```python
@dataclass
class MCPServer:
    """An MCP server configuration."""
    name: str
    url: str
    description: str
    server_type: Literal["remote", "local"]
    auth_type: Optional[Literal["oauth", "api-key"]]


@dataclass
class MCPConfig:
    """MCP configuration in opencode.json."""
    servers: Dict[str, MCPServerConfig]
```

### Config
Project configuration.

```python
@dataclass
class OpenCodeConfig:
    """Contents of opencode.json."""
    schema: str
    mcp: Dict[str, Any]
    agents: Optional[Dict[str, Any]]
    commands: Optional[Dict[str, Any]]
    skills: Optional[Dict[str, Any]]


@dataclass
class ProjectConfig:
    """ContextHarness project configuration."""
    context_harness_dir: Path
    opencode_dir: Path
    sessions_dir: Path
    skills_dir: Path
```

### Result
Generic result types for operations.

```python
@dataclass
class Success(Generic[T]):
    """Successful operation result."""
    value: T
    message: Optional[str] = None


@dataclass
class Failure:
    """Failed operation result."""
    error: str
    code: ErrorCode
    details: Optional[Dict[str, Any]] = None


Result = Union[Success[T], Failure]


class ErrorCode(Enum):
    """Standard error codes."""
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    AUTH_REQUIRED = "auth_required"
    AUTH_FAILED = "auth_failed"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
```

---

## Services

Services implement business logic using primitives. They:
- Accept primitives as input
- Return `Result[Primitive]` types
- Handle I/O through injected storage adapters
- Never import CLI or web framework code

### SessionService
```python
class SessionService:
    def __init__(self, storage: SessionStorage):
        self.storage = storage

    def create(self, name: str) -> Result[Session]: ...
    def get(self, session_id: str) -> Result[Session]: ...
    def list_all(self) -> Result[List[Session]]: ...
    def update(self, session: Session) -> Result[Session]: ...
    def compact(self, session: Session, guidance: str) -> Result[CompactionCycle]: ...
    def delete(self, session_id: str) -> Result[None]: ...
```

### SkillService
```python
class SkillService:
    def __init__(self, storage: SkillStorage, registry_client: RegistryClient):
        self.storage = storage
        self.registry = registry_client

    def list_remote(self, tags: List[str] = None) -> Result[List[Skill]]: ...
    def list_local(self, project_path: Path) -> Result[List[Skill]]: ...
    def get_info(self, skill_name: str) -> Result[Skill]: ...
    def install(self, skill_name: str, target: Path, force: bool) -> Result[Skill]: ...
    def extract(self, skill_name: str, source: Path) -> Result[str]: ...  # Returns PR URL
```

### OAuthService
```python
class OAuthService:
    def __init__(self, token_storage: TokenStorage):
        self.token_storage = token_storage

    def get_provider(self, name: str) -> Result[OAuthConfig]: ...
    def list_providers(self) -> List[OAuthConfig]: ...
    def authenticate(self, provider: str, client_id: str) -> Result[OAuthTokens]: ...
    def get_status(self, provider: str) -> AuthStatus: ...
    def refresh(self, provider: str) -> Result[OAuthTokens]: ...
    def logout(self, provider: str) -> Result[None]: ...
```

### MCPService
```python
class MCPService:
    def __init__(self, config_service: ConfigService, oauth_service: OAuthService):
        self.config = config_service
        self.oauth = oauth_service

    def list_available(self) -> List[MCPServer]: ...
    def list_configured(self, project_path: Path) -> Result[Dict[str, Any]]: ...
    def add(self, server: str, project_path: Path, api_key: str = None) -> Result[MCPServer]: ...
    def remove(self, server: str, project_path: Path) -> Result[None]: ...
```

---

## Storage Layer

Storage adapters abstract persistence details.

```python
class SessionStorage(Protocol):
    """Protocol for session persistence."""
    def save(self, session: Session) -> None: ...
    def load(self, session_id: str) -> Optional[Session]: ...
    def list_all(self) -> List[Session]: ...
    def delete(self, session_id: str) -> bool: ...


class FileSessionStorage(SessionStorage):
    """File-based session storage (SESSION.md files)."""
    def __init__(self, base_path: Path): ...


class TokenStorage(Protocol):
    """Protocol for secure token storage."""
    def save_tokens(self, service: str, tokens: OAuthTokens) -> None: ...
    def load_tokens(self, service: str) -> Optional[OAuthTokens]: ...
    def delete_tokens(self, service: str) -> bool: ...


class KeyringTokenStorage(TokenStorage):
    """System keyring-based token storage."""
    ...


class FileTokenStorage(TokenStorage):
    """File-based token storage (fallback)."""
    ...
```

---

## Interfaces

### CLI Interface
The CLI is a thin layer that:
1. Parses arguments via Click
2. Calls services
3. Transforms `Result` types into Rich console output

```python
# interfaces/cli/commands/skill.py
@skill.command("install")
@click.argument("skill_name")
def skill_install(skill_name: str):
    service = get_skill_service()  # Dependency injection
    result = service.install(skill_name, Path.cwd())

    if isinstance(result, Success):
        console.print(f"[green]✅ Installed {result.value.name}[/green]")
    else:
        console.print(f"[red]❌ {result.error}[/red]")
        raise SystemExit(1)
```

### SDK Interface
For programmatic use (web interface, scripts):

```python
# interfaces/sdk/client.py
class ContextHarnessClient:
    """High-level SDK for ContextHarness operations."""
    
    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path.cwd()
        self._init_services()

    # Session operations
    def create_session(self, name: str) -> Session: ...
    def get_session(self, session_id: str) -> Session: ...
    def list_sessions(self) -> List[Session]: ...
    def compact_session(self, session_id: str) -> CompactionCycle: ...

    # Skill operations
    def list_skills(self, tags: List[str] = None) -> List[Skill]: ...
    def install_skill(self, name: str, force: bool = False) -> Skill: ...
    def extract_skill(self, name: str) -> str: ...

    # MCP operations
    def list_mcp_servers(self) -> List[MCPServer]: ...
    def add_mcp_server(self, name: str, api_key: str = None) -> MCPServer: ...

    # Auth operations
    def authenticate(self, provider: str, client_id: str) -> OAuthTokens: ...
    def get_auth_status(self, provider: str) -> AuthStatus: ...
```

---

## Web Interface Foundation

The primitives and SDK enable a web interface to be built cleanly:

```python
# Future: web/routes/sessions.py
from fastapi import APIRouter
from context_harness.interfaces.sdk import ContextHarnessClient
from context_harness.primitives import Session

router = APIRouter(prefix="/sessions")

@router.get("/")
async def list_sessions() -> List[Session]:
    client = ContextHarnessClient()
    return client.list_sessions()

@router.post("/")
async def create_session(name: str) -> Session:
    client = ContextHarnessClient()
    return client.create_session(name)
```

---

## Migration Path

### Phase 1: Primitives (This PR)
1. Create `primitives/` package with all domain models
2. Add `result.py` for standardized error handling
3. Maintain backward compatibility with existing modules

### Phase 2: Services
1. Create `services/` package
2. Extract business logic from existing modules into services
3. Keep CLI working via shims

### Phase 3: Storage
1. Create `storage/` package
2. Abstract file operations behind storage protocols
3. Migrate token storage

### Phase 4: CLI Refactor
1. Move CLI to `interfaces/cli/`
2. Split into command modules
3. CLI calls services, formats output

### Phase 5: SDK
1. Create `interfaces/sdk/`
2. High-level client wrapping services
3. Ready for web interface development

---

## Testing Strategy

```
tests/
├── unit/
│   ├── primitives/          # Pure dataclass tests
│   ├── services/            # Service logic tests (mocked storage)
│   └── storage/             # Storage adapter tests
│
├── integration/
│   ├── test_cli.py          # CLI integration tests
│   └── test_sdk.py          # SDK integration tests
│
└── fixtures/
    ├── sessions/            # Sample session files
    └── skills/              # Sample skill directories
```

---

## Appendix: File-to-Module Mapping

| Current File | New Location | Notes |
|--------------|--------------|-------|
| `cli.py` | `interfaces/cli/main.py` + `commands/` | Split into modules |
| `oauth.py` | `primitives/oauth.py` + `services/oauth_service.py` + `storage/token_storage.py` | Split by concern |
| `mcp_config.py` | `primitives/mcp.py` + `services/mcp_service.py` | Split model/logic |
| `skills.py` | `primitives/skill.py` + `services/skill_service.py` | Split model/logic |
| `installer.py` | `services/install_service.py` | Minimal changes |
| `completion.py` | `interfaces/cli/completion.py` | CLI-specific |

---

## Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Primitives as pure dataclasses | Enables reuse across interfaces, easy testing | 2025-12-30 |
| Services return Result types | Explicit error handling, no exceptions for control flow | 2025-12-30 |
| Storage as protocols | Allows swapping implementations (file, database, cloud) | 2025-12-30 |
| SDK as primary interface | Web interface uses SDK, CLI uses SDK or services | 2025-12-30 |
