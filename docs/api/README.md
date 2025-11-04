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

- **Authentication**: No authentication required for read-only operations
- **Rate Limiting**:
  - Tool calls: 50 requests/minute
  - Resource access: 200 requests/minute
- **Content Limits**: 10MB per resource, 50MB per tool response

## Framework Support

The server provides access to 5 governance frameworks:

| Framework | Type | Status | Description |
|-----------|------|--------|-------------|
| **NIST AI 600-1** | Active | Production | US federal AI governance framework |
| **EU AI Act 2024** | Active | Production | European Union AI regulation |
| **GDPR** | Active | Dynamic Loading | General Data Protection Regulation |
| **OWASP LLM Top 10** | Active | Production | AI security best practices |
| **ISO/IEC 23053** | Active | Production | International AI standards |

## Performance Characteristics

- **Response Time**: Sub-0.1ms for cached content
- **Concurrent Users**: Supports 100+ simultaneous connections
- **Memory Usage**: <500MB base memory footprint
- **Cache Hit Rate**: >95% for framework data
- **Uptime**: >99.9% availability target

## Getting Started

1. **Installation**: See [Setup Guide](../README.md)
2. **First API Call**: Start with `list_frameworks`
3. **Search Content**: Use `search_frameworks` for general queries
4. **Get Details**: Use `get_framework` to retrieve complete framework content

## Version Compatibility

- **MCP Protocol**: 1.0+
- **Python**: 3.10+
- **Clients**: Claude, VS Code, Cursor, and other MCP-compatible tools

For detailed tool documentation, see [MCP Tools Reference](mcp-tools.md).
