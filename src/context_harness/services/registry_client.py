"""Registry client abstraction for ContextHarness skills.

Provides a Protocol-based abstraction for skill registry operations,
supporting multiple backends (GitHub, HTTP, etc.).

This module enables organizations to host skill registries without
GitHub dependency, using any HTTP(S) endpoint.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class RegistryType(Enum):
    """Supported registry backend types."""

    GITHUB = "github"
    HTTP = "http"


class AuthType(Enum):
    """Supported authentication types for HTTP registries."""

    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"


@dataclass
class RegistryAuth:
    """Authentication configuration for registry access.

    Attributes:
        type: Authentication type (bearer, api_key, basic, none)
        token_env: Environment variable name containing the token
        header_name: Custom header name for API key auth (default: X-API-Key)
        username_env: Environment variable for basic auth username
        password_env: Environment variable for basic auth password
    """

    type: AuthType = AuthType.NONE
    token_env: Optional[str] = None
    header_name: str = "X-API-Key"
    username_env: Optional[str] = None
    password_env: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegistryAuth":
        """Create from dictionary."""
        auth_type_str = data.get("type", "none").lower()
        auth_type = AuthType(auth_type_str) if auth_type_str in [e.value for e in AuthType] else AuthType.NONE

        return cls(
            type=auth_type,
            token_env=data.get("token_env"),
            header_name=data.get("header_name", "X-API-Key"),
            username_env=data.get("username_env"),
            password_env=data.get("password_env"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {"type": self.type.value}
        if self.token_env:
            result["token_env"] = self.token_env
        if self.header_name != "X-API-Key":
            result["header_name"] = self.header_name
        if self.username_env:
            result["username_env"] = self.username_env
        if self.password_env:
            result["password_env"] = self.password_env
        return result

    def get_token(self) -> Optional[str]:
        """Get the auth token from environment variable."""
        if self.token_env:
            return os.environ.get(self.token_env)
        return None

    def get_username(self) -> Optional[str]:
        """Get the username from environment variable."""
        if self.username_env:
            return os.environ.get(self.username_env)
        return None

    def get_password(self) -> Optional[str]:
        """Get the password from environment variable."""
        if self.password_env:
            return os.environ.get(self.password_env)
        return None


@dataclass
class RegistryConfig:
    """Configuration for a skill registry.

    Attributes:
        type: Registry type (github, http)
        url: Registry URL (e.g., "https://registry.example.com/skills" or "owner/repo")
        auth: Authentication configuration
    """

    type: RegistryType = RegistryType.GITHUB
    url: str = ""
    auth: RegistryAuth = field(default_factory=RegistryAuth)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegistryConfig":
        """Create from dictionary."""
        type_str = data.get("type", "github").lower()
        reg_type = RegistryType(type_str) if type_str in [e.value for e in RegistryType] else RegistryType.GITHUB

        auth_data = data.get("auth", {})
        auth = RegistryAuth.from_dict(auth_data) if auth_data else RegistryAuth()

        return cls(
            type=reg_type,
            url=data.get("url", ""),
            auth=auth,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {
            "type": self.type.value,
            "url": self.url,
        }
        if self.auth.type != AuthType.NONE:
            result["auth"] = self.auth.to_dict()
        return result

    @classmethod
    def github(cls, repo: str) -> "RegistryConfig":
        """Create a GitHub registry config."""
        return cls(type=RegistryType.GITHUB, url=repo)

    @classmethod
    def http(cls, url: str, auth: Optional[RegistryAuth] = None) -> "RegistryConfig":
        """Create an HTTP registry config."""
        return cls(
            type=RegistryType.HTTP,
            url=url,
            auth=auth or RegistryAuth(),
        )


class RegistryClient(Protocol):
    """Protocol for skill registry operations.

    Allows for dependency injection and multi-backend support.
    Supports GitHub, HTTP, and future backends (OCI, S3, etc.).
    """

    def check_auth(self) -> bool:
        """Check if authenticated with the registry.

        Returns:
            True if authentication is valid, False otherwise
        """
        ...

    def check_access(self) -> bool:
        """Check if the registry is accessible.

        Returns:
            True if registry is accessible, False otherwise
        """
        ...

    def fetch_manifest(self) -> Optional[str]:
        """Fetch the skills.json manifest.

        Returns:
            JSON string of the manifest, or None on failure
        """
        ...

    def fetch_file(self, path: str) -> Optional[bytes]:
        """Fetch a single file from the registry.

        Args:
            path: Path to the file relative to registry root

        Returns:
            File contents as bytes, or None on failure
        """
        ...

    def fetch_directory(self, path: str, dest: Path) -> bool:
        """Fetch a directory recursively from the registry.

        Args:
            path: Path to the directory relative to registry root
            dest: Local destination path

        Returns:
            True on success, False on failure
        """
        ...


class GitHubRegistryClient:
    """GitHub registry client using gh CLI.

    Uses the GitHub Contents API via the gh CLI tool.
    This is the default backend for backward compatibility.
    """

    def __init__(self, repo: str):
        """Initialize the GitHub registry client.

        Args:
            repo: Repository in owner/repo format
        """
        self.repo = repo

    def check_auth(self) -> bool:
        """Check if GitHub CLI is authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def check_access(self) -> bool:
        """Check if the repository is accessible."""
        result = subprocess.run(
            ["gh", "api", f"/repos/{self.repo}", "--silent"],
            capture_output=True,
        )
        return result.returncode == 0

    def fetch_manifest(self) -> Optional[str]:
        """Fetch the skills.json manifest from GitHub."""
        return self._fetch_file_content("skills.json")

    def fetch_file(self, path: str) -> Optional[bytes]:
        """Fetch a single file from GitHub."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"/repos/{self.repo}/contents/{path}",
                    "-H",
                    "Accept: application/vnd.github.raw+json",
                ],
                capture_output=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None

    def fetch_directory(self, path: str, dest: Path) -> bool:
        """Fetch a directory recursively from GitHub."""
        try:
            result = subprocess.run(
                ["gh", "api", f"/repos/{self.repo}/contents/{path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            contents = json.loads(result.stdout)

            if isinstance(contents, dict):
                contents = [contents]

            dest.mkdir(parents=True, exist_ok=True)

            for item in contents:
                item_name = item["name"]
                item_path = dest / item_name

                if item["type"] == "file":
                    file_result = subprocess.run(
                        [
                            "gh",
                            "api",
                            item["url"],
                            "-H",
                            "Accept: application/vnd.github.raw+json",
                        ],
                        capture_output=True,
                        check=True,
                    )
                    item_path.write_bytes(file_result.stdout)

                elif item["type"] == "dir":
                    if not self.fetch_directory(item["path"], item_path):
                        return False

            return True

        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return False

    def _fetch_file_content(self, path: str) -> Optional[str]:
        """Fetch a file's content as string."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"/repos/{self.repo}/contents/{path}",
                    "-H",
                    "Accept: application/vnd.github.raw+json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None


class HttpRegistryClient:
    """HTTP(S) registry client.

    Fetches skills from any HTTP(S) endpoint serving the standard
    registry directory structure:

        /skills.json              # Manifest
        /skill/<name>/SKILL.md    # Skill definition
        /skill/<name>/version.txt # Version
        /skill/<name>/references/ # Additional docs

    Supports Bearer token, API key header, and Basic authentication.
    """

    def __init__(self, base_url: str, auth: Optional[RegistryAuth] = None):
        """Initialize the HTTP registry client.

        Args:
            base_url: Base URL for the registry (e.g., "https://registry.example.com/skills")
            auth: Authentication configuration
        """
        self.base_url = base_url.rstrip("/")
        self.auth = auth or RegistryAuth()

    def check_auth(self) -> bool:
        """Check if authentication is configured and valid.

        For HTTP registries, we check if auth is configured.
        Actual validation happens on first request.
        """
        if self.auth.type == AuthType.NONE:
            return True  # No auth required

        if self.auth.type == AuthType.BEARER:
            return self.auth.get_token() is not None

        if self.auth.type == AuthType.API_KEY:
            return self.auth.get_token() is not None

        if self.auth.type == AuthType.BASIC:
            return (
                self.auth.get_username() is not None
                and self.auth.get_password() is not None
            )

        return False

    def check_access(self) -> bool:
        """Check if the registry endpoint is accessible."""
        try:
            request = self._build_request(f"{self.base_url}/skills.json")
            with urlopen(request, timeout=10) as response:
                return response.status == 200
        except (HTTPError, URLError, OSError):
            return False

    def fetch_manifest(self) -> Optional[str]:
        """Fetch the skills.json manifest from HTTP endpoint."""
        content = self._fetch_file("skills.json")
        if content:
            return content.decode("utf-8")
        return None

    def fetch_file(self, path: str) -> Optional[bytes]:
        """Fetch a single file from HTTP endpoint."""
        return self._fetch_file(path)

    def fetch_directory(self, path: str, dest: Path) -> bool:
        """Fetch a directory from HTTP endpoint.

        For HTTP registries, this implementation relies on per-file fetches.
        It first attempts to use an optional directory listing (e.g.,
        a JSON manifest describing files and subdirectories); if no listing is
        available, it falls back to fetching a small set of common files.

        Note: This implementation assumes the registry serves individual files.
        For better performance, registries should provide archive endpoints.
        """
        # For HTTP, we need to know what files exist.
        # We'll fetch the skill's SKILL.md first to validate,
        # then fetch common files.

        dest.mkdir(parents=True, exist_ok=True)

        # Common skill files to fetch
        common_files = [
            "SKILL.md",
            "version.txt",
        ]

        # First, try to fetch a file listing if the registry provides one
        # (This is optional - registries may not support it)
        listing = self._fetch_directory_listing(path)

        files_to_fetch = common_files[:]
        dirs_to_fetch = []

        if listing:
            files_to_fetch = listing.get("files", common_files)
            dirs_to_fetch = listing.get("directories", [])

        # Fetch files
        for filename in files_to_fetch:
            # Validate filename to prevent path traversal
            if not self._is_safe_path_component(filename):
                continue  # Skip potentially malicious filenames
            file_path = f"{path}/{filename}"
            content = self._fetch_file(file_path)
            if content:
                (dest / filename).write_bytes(content)

        # Fetch directories (like references/, scripts/, assets/)
        for dirname in dirs_to_fetch:
            # Validate dirname to prevent path traversal
            if not self._is_safe_path_component(dirname):
                continue  # Skip potentially malicious dirnames
            dir_path = f"{path}/{dirname}"
            dir_dest = dest / dirname
            # Ensure resolved path stays within dest
            try:
                dir_dest.resolve().relative_to(dest.resolve())
            except ValueError:
                continue  # Path traversal attempt, skip
            if not self.fetch_directory(dir_path, dir_dest):
                # Continue even if subdirectory fetch fails
                pass

        # Check if we got at least the SKILL.md
        return (dest / "SKILL.md").exists()

    def _is_safe_path_component(self, component: str) -> bool:
        """Check if a path component is safe (no path traversal).

        Args:
            component: A filename or directory name

        Returns:
            True if the component is safe, False otherwise
        """
        if not component:
            return False
        # Reject absolute paths, parent references, and path separators
        if component.startswith("/") or component.startswith("\\"):
            return False
        if ".." in component:
            return False
        if "/" in component or "\\" in component:
            return False
        return True

    def _fetch_file(self, path: str) -> Optional[bytes]:
        """Fetch a file from the HTTP endpoint."""
        try:
            url = f"{self.base_url}/{path}"
            request = self._build_request(url)
            with urlopen(request, timeout=30) as response:
                return response.read()
        except (HTTPError, URLError, OSError):
            return None

    def _fetch_directory_listing(self, path: str) -> Optional[Dict[str, Any]]:
        """Try to fetch a directory listing if available.

        Some registries may provide a .listing.json file for each directory.
        """
        try:
            listing_content = self._fetch_file(f"{path}/.listing.json")
            if listing_content:
                return json.loads(listing_content.decode("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def _build_request(self, url: str) -> Request:
        """Build an HTTP request with authentication headers."""
        request = Request(url)

        if self.auth.type == AuthType.NONE:
            return request

        if self.auth.type == AuthType.BEARER:
            token = self.auth.get_token()
            if token:
                request.add_header("Authorization", f"Bearer {token}")

        elif self.auth.type == AuthType.API_KEY:
            token = self.auth.get_token()
            if token:
                request.add_header(self.auth.header_name, token)

        elif self.auth.type == AuthType.BASIC:
            import base64

            username = self.auth.get_username() or ""
            password = self.auth.get_password() or ""
            credentials = base64.b64encode(
                f"{username}:{password}".encode("utf-8")
            ).decode("ascii")
            request.add_header("Authorization", f"Basic {credentials}")

        return request


def create_registry_client(config: RegistryConfig) -> RegistryClient:
    """Factory function to create the appropriate registry client.

    Args:
        config: Registry configuration

    Returns:
        RegistryClient implementation for the configured backend
    """
    if config.type == RegistryType.HTTP:
        return HttpRegistryClient(config.url, config.auth)
    else:
        # Default to GitHub
        return GitHubRegistryClient(config.url)
