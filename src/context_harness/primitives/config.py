"""Configuration primitives for ContextHarness.

Provides dataclasses for opencode.json configuration and project paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_harness.primitives.mcp import MCPServerConfig


# Default skills repository
DEFAULT_SKILLS_REPO = "co-labs-co/context-harness-skills"

# Environment variable for skills repo override
SKILLS_REPO_ENV_VAR = "CONTEXT_HARNESS_SKILLS_REPO"


@dataclass(frozen=True)
class SkillsRegistryConfig:
    """Configuration for skills registry sources.

    Attributes:
        default: Default skills repository (owner/repo format)
    """

    default: str = DEFAULT_SKILLS_REPO

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillsRegistryConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with registry config

        Returns:
            SkillsRegistryConfig instance
        """
        return cls(
            default=data.get("default", DEFAULT_SKILLS_REPO),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {}
        if self.default != DEFAULT_SKILLS_REPO:
            result["default"] = self.default
        return result


@dataclass(frozen=True)
class UserConfig:
    """User-level ContextHarness configuration (~/.context-harness/config.json).

    This configuration is stored in the user's home directory and applies
    to all projects unless overridden by project-level config.

    Attributes:
        skills_registry: Skills registry configuration
    """

    skills_registry: Optional[SkillsRegistryConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserConfig":
        """Create from dictionary.

        Args:
            data: Dictionary from parsing config.json

        Returns:
            UserConfig instance
        """
        skills_registry = None
        if "skillsRegistry" in data:
            skills_registry = SkillsRegistryConfig.from_dict(data["skillsRegistry"])

        return cls(skills_registry=skills_registry)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {}
        if self.skills_registry:
            registry_dict = self.skills_registry.to_dict()
            if registry_dict:
                result["skillsRegistry"] = registry_dict
        return result

    @staticmethod
    def config_dir() -> Path:
        """Get the user config directory path.

        Returns:
            Path to ~/.context-harness/
        """
        return Path.home() / ".context-harness"

    @staticmethod
    def config_path() -> Path:
        """Get the user config file path.

        Returns:
            Path to ~/.context-harness/config.json
        """
        return UserConfig.config_dir() / "config.json"


@dataclass(frozen=True)
class ProjectHarnessConfig:
    """Project-level ContextHarness configuration (.context-harness/config.json).

    This configuration is stored in the project's .context-harness directory
    and takes precedence over user-level config but not environment variables.

    Attributes:
        skills_registry: Skills registry configuration
    """

    skills_registry: Optional[SkillsRegistryConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectHarnessConfig":
        """Create from dictionary.

        Args:
            data: Dictionary from parsing config.json

        Returns:
            ProjectHarnessConfig instance
        """
        skills_registry = None
        if "skillsRegistry" in data:
            skills_registry = SkillsRegistryConfig.from_dict(data["skillsRegistry"])

        return cls(skills_registry=skills_registry)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {}
        if self.skills_registry:
            registry_dict = self.skills_registry.to_dict()
            if registry_dict:
                result["skillsRegistry"] = registry_dict
        return result


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for an agent in opencode.json.

    Attributes:
        system_prompt: The agent's system prompt file path
        tools: List of tools available to the agent
        model: Optional model override for this agent
    """

    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    model: Optional[str] = None


@dataclass(frozen=True)
class CommandConfig:
    """Configuration for a custom command in opencode.json.

    Attributes:
        description: Human-readable description of the command
        agent: Agent to use for this command
        prompt: The prompt template for the command
    """

    description: str
    agent: Optional[str] = None
    prompt: Optional[str] = None


@dataclass
class OpenCodeConfig:
    """Contents of opencode.json configuration file.

    This represents the full opencode.json structure used by OpenCode.ai
    to configure MCP servers, agents, commands, and other settings.

    Attributes:
        schema_version: JSON schema version (e.g., "1.0")
        mcp: MCP server configurations keyed by server name
        agents: Agent configurations keyed by agent name
        commands: Custom command configurations keyed by command name
        skills: Skill configurations
        project_context: Path to project context file
        raw_data: The original parsed JSON data for fields not explicitly modeled
    """

    schema_version: str = "1.0"
    mcp: Dict[str, MCPServerConfig] = field(default_factory=dict)
    agents: Dict[str, AgentConfig] = field(default_factory=dict)
    commands: Dict[str, CommandConfig] = field(default_factory=dict)
    skills: Dict[str, Any] = field(default_factory=dict)
    project_context: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OpenCodeConfig:
        """Create an OpenCodeConfig from a dictionary (parsed JSON).

        Args:
            data: Dictionary from parsing opencode.json

        Returns:
            An OpenCodeConfig instance
        """
        mcp_data = data.get("mcp", {})
        mcp_servers = {}
        for name, config in mcp_data.items():
            if isinstance(config, dict):
                mcp_servers[name] = MCPServerConfig.from_dict(name, config)

        agents_data = data.get("agents", {})
        agents = {}
        for name, config in agents_data.items():
            if isinstance(config, dict):
                agents[name] = AgentConfig(
                    system_prompt=config.get("systemPrompt"),
                    tools=config.get("tools"),
                    model=config.get("model"),
                )

        commands_data = data.get("commands", {})
        commands = {}
        for name, config in commands_data.items():
            if isinstance(config, dict):
                commands[name] = CommandConfig(
                    description=config.get("description", ""),
                    agent=config.get("agent"),
                    prompt=config.get("prompt"),
                )

        return cls(
            schema_version=data.get("$schema", "1.0"),
            mcp=mcp_servers,
            agents=agents,
            commands=commands,
            skills=data.get("skills", {}),
            project_context=data.get("projectContext"),
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization.

        Returns:
            Dictionary representation of the config
        """
        result: Dict[str, Any] = {}

        if self.schema_version:
            result["$schema"] = self.schema_version

        if self.mcp:
            result["mcp"] = {}
            for name, server in self.mcp.items():
                result["mcp"][name] = server.to_dict()

        if self.agents:
            result["agents"] = {}
            for name, agent in self.agents.items():
                agent_dict: Dict[str, Any] = {}
                if agent.system_prompt:
                    agent_dict["systemPrompt"] = agent.system_prompt
                if agent.tools:
                    agent_dict["tools"] = agent.tools
                if agent.model:
                    agent_dict["model"] = agent.model
                result["agents"][name] = agent_dict

        if self.commands:
            result["commands"] = {}
            for name, cmd in self.commands.items():
                cmd_dict: Dict[str, Any] = {"description": cmd.description}
                if cmd.agent:
                    cmd_dict["agent"] = cmd.agent
                if cmd.prompt:
                    cmd_dict["prompt"] = cmd.prompt
                result["commands"][name] = cmd_dict

        if self.skills:
            result["skills"] = self.skills

        if self.project_context:
            result["projectContext"] = self.project_context

        return result


@dataclass(frozen=True)
class ProjectConfig:
    """ContextHarness project configuration paths.

    Provides standardized paths for all ContextHarness directories
    and files within a project. Supports both OpenCode and Claude Code tools.

    Attributes:
        project_root: Root directory of the project
        context_harness_dir: Path to .context-harness directory
        opencode_dir: Path to .opencode directory
        claude_dir: Path to .claude directory (Claude Code)
        sessions_dir: Path to sessions directory
        templates_dir: Path to templates directory
        skills_dir: Path to OpenCode skills directory (.opencode/skill)
        claude_skills_dir: Path to Claude Code skills directory (.claude/skills)
        baseline_dir: Path to baseline analysis directory
        project_context_path: Path to PROJECT-CONTEXT.md
        opencode_json_path: Path to opencode.json
        mcp_json_path: Path to .mcp.json (Claude Code)
        agents_md_path: Path to AGENTS.md (OpenCode)
        claude_md_path: Path to CLAUDE.md (Claude Code)
        harness_config_path: Path to .context-harness/config.json (project-level config)
    """

    project_root: Path
    context_harness_dir: Path
    opencode_dir: Path
    claude_dir: Path
    sessions_dir: Path
    templates_dir: Path
    skills_dir: Path
    claude_skills_dir: Path
    baseline_dir: Path
    project_context_path: Path
    opencode_json_path: Path
    mcp_json_path: Path
    agents_md_path: Path
    claude_md_path: Path
    harness_config_path: Path

    @classmethod
    def from_project_root(cls, project_root: Path) -> ProjectConfig:
        """Create a ProjectConfig from a project root directory.

        Args:
            project_root: The root directory of the project

        Returns:
            A ProjectConfig with all paths resolved
        """
        context_harness_dir = project_root / ".context-harness"
        opencode_dir = project_root / ".opencode"
        claude_dir = project_root / ".claude"

        return cls(
            project_root=project_root,
            context_harness_dir=context_harness_dir,
            opencode_dir=opencode_dir,
            claude_dir=claude_dir,
            sessions_dir=context_harness_dir / "sessions",
            templates_dir=context_harness_dir / "templates",
            skills_dir=opencode_dir / "skill",  # singular for OpenCode
            claude_skills_dir=claude_dir / "skills",  # plural for Claude Code
            baseline_dir=context_harness_dir / "baseline",
            project_context_path=context_harness_dir / "PROJECT-CONTEXT.md",
            opencode_json_path=project_root / "opencode.json",
            mcp_json_path=project_root / ".mcp.json",
            agents_md_path=project_root / "AGENTS.md",
            claude_md_path=project_root / "CLAUDE.md",
            harness_config_path=context_harness_dir / "config.json",
        )

    @classmethod
    def from_cwd(cls) -> ProjectConfig:
        """Create a ProjectConfig from the current working directory.

        Returns:
            A ProjectConfig with paths relative to CWD
        """
        return cls.from_project_root(Path.cwd())

    def ensure_directories(self) -> List[Path]:
        """Get list of directories that should exist for OpenCode.

        Returns:
            List of directory paths that should be created
        """
        return [
            self.context_harness_dir,
            self.sessions_dir,
            self.templates_dir,
            self.opencode_dir,
            self.skills_dir,
            self.baseline_dir,
        ]

    def ensure_directories_claude(self) -> List[Path]:
        """Get list of directories that should exist for Claude Code.

        Returns:
            List of directory paths that should be created
        """
        return [
            self.context_harness_dir,
            self.sessions_dir,
            self.templates_dir,
            self.claude_dir,
            self.claude_skills_dir,
            self.baseline_dir,
        ]

    def ensure_all_directories(self) -> List[Path]:
        """Get list of all directories for both tools.

        Returns:
            List of directory paths that should be created
        """
        return [
            self.context_harness_dir,
            self.sessions_dir,
            self.templates_dir,
            self.opencode_dir,
            self.skills_dir,
            self.claude_dir,
            self.claude_skills_dir,
            self.baseline_dir,
        ]

    def session_path(self, session_name: str) -> Path:
        """Get the path to a specific session directory.

        Args:
            session_name: Name of the session

        Returns:
            Path to the session directory
        """
        return self.sessions_dir / session_name

    def session_file(self, session_name: str) -> Path:
        """Get the path to a session's SESSION.md file.

        Args:
            session_name: Name of the session

        Returns:
            Path to the SESSION.md file
        """
        return self.session_path(session_name) / "SESSION.md"
