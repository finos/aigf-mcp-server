# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 3 Complete**: Framework Integration & Testing successfully completed
- **Framework Tools**: 5 new framework tools for governance reference access
  - `search_frameworks` - Cross-framework search with filtering
  - `list_frameworks` - Framework discovery and metadata
  - `get_framework_details` - Detailed framework information
  - `get_compliance_analysis` - Compliance metrics and analytics
  - `search_framework_references` - Framework-specific reference search
- **Multi-Framework Support**: NIST AI RMF, EU AI Act, OWASP LLM Top 10 integration
- **Performance Excellence**: Sub-0.1ms cached response times (1000x better than target)
- **Governance Content**: 200+ governance references across multiple frameworks
- **Test Coverage**: 438/438 tests passing with zero regressions
- Comprehensive security analysis stack (Semgrep + Bandit + Pylint)
- Performance optimization with intelligent caching and connection pooling
- Legal foundation with Apache 2.0 license and contributor guidelines
- Automated release pipeline with semantic versioning
- Production-ready containerization

### Changed
- **Project Scope**: Evolved from "AI Governance MCP Server" to "Governance Framework Reference System"
- **Tool Count**: Expanded from 10 to 15 total tools
- **Content Focus**: From AI-specific to comprehensive governance framework coverage
- **Architecture**: Enhanced with framework data loader and advanced search capabilities

### Performance
- **Response Times**: Achieved <0.1ms average response time across all framework tools
- **Search Performance**: 0.04ms average search time with intelligent indexing
- **Caching**: 3.9x performance improvement with multi-level caching
- **Data Loading**: Concurrent framework loading for improved startup time

### Security
- Zero-tolerance security policy with automated scanning
- No high severity issues allowed in releases
- Comprehensive vulnerability detection and prevention
- Secure coding practices enforcement

## [0.1.0] - 2024-12-06

### Added
- Initial development version
- Basic MCP server functionality
- FINOS AI Governance Framework integration
- Risk and mitigation content serving

[Unreleased]: https://github.com/finos/aigf-mcp-server/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/finos/aigf-mcp-server/releases/tag/v0.1.0
