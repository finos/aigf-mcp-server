# FINOS MCP Server API Documentation

This directory contains comprehensive API documentation for the FINOS AI Governance Framework MCP Server.

## Documentation Structure

- **[MCP Tools Reference](mcp-tools.md)** - Complete reference for all 11 MCP tools
- **[Framework System Architecture](framework-architecture.md)** - Framework system design and patterns
- **[Response Schemas](response-schemas.md)** - Detailed response format documentation
- **[Error Handling](error-handling.md)** - Error codes and handling patterns
- **[Integration Guide](integration-guide.md)** - Integration patterns for developers

## Quick Reference

### Tool Categories

| Category | Tools Count | Purpose |
|----------|-------------|---------|
| **Framework Access Tools** | 5 tools | List, retrieve, and search governance frameworks |
| **Risk & Mitigation Tools** | 4 tools | Access and search AI governance risks and mitigations |
| **System Monitoring Tools** | 2 tools | Service health monitoring and performance metrics |

### Framework Access Tools

- `list_frameworks` - List all available AI governance frameworks
- `get_framework` - Get complete content of a specific framework
- `search_frameworks` - Search for text within framework documents
- `list_risks` - List all available risk documents
- `get_risk` - Get complete content of specific risk documents

### Risk & Mitigation Tools

- `search_risks` - Search within risk documentation
- `list_mitigations` - List all available mitigation documents
- `get_mitigation` - Get complete content of specific mitigation documents
- `search_mitigations` - Search within mitigation documentation

### System Monitoring Tools

- `get_service_health` - Get service health status and metrics
- `get_cache_stats` - Get cache performance statistics

### Authentication & Rate Limiting

- **Authentication**: Optional JWT boundary auth via `FINOS_MCP_MCP_AUTH_*` environment variables (recommended for production)
- **Rate Limiting**: Configurable DoS protection (`FINOS_MCP_DOS_*`)
  - Default: 600 requests/minute per client
  - Default: 10 concurrent requests per client
- **Content Limits**:
  - Tool result size validation: 5MB default
  - Resource/document payload validation: 1MB default

## Framework Support

Framework catalog entries are discovered dynamically from the configured upstream
repository at runtime. Use `list_frameworks` to retrieve the current available set.

## Runtime Characteristics

- Cached responses are typically fast; exact latency depends on host and load.
- Uncached/discovery requests depend on upstream GitHub API/network conditions.
- Health and cache tools expose runtime metrics via:
  - `get_service_health`
  - `get_cache_stats`

## Getting Started

1. **Installation**: See [Setup Guide](../README.md)
2. **First API Call**: Start with `list_frameworks`
3. **Search Content**: Use `search_frameworks` for general queries
4. **Get Details**: Use `get_framework` to retrieve complete framework content

## Version Compatibility

- **MCP Protocol**: FastMCP-based implementation aligned with current project runtime
- **Python**: 3.10+
- **Clients**: Claude, VS Code, Cursor, and other MCP-compatible tools

For detailed tool documentation, see [MCP Tools Reference](mcp-tools.md).
