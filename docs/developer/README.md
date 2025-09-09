# 🛠️ Developer Documentation

Welcome to the developer documentation for the AI Governance MCP Server. This section provides comprehensive resources for contributors, maintainers, and anyone extending or modifying the server.

## 🏗️ Getting Started as a Developer

New to contributing? Follow this path:

1. **[Contributing Guidelines](CONTRIBUTING.md)** - Essential contribution requirements
2. **[Development Guide](development-guide.md)** - Set up your local environment
3. **[API Reference](api-reference.md)** - Technical API documentation

## 📚 Developer Resources

### Core Development Guides
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project
- **[Development Guide](development-guide.md)** - Local development environment setup
- **[API Reference](api-reference.md)** - Technical API documentation

### Code Quality & Standards

## 🎯 Developer Audience

This documentation is designed for:

- **New Contributors** looking to make their first contribution
- **Active Maintainers** managing the project
- **External Developers** integrating or extending the server
- **Security Researchers** analyzing the codebase
- **DevOps Engineers** understanding the project architecture

## 🚀 What You'll Master

After reading this documentation, you'll be able to:

- ✅ Set up a complete development environment
- ✅ Understand the entire system architecture
- ✅ Write high-quality, tested code following our standards
- ✅ Debug issues effectively using our tools and techniques
- ✅ Contribute new features and improvements
- ✅ Review and merge pull requests
- ✅ Optimize performance and security

## 🏛️ System Architecture Overview

The AI Governance MCP Server is built with:

### Core Components
- **MCP Server Implementation** - Model Context Protocol compliance
- **Content Management** - Document fetching, caching, and parsing
- **Security Layer** - Input validation, rate limiting, and audit logging
- **Health Monitoring** - Service health and performance tracking

### Key Design Principles
- **🔒 Security First** - Zero-tolerance security approach
- **⚡ Performance Optimized** - Caching, connection pooling, async operations
- **🛡️ Resilient Architecture** - Error boundaries, circuit breakers, graceful degradation
- **🧪 Test-Driven** - Comprehensive test coverage with quality gates
- **📊 Observable** - Comprehensive logging and health monitoring

## 🔧 Development Workflow

Our development process emphasizes quality and security:

### Quality Gates
- **Code Quality**: Pylint score 9.5+ (currently 9.72/10)
- **Security Scanning**: Zero high/critical vulnerabilities
- **Test Coverage**: 85%+ minimum coverage
- **Type Safety**: Full MyPy type checking

### Development Process
1. **Fork & Branch** - Create feature branch from main
2. **Develop** - Follow coding standards and write tests
3. **Quality Check** - Run comprehensive quality validation
4. **Submit PR** - Create pull request with detailed description
5. **Review** - Code review and automated checks
6. **Merge** - Merge after all checks pass

## 🛡️ Security Standards

All code contributions must meet strict security requirements:

- **Input Validation** - All inputs validated with Pydantic schemas
- **Dependency Security** - Regular vulnerability scanning
- **Secrets Management** - No hardcoded secrets or credentials
- **Audit Logging** - All security-relevant operations logged
- **Principle of Least Privilege** - Minimal required permissions

## 📋 Code Organization

```
src/finos_mcp/
├── __init__.py              # Package entry point
├── server.py                # Main MCP server implementation
├── config.py                # Configuration management
├── logging.py               # Centralized logging
├── content/                 # Content management domain
│   ├── cache.py             # Caching layer
│   ├── discovery.py         # Content discovery
│   ├── fetch.py             # HTTP client with circuit breaker
│   ├── parse.py             # Frontmatter parsing
│   └── service.py           # Content service orchestration
├── security/                # Security domain
│   ├── rate_limit.py        # Rate limiting
│   └── validators.py        # Input validation
├── health/                  # Health monitoring domain
│   └── monitor.py           # Health monitoring
└── tools/                   # MCP tools implementation
    ├── details.py           # Document details tool
    ├── listing.py           # Document listing tool
    ├── search.py            # Search tool
    └── system.py            # System tools
```

## 🧪 Testing Philosophy

We maintain comprehensive testing coverage:

- **Unit Tests** - Test individual components in isolation
- **Integration Tests** - Test component interactions
- **End-to-End Tests** - Test complete workflows
- **Security Tests** - Validate security controls
- **Performance Tests** - Ensure performance requirements

## 🔗 Related Documentation

- **[User Documentation](../user/)** - For end users of the server
- **[Operations Documentation](../operations/)** - For production deployment
- **[Governance Documentation](../governance/)** - For project governance

## 📞 Developer Support

Need development assistance?

- 💬 **Technical Questions**: [GitHub Discussions](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 🔒 **Security Issues**: Create a private security issue on GitHub

---

> **Ready to contribute?** Start with our [Contributing Guidelines](CONTRIBUTING.md) to understand our development process and quality standards.
