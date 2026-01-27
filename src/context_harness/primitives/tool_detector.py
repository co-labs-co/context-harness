"""Tool detection utilities for ContextHarness.

Provides centralized detection and path resolution for OpenCode and Claude Code tools.
This module enables dual-tool support throughout the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional


class ToolType(str, Enum):
    """Supported AI coding tools."""

    OPENCODE = "opencode"
    CLAUDE_CODE = "claude-code"


# Type alias for tool target specification
ToolTarget = Literal["opencode", "claude-code", "both"]


@dataclass(frozen=True)
class ToolPaths:
    """Paths for a specific tool installation.

    Attributes:
        tool: The tool type
        config_dir: Tool configuration directory (.opencode or .claude)
        skills_dir: Skills directory within config_dir
        agents_dir: Agents directory within config_dir
        commands_dir: Commands directory within config_dir
        mcp_config: MCP configuration file path
        memory_file: Project memory file (AGENTS.md or CLAUDE.md)
    """

    tool: ToolType
    config_dir: Path
    skills_dir: Path
    agents_dir: Path
    commands_dir: Path
    mcp_config: Path
    memory_file: Path

    @classmethod
    def for_opencode(cls, project_path: Path) -> "ToolPaths":
        """Create paths for OpenCode tool.

        Args:
            project_path: Root project directory

        Returns:
            ToolPaths configured for OpenCode
        """
        config_dir = project_path / ".opencode"
        return cls(
            tool=ToolType.OPENCODE,
            config_dir=config_dir,
            skills_dir=config_dir / "skill",  # singular
            agents_dir=config_dir / "agent",  # singular
            commands_dir=config_dir / "command",  # singular
            mcp_config=project_path / "opencode.json",
            memory_file=project_path / "AGENTS.md",
        )

    @classmethod
    def for_claude_code(cls, project_path: Path) -> "ToolPaths":
        """Create paths for Claude Code tool.

        Args:
            project_path: Root project directory

        Returns:
            ToolPaths configured for Claude Code
        """
        config_dir = project_path / ".claude"
        return cls(
            tool=ToolType.CLAUDE_CODE,
            config_dir=config_dir,
            skills_dir=config_dir / "skills",  # plural
            agents_dir=config_dir / "agents",  # plural
            commands_dir=config_dir / "commands",  # plural
            mcp_config=project_path / ".mcp.json",
            memory_file=project_path / "CLAUDE.md",
        )


@dataclass(frozen=True)
class DetectedTools:
    """Result of tool detection.

    Attributes:
        opencode: True if OpenCode is installed
        claude_code: True if Claude Code is installed
        primary: The primary (preferred) tool, or None if neither installed
        opencode_paths: Paths for OpenCode (always populated for convenience)
        claude_code_paths: Paths for Claude Code (always populated for convenience)
    """

    opencode: bool
    claude_code: bool
    primary: Optional[ToolType]
    opencode_paths: ToolPaths
    claude_code_paths: ToolPaths

    @property
    def any_installed(self) -> bool:
        """Check if any tool is installed."""
        return self.opencode or self.claude_code

    @property
    def both_installed(self) -> bool:
        """Check if both tools are installed."""
        return self.opencode and self.claude_code

    @property
    def installed_tools(self) -> List[ToolType]:
        """Get list of installed tools."""
        tools = []
        if self.opencode:
            tools.append(ToolType.OPENCODE)
        if self.claude_code:
            tools.append(ToolType.CLAUDE_CODE)
        return tools

    def get_paths(self, tool: Optional[ToolType] = None) -> Optional[ToolPaths]:
        """Get paths for a specific tool or the primary tool.

        Args:
            tool: Specific tool to get paths for, or None for primary

        Returns:
            ToolPaths for the requested tool, or None if not installed
        """
        if tool is None:
            tool = self.primary

        if tool == ToolType.OPENCODE:
            return self.opencode_paths if self.opencode else None
        elif tool == ToolType.CLAUDE_CODE:
            return self.claude_code_paths if self.claude_code else None
        return None


class ToolDetector:
    """Utility class for detecting installed AI coding tools.

    This class provides methods to detect which tools are installed in a project
    and resolve the appropriate paths for tool-specific operations.

    Example:
        detector = ToolDetector(project_path)
        detected = detector.detect()

        if detected.opencode:
            skills_dir = detected.opencode_paths.skills_dir
            # Use skills_dir for OpenCode operations

        # Or use the primary tool
        if detected.primary:
            paths = detected.get_paths()
            print(f"Using {paths.tool.value} skills at {paths.skills_dir}")
    """

    def __init__(self, project_path: Path):
        """Initialize the detector.

        Args:
            project_path: Root project directory to check for tool installations
        """
        self.project_path = project_path.resolve()
        self._opencode_paths = ToolPaths.for_opencode(self.project_path)
        self._claude_code_paths = ToolPaths.for_claude_code(self.project_path)

    def detect(self) -> DetectedTools:
        """Detect which tools are installed in the project.

        Detection is based on the presence of tool-specific configuration directories:
        - OpenCode: `.opencode/` directory exists
        - Claude Code: `.claude/` directory exists

        Returns:
            DetectedTools with information about installed tools
        """
        opencode_installed = self._opencode_paths.config_dir.exists()
        claude_code_installed = self._claude_code_paths.config_dir.exists()

        # Determine primary tool (prefer OpenCode if both installed for backward compatibility)
        primary: Optional[ToolType] = None
        if opencode_installed and claude_code_installed:
            primary = (
                ToolType.OPENCODE
            )  # Default to OpenCode for backward compatibility
        elif opencode_installed:
            primary = ToolType.OPENCODE
        elif claude_code_installed:
            primary = ToolType.CLAUDE_CODE

        return DetectedTools(
            opencode=opencode_installed,
            claude_code=claude_code_installed,
            primary=primary,
            opencode_paths=self._opencode_paths,
            claude_code_paths=self._claude_code_paths,
        )

    def get_skills_dirs(self, tool_target: Optional[ToolTarget] = None) -> List[Path]:
        """Get skills directories based on tool target.

        Args:
            tool_target: Which tool(s) to get paths for:
                - "opencode": Only OpenCode skills dir
                - "claude-code": Only Claude Code skills dir
                - "both": Both directories
                - None: Auto-detect installed tools

        Returns:
            List of skills directory paths (may be empty if no tools installed)
        """
        if tool_target == "opencode":
            return [self._opencode_paths.skills_dir]
        elif tool_target == "claude-code":
            return [self._claude_code_paths.skills_dir]
        elif tool_target == "both":
            return [
                self._opencode_paths.skills_dir,
                self._claude_code_paths.skills_dir,
            ]
        else:
            # Auto-detect
            detected = self.detect()
            dirs = []
            if detected.opencode:
                dirs.append(self._opencode_paths.skills_dir)
            if detected.claude_code:
                dirs.append(self._claude_code_paths.skills_dir)
            return dirs

    def get_mcp_config_paths(
        self, tool_target: Optional[ToolTarget] = None
    ) -> List[Path]:
        """Get MCP configuration file paths based on tool target.

        Args:
            tool_target: Which tool(s) to get paths for:
                - "opencode": Only opencode.json
                - "claude-code": Only .mcp.json
                - "both": Both config files
                - None: Auto-detect installed tools

        Returns:
            List of MCP config file paths (may be empty if no tools installed)
        """
        if tool_target == "opencode":
            return [self._opencode_paths.mcp_config]
        elif tool_target == "claude-code":
            return [self._claude_code_paths.mcp_config]
        elif tool_target == "both":
            return [
                self._opencode_paths.mcp_config,
                self._claude_code_paths.mcp_config,
            ]
        else:
            # Auto-detect
            detected = self.detect()
            paths = []
            if detected.opencode:
                paths.append(self._opencode_paths.mcp_config)
            if detected.claude_code:
                paths.append(self._claude_code_paths.mcp_config)
            return paths

    def resolve_skill_install_dir(
        self, tool_target: Optional[ToolTarget] = None
    ) -> Optional[Path]:
        """Resolve the directory to install skills into.

        For installation, we need a single directory. This method resolves which
        one to use based on tool target and installation state.

        Args:
            tool_target: Which tool to install for:
                - "opencode": .opencode/skill/
                - "claude-code": .claude/skills/
                - "both": .opencode/skill/ (default, creates in both)
                - None: Auto-detect (prefer OpenCode if both installed)

        Returns:
            Path to install skills into, or None if no suitable directory
        """
        if tool_target == "opencode":
            return self._opencode_paths.skills_dir
        elif tool_target == "claude-code":
            return self._claude_code_paths.skills_dir
        elif tool_target == "both":
            # For "both", return OpenCode as primary (we'll handle duplication elsewhere)
            return self._opencode_paths.skills_dir
        else:
            # Auto-detect
            detected = self.detect()
            if detected.primary:
                paths = detected.get_paths(detected.primary)
                return paths.skills_dir if paths else None
            return None

    def get_memory_file_path(
        self, tool_target: Optional[ToolTarget] = None
    ) -> Optional[Path]:
        """Get the project memory file path (AGENTS.md or CLAUDE.md).

        Args:
            tool_target: Which tool to get the memory file for

        Returns:
            Path to the memory file, or None if no tool specified/detected
        """
        if tool_target == "opencode":
            return self._opencode_paths.memory_file
        elif tool_target == "claude-code":
            return self._claude_code_paths.memory_file
        else:
            detected = self.detect()
            if detected.primary:
                paths = detected.get_paths(detected.primary)
                return paths.memory_file if paths else None
            return None


# Convenience functions for common operations


def detect_tools(project_path: Path) -> DetectedTools:
    """Convenience function to detect installed tools.

    Args:
        project_path: Project directory to check

    Returns:
        DetectedTools instance
    """
    return ToolDetector(project_path).detect()


def get_skills_dir(
    project_path: Path, tool_target: Optional[ToolTarget] = None
) -> Optional[Path]:
    """Get the primary skills directory for a project.

    Args:
        project_path: Project directory
        tool_target: Optional tool to target

    Returns:
        Path to skills directory, or None if no tools installed
    """
    detector = ToolDetector(project_path)
    dirs = detector.get_skills_dirs(tool_target)
    return dirs[0] if dirs else None


def get_all_skills_dirs(project_path: Path) -> List[Path]:
    """Get all skills directories for installed tools.

    Args:
        project_path: Project directory

    Returns:
        List of skills directory paths for all installed tools
    """
    return ToolDetector(project_path).get_skills_dirs()
