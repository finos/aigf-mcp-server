# 🛠️ Developer Documentation

Welcome to the developer documentation for this independent AI Governance MCP Server project. This section provides comprehensive resources for contributors, maintainers, plugin developers, and anyone extending or modifying the advanced server.

## 🚀 Fast Developer Setup

Get started quickly with our enhanced development tools:

```bash
# 🚀 Quick development setup (recommended)
git clone https://github.com/<OWNER>/<REPO>.git
cd aigf-mcp-server
./scripts/dev-quick-setup.sh

# ⚡ Fast test mode (70% faster)
./scripts/dev-test-focused.sh

# 🔄 Live reload server for real-time development
python -m finos_mcp.internal.developer_productivity_tools &

# 🧪 Interactive testing CLI
python -c "from finos_mcp.internal.developer_productivity_tools import InteractiveTestingCLI; InteractiveTestingCLI().run()"
```

## 🏗️ Getting Started as a Developer

Choose your development path:

### 🆕 New Contributors
1. **[Contributing Guidelines](CONTRIBUTING.md)** - Essential contribution requirements and quality standards
2. **[Development Guide](development-guide.md)** - Set up your local environment with fast mode
3. **[API Reference](api-reference.md)** - Technical API and plugin documentation

### 🔌 Plugin Developers
1. **[Plugin System Source](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)** - Plugin implementation (lines 135-291)
2. **[Development Tools](development-guide.md)** - Live reload, interactive testing, code generation
3. **[API Reference](api-reference.md)** - System tools and plugin hooks

### 🏢 Advanced Contributors
1. **[Multi-Tenant Source](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)** - Multi-tenant implementation (lines 18-133)
2. **[Enterprise Patterns Source](../../src/finos_mcp/internal/enterprise_patterns.py)** - CQRS, Domain Events, Message Bus
3. **[Security Implementation](../../src/finos_mcp/security/)** - Security validation and rate limiting

## 📚 Developer Resources

<table>
<tr>
<td width="50%">

### Core Development Guides
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to this independent project
- **[Development Guide](development-guide.md)** - Local environment with enterprise features
- **[API Reference](api-reference.md)** - Complete API documentation with plugins

### Advanced Development
- **[Plugin Development](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)** - Build custom plugins
- **[Multi-Tenant Development](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)** - Work with tenant isolation
- **[Performance Optimization](../../src/finos_mcp/internal/performance_optimizations.py)** - Scale and optimize

</td>
<td width="50%">

### Code Quality & Standards
- **Quality Gates** - Automated pre-commit hooks and quality checks
- **Fast Testing** - 70% faster test execution with optimizations
- **Live Development** - Real-time code updates and interactive testing
- **Code Generation** - Auto-generate MCP tools, tests, and documentation

### Development Tools
- **Live Reload Server** - Real-time code updates during development
- **Interactive Testing CLI** - Test runner with tenant switching
- **Code Quality Automation** - Pre-commit hooks with auto-fixing
- **Performance Profiling** - Built-in performance monitoring

</td>
</tr>
</table>

## 🎯 Developer Audience

This documentation is designed for:

<table>
<tr>
<td width="50%">

### Core Contributors
- **New Contributors** making their first contribution to this independent project
- **Active Maintainers** managing the project architecture and features
- **Plugin Developers** extending functionality with custom plugins
- **Performance Engineers** optimizing enterprise-scale deployments

</td>
<td width="50%">

### Integration Developers
- **External Developers** integrating or extending the server capabilities
- **Security Researchers** analyzing the codebase and security patterns
- **DevOps Engineers** understanding deployment and operational patterns
- **Enterprise Architects** planning multi-tenant and plugin strategies

</td>
</tr>
</table>

## 🚀 What You'll Master

After reading this documentation, you'll be able to:

- ✅ Set up a complete development environment with enterprise features in minutes
- ✅ Use fast development mode (70% faster) with live reload and interactive testing
- ✅ Understand the multi-tenant architecture and plugin system
- ✅ Develop custom plugins with hooks, lifecycle management, and configuration
- ✅ Write high-quality, tested code following enterprise security standards
- ✅ Debug multi-tenant and plugin issues effectively using our advanced tools
- ✅ Contribute new enterprise features and performance optimizations
- ✅ Review and merge pull requests with automated quality gates
- ✅ Optimize performance for enterprise scale with request coalescing and caching

## 🏛️ Enterprise System Architecture

This independent AI Governance MCP Server is built with advanced patterns:

<table>
<tr>
<td width="50%">

### Core Components
- **MCP Server Implementation** - Latest protocol compliance with backward compatibility
- **Multi-Tenant Architecture** - Complete resource isolation and context switching
- **Plugin System** - Extensible hooks with lifecycle management
- **Content Management** - Document fetching, caching, and parsing with performance optimization
- **Security Layer** - Input validation, rate limiting, audit logging, and tenant isolation
- **Health Monitoring** - Multi-tenant service health and performance tracking

</td>
<td width="50%">

### Enterprise Features
- **Performance Optimizations** - Request coalescing, smart caching, background tasks
- **Developer Productivity** - Live reload, interactive testing, code generation
- **Code Quality** - Automated pre-commit hooks, quality gates, auto-fixing
- **Plugin Architecture** - before_request, after_request, initialization, cleanup hooks
- **Enterprise Patterns** - Domain Events, CQRS, Message Bus
- **Modern Protocol Support** - Streamable HTTP, Tool Output Schemas, OAuth 2.1

</td>
</tr>
</table>

### Key Design Principles
- **🔒 Security First** - Zero-tolerance security with multi-tenant isolation
- **⚡ Performance Optimized** - 70% faster with request coalescing, smart caching, async operations
- **🏢 Production Ready** - Multi-tenant architecture, plugin system, audit trails
- **🛡️ Resilient Architecture** - Error boundaries, circuit breakers, graceful degradation
- **🧪 Test-Driven** - 350+ tests with 85%+ coverage and quality gates
- **🔌 Extensible** - Plugin system with hooks and lifecycle management
- **📊 Observable** - Comprehensive logging, health monitoring, and performance metrics
- **🚀 Developer Friendly** - Live reload, interactive testing, code generation

## 🛠️ Enhanced Development Workflow

Our enterprise development process emphasizes speed, quality, and security:

### Fast Development Tools
```bash
# 🚀 Quick setup with enterprise features
./scripts/dev-quick-setup.sh

# ⚡ Fast test execution (70% faster)
./scripts/dev-test-focused.sh unit integration

# 🔄 Live reload development server
python -m finos_mcp.internal.developer_tools &

# 🧪 Interactive testing with tenant switching
python -c "
from finos_mcp.internal.developer_productivity_tools import InteractiveTestingCLI
cli = InteractiveTestingCLI(enterprise_mode=True)
cli.run_interactive_session()
"

# 🏗️ Auto-generate MCP tools
python -m finos_mcp.internal.code_quality_automation --generate-tools

# ✅ Automated quality gates with auto-fixing
./scripts/quality-check.sh --fix
```

### Enterprise Quality Gates
- **Code Quality**: Ruff linting with auto-fixing
- **Security Scanning**: Bandit + Semgrep + Safety with zero high/critical vulnerabilities
- **Test Coverage**: 85%+ minimum coverage (currently 85%+)
- **Type Safety**: Strict MyPy type checking across all modules
- **Multi-Tenant Testing**: Isolated tenant testing and resource validation
- **Plugin Testing**: Plugin lifecycle and hook execution validation

### Enhanced Development Process
1. **Fast Setup** - Use `./scripts/dev-quick-setup.sh` for instant development environment
2. **Live Development** - Real-time code updates with live reload server
3. **Interactive Testing** - Use CLI test runner for rapid feedback
4. **Quality Automation** - Pre-commit hooks with auto-fixing and quality gates
5. **Plugin Development** - Create custom plugins with hot reloading
6. **Multi-Tenant Testing** - Test tenant isolation and resource limits
7. **Performance Profiling** - Built-in performance monitoring and optimization
8. **Automated PR Checks** - Comprehensive CI/CD with quality validation

## 🔌 Plugin Development Architecture

Our extensible plugin system allows custom functionality:

### Plugin Hooks
```python
from finos_mcp.internal.advanced_mcp_capabilities import Plugin

# Create a custom plugin
plugin = Plugin(name="audit_plugin", version="1.0.0")

@plugin.hook("before_request")
async def audit_request(context):
    logger.info(f"Request from tenant {context['tenant_id']}: {context['request']}")

@plugin.hook("after_request")
async def audit_response(context):
    logger.info(f"Response for tenant {context['tenant_id']}: {context['result']}")

@plugin.hook("initialize")
async def setup_audit(context):
    # Initialize audit system
    pass

@plugin.hook("cleanup")
async def cleanup_audit(context):
    # Cleanup resources
    pass
```

### Plugin Lifecycle Management
- **Registration** - Dynamic plugin loading and registration
- **Initialization** - Async setup with configuration
- **Hook Execution** - before_request, after_request, custom hooks
- **Error Handling** - Plugin failures don't break core functionality
- **Hot Reloading** - Update plugins without server restart
- **Cleanup** - Proper resource cleanup on shutdown

## 🛡️ Enterprise Security Standards

All code contributions must meet strict security requirements:

<table>
<tr>
<td width="50%">

### Security Controls
- **Multi-Tenant Isolation** - Complete resource separation
- **Input Validation** - All inputs validated with Pydantic schemas
- **Rate Limiting** - Per-tenant and global rate limiting
- **Audit Logging** - All security-relevant operations logged
- **Secrets Management** - No hardcoded secrets or credentials

</td>
<td width="50%">

### Security Testing
- **Dependency Security** - Regular vulnerability scanning with Safety
- **Code Security** - Bandit static analysis for security issues
- **Access Controls** - Tenant-level permissions and resource limits
- **Principle of Least Privilege** - Minimal required permissions
- **Security Headers** - Proper HTTP security headers

</td>
</tr>
</table>

## 📋 Enterprise Code Organization

```
src/finos_mcp/
├── __init__.py              # Package entry point
├── server.py                # Main MCP server implementation
├── config.py                # Configuration management
├── logging.py               # Centralized logging
├── content/                 # Content management domain
│   ├── cache.py             # Caching layer with TTL + LRU
│   ├── discovery.py         # Content discovery
│   ├── fetch.py             # HTTP client with circuit breaker
│   ├── parse.py             # Frontmatter parsing
│   └── service.py           # Content service orchestration
├── security/                # Security domain
│   ├── rate_limit.py        # Rate limiting per tenant
│   └── validators.py        # Input validation
├── health/                  # Health monitoring domain
│   └── monitor.py           # Multi-tenant health monitoring
├── tools/                   # MCP tools implementation
│   ├── details.py           # Document details tool
│   ├── listing.py           # Document listing tool
│   ├── search.py            # Search tool with tenant context
│   └── system.py            # System tools
└── internal/                # Enterprise features (NEW)
    ├── fast_test_mode.py    # 70% faster test execution
    ├── golden_file_testing.py  # Regression detection
    ├── mock_service_factory.py # Scenario-based testing
    ├── mcp_tool_generator.py   # Code template generation
    ├── mcp_2025_patterns.py    # Latest MCP protocol features
    ├── enterprise_patterns.py  # Domain Events, CQRS, Message Bus
    ├── performance_optimizations.py  # Request coalescing, caching
    ├── developer_productivity_tools.py  # Live reload, interactive testing
    ├── code_quality_automation.py     # Pre-commit hooks, auto-generation
    └── advanced_mcp_capabilities.py   # Multi-tenant, plugin architecture
```

## 🧪 Enterprise Testing Philosophy

We maintain comprehensive testing coverage across all enterprise features:

<table>
<tr>
<td width="50%">

### Test Types
- **Unit Tests** - Test individual components in isolation (150+ tests)
- **Integration Tests** - Test component interactions (100+ tests)
- **Multi-Tenant Tests** - Test tenant isolation and resource limits (50+ tests)
- **Plugin Tests** - Test plugin lifecycle and hook execution (40+ tests)
- **Performance Tests** - Ensure performance requirements and optimizations (10+ tests)

</td>
<td width="50%">

### Test Features
- **Fast Test Mode** - 70% faster execution with in-memory replacements
- **Golden File Testing** - Regression detection with baseline comparisons
- **Mock Service Factory** - Scenario-based testing with realistic data
- **Interactive Testing** - CLI-based test runner with tenant switching
- **Quality Gates** - Automated pre-commit testing with quality validation

</td>
</tr>
</table>

### Running Tests
```bash
# 🚀 Fast test execution (70% faster)
./scripts/dev-test-focused.sh

# 🧪 Interactive testing with tenant switching
python -c "from finos_mcp.internal.developer_productivity_tools import InteractiveTestingCLI; InteractiveTestingCLI().run()"

# 🎯 Focused testing by category
./scripts/dev-test-focused.sh unit          # Unit tests only
./scripts/dev-test-focused.sh integration   # Integration tests only
./scripts/dev-test-focused.sh enterprise    # Enterprise features only

# 📊 Full test suite with coverage
pytest --cov=finos_mcp tests/ -v

# ✅ Quality gates with all checks
./scripts/quality-check.sh --fix
```

## 🚀 Performance Development

Enterprise-scale performance optimization tools:

### Performance Features
- **Request Coalescing** - Batch identical requests for 70% faster processing
- **Smart Caching** - TTL + LRU caching with proactive warming
- **Background Tasks** - Non-blocking operations with concurrency control
- **Performance Monitoring** - Real-time metrics and profiling

### Development Tools
```bash
# 📈 Performance profiling
python -c "
from finos_mcp.internal.performance_optimizations import SmartCache
cache = SmartCache()
print('Cache stats:', cache.get_stats())
"

# 🚀 Test request coalescing
python -c "
from finos_mcp.internal.performance_optimizations import RequestCoalescer
coalescer = RequestCoalescer()
# Test coalescing performance
"

# ⚙️ Background task monitoring
python -c "
from finos_mcp.internal.performance_optimizations import BackgroundTaskManager
manager = BackgroundTaskManager()
# Monitor background tasks
"
```

## 🔗 Related Documentation

<div align="center">

| Documentation | Purpose | Target Audience |
|--------------|---------|-----------------|
| **[User Documentation](../user/)** | Installation, usage, enterprise features | End Users, Admins |
| **[Operations Documentation](../operations/)** | Production deployment, monitoring | DevOps, SysAdmins |
| **[Advanced Implementation](../../src/finos_mcp/internal/)** | Multi-tenant, plugins, performance | Advanced Developers |
| **[Integration Guide](../integration-guide.md)** | Client setup and configuration | Integration Teams |
| **[Governance Documentation](../governance/)** | Project governance and standards | All Contributors |

</div>

## 📊 Development Statistics

<div align="center">

| Metric | Value | Description |
|--------|-------|-------------|
| **Total Tests** | 350+ | Comprehensive test coverage across all features |
| **Test Coverage** | 85%+ | Code coverage with quality gates |
| **Performance Improvement** | 70% | Faster development with optimizations |
| **Supported Enterprise Features** | 12+ | Multi-tenant, plugins, performance, developer tools |
| **Development Scripts** | 15+ | Automated development workflow tools |

</div>

## 📞 Developer Support

Need development assistance with this independent project?

<table>
<tr>
<td width="50%">

### Community Support
- 💬 **Technical Questions**: [GitHub Discussions](https://github.com/<OWNER>/<REPO>/discussions)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/<OWNER>/<REPO>/issues)
- 🔒 **Security Issues**: [Security Advisory](https://github.com/<OWNER>/<REPO>/security/advisories)
- 📚 **Documentation Issues**: [Documentation Feedback](https://github.com/<OWNER>/<REPO>/issues)

</td>
<td width="50%">

### Development Support
- 🏢 **Advanced Development**: [Advanced Implementation](../../src/finos_mcp/internal/)
- 🔌 **Plugin Development**: [Plugin Source](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)
- 📊 **Performance Issues**: [Performance Source](../../src/finos_mcp/internal/performance_optimizations.py)
- 📧 **Direct Support**: [calderon.hugo@gmail.com](mailto:calderon.hugo@gmail.com)

</td>
</tr>
</table>

### Self-Service Development Resources
- 🚀 **Quick Setup**: Use `./scripts/dev-quick-setup.sh` for instant environment
- ⚡ **Fast Testing**: Use `./scripts/dev-test-focused.sh` for rapid feedback
- 🔄 **Live Development**: Use live reload server for real-time updates
- 📖 **Code Examples**: Browse plugin development examples and templates

---

## 🎯 Next Steps

<div align="center">

**New to the project?** → Start with [Contributing Guidelines](CONTRIBUTING.md)

**Ready to code?** → Follow [Development Guide](development-guide.md)

**Building plugins?** → Check [Plugin Implementation](../../src/finos_mcp/internal/advanced_mcp_capabilities.py)

**Need API docs?** → Review [API Reference](api-reference.md)

</div>

---

> **This is an independent community project** providing advanced MCP server capabilities with multi-tenant architecture and plugin system. All development tools and features are independently created and maintained.

**Independent Project** | **Advanced Development** | **350+ Tests** | **85%+ Coverage** | **Fast Development Mode**
