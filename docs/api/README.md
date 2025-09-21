# FINOS MCP Server API Documentation

This directory contains comprehensive API documentation for the FINOS AI Governance Framework MCP Server.

## Documentation Structure

- **[MCP Tools Reference](mcp-tools.md)** - Complete reference for all 21 MCP tools
- **[Framework System Architecture](framework-architecture.md)** - Framework system design and patterns
- **[Response Schemas](response-schemas.md)** - Detailed response format documentation
- **[Error Handling](error-handling.md)** - Error codes and handling patterns
- **[Integration Guide](integration-guide.md)** - Integration patterns for developers

## Quick Reference

### Tool Categories

| Category | Tools Count | Purpose |
|----------|-------------|---------|
| **Framework Tools** | 11 tools | Governance framework navigation and compliance analysis |
| **FINOS Tools** | 4 tools | Original FINOS AI governance content access |
| **System Tools** | 4 tools | Service health monitoring and performance metrics |

### Core Framework Tools

- `search_frameworks` - Multi-framework content search
- `get_framework_details` - Framework metadata and structure
- `get_compliance_analysis` - Cross-framework compliance metrics
- `export_framework_data` - Export capabilities (JSON/CSV/Markdown)
- `find_compliance_gaps` - Gap analysis for multi-framework compliance

### Authentication & Rate Limiting

- **Authentication**: No authentication required for read-only operations
- **Rate Limiting**:
  - Tool calls: 50 requests/minute
  - Resource access: 200 requests/minute
- **Content Limits**: 10MB per resource, 50MB per tool response

## Framework Support

The server provides access to 7 governance frameworks:

| Framework | Type | Status | References |
|-----------|------|--------|------------|
| **NIST AI RMF** | Active | Production | 30+ controls |
| **EU AI Act** | Active | Production | 40+ articles |
| **OWASP LLM Top 10** | Active | Production | 10 vulnerabilities |
| **GDPR** | Active | Dynamic Loading | 9 sections |
| **CCPA** | Modeled | Static Data | 15 sections |
| **ISO 27001** | Modeled | Static Data | 25 controls |
| **SOC 2** | Modeled | Static Data | 20 criteria |

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
4. **Export Data**: Use `export_framework_data` for reports

## Version Compatibility

- **MCP Protocol**: 1.0+
- **Python**: 3.10+
- **Clients**: Claude, VS Code, Cursor, and other MCP-compatible tools

For detailed tool documentation, see [MCP Tools Reference](mcp-tools.md).
