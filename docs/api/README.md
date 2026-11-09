# API Documentation

The reference pages for the FINOS AI Governance MCP Server's MCP surface.

- **[MCP Tools Reference](mcp-tools.md)**: the 9 tools, the list, choose, get
  workflow and the document ids
- **[Response Schemas](response-schemas.md)**: each result and error as a
  client receives it
- **[Framework System Architecture](framework-architecture.md)**: how the
  server is assembled and how a call reaches a document
- **[Integration Guide](integration-guide.md)**: client code that calls the
  server
- **[Prompts and Resources Reference](../tools-reference.md)**: the 3 prompts
  and the resources

## Where else to look

- **Authentication, rate limits and every setting**: the
  [Deployment Guide](../deployment.md#settings)
- **The rate and concurrency limits a client meets**:
  [Rate Limiting](mcp-tools.md#rate-limiting)
- **The frameworks the server serves**: the
  [project README](../../README.md#supported-content); `list_frameworks`
  gives the current catalog
- **Caching**: [Caching Behavior](response-schemas.md#caching-behavior)

## Version Compatibility

- **MCP protocol**: the versions the `mcp` Python SDK 2.x negotiates
- **Python**: 3.11 or newer
- **Clients**: any MCP client that speaks stdio, or streamable HTTP for a
  server run over HTTP
