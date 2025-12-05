# Context7 MCP Configuration

This file documents how to configure Context7 MCP for ContextHarness agents.

## OpenCode Configuration

Add the following to your `opencode.json` to enable Context7 MCP:

### Basic Configuration

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

### With API Key (Higher Rate Limits)

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      },
      "enabled": true
    }
  }
}
```

Sign up for a free API key at [context7.com](https://context7.com).

## Tool Access in Agents

MCP tools are exposed using the MCP server name as a prefix. Since we name our MCP `context7`, all its tools are available as `context7_*`.

In agent definitions, use glob patterns to enable all Context7 tools:

```yaml
tools:
  "context7*": true
```

Or enable specific tools:

```yaml
tools:
  context7_resolve-library-id: true
  context7_get-library-docs: true
```

## Available Context7 Tools

Context7 MCP provides these tools:

### context7_resolve-library-id
Resolves a library name to its Context7 library ID.

**Use case**: Find the correct ID before fetching documentation.

### context7_get-library-docs
Fetches documentation for a specific library.

**Parameters**:
- `libraryId`: The Context7 library ID
- `topic`: Optional topic filter

**Returns**:
- Relevant documentation sections
- Code examples
- API references

## Integration with ContextHarness Agents

The research and documentation subagents are configured to use Context7:

| Agent | Tool Config | Purpose |
|-------|-------------|---------|
| `research-subagent` | `"context7*": true` | Grounded research with verified docs |
| `docs-subagent` | `"context7*": true` | Documentation lookup and summarization |

## Supported Libraries

Context7 provides documentation for popular libraries including:

- **JavaScript/TypeScript**: React, Next.js, Express, Node.js, Vue, Angular
- **Python**: Flask, Django, FastAPI, SQLAlchemy, Pandas
- **Databases**: PostgreSQL, MongoDB, Redis, MySQL
- **Cloud**: AWS SDK, Google Cloud, Azure SDK
- **Tools**: Docker, Kubernetes, Terraform, GitHub Actions

## Usage Tips

1. **Invoke Context7 explicitly**: Add "use context7" to prompts for explicit usage
2. **Library resolution**: Always resolve library ID first for best results
3. **Version awareness**: Context7 tracks library versions for accurate docs

## References

- [OpenCode MCP Servers Documentation](https://opencode.ai/docs/mcp-servers/)
- [Context7 GitHub Repository](https://github.com/upstash/context7)
- [Context7 MCP Example](https://opencode.ai/docs/mcp-servers/#context7)
