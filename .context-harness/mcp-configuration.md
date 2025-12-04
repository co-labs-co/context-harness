# MCP Configuration Example

This file documents how Context7 MCP would be configured for the enhanced research subagent.

## MCP Server Configuration

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["@upstash/context7-mcp"],
      "env": {
        "UPSTASH_REDIS_REST_URL": "your-redis-url",
        "UPSTASH_REDIS_REST_TOKEN": "your-redis-token"
      }
    }
  }
}
```

## Available MCP Tools

### context7_search
Search for documentation in Context7's indexed libraries.

**Parameters**:
- `query`: Search query string
- `library`: Optional library filter
- `version`: Optional version filter

**Returns**:
- Relevant documentation sections
- Code examples
- API references
- Version-specific information

### context7_list_libraries
List all libraries available in Context7.

**Returns**:
- Array of supported libraries
- Latest versions
- Documentation coverage

## Integration Notes

The research subagent automatically:
1. Attempts Context7 MCP first for supported libraries
2. Falls back to web search if MCP unavailable
3. Cross-references information from multiple sources
4. Cites all sources with verification dates

## Supported Libraries (Partial List)

- **JavaScript/TypeScript**: React, Next.js, Express, Node.js
- **Python**: Flask, Django, FastAPI, SQLAlchemy
- **Databases**: PostgreSQL, MongoDB, Redis
- **Cloud**: AWS SDK v3, Google Cloud, Azure
- **Tools**: Docker, Kubernetes, Terraform

## Example MCP Query

```javascript
// Internal query example
const result = await mcp.context7_search({
  query: "JWT authentication middleware",
  library: "express",
  version: "4.18"
});
```

This documentation is for reference only. The actual MCP server must be configured separately in the OpenCode.ai environment.