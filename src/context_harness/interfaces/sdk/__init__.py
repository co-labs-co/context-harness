"""SDK package for ContextHarness.

Provides a high-level programmatic interface to ContextHarness functionality.
Use this SDK when you want to integrate ContextHarness into your Python
applications without using the CLI.

Example:
    from context_harness.interfaces.sdk import Client

    # Create a client
    client = Client()

    # Work with configuration
    config = client.config.load()
    client.config.add_mcp_server("context7")

    # Work with skills
    skills = client.skills.list_local()
    client.skills.install("react-forms")

    # Work with MCP servers
    servers = client.mcp.list_available()
    client.mcp.configure("atlassian")

    # Work with OAuth
    status = client.oauth.get_status("atlassian")
    client.oauth.authenticate("atlassian")
"""

from context_harness.interfaces.sdk.client import Client, create_client

__all__ = [
    "Client",
    "create_client",
]
