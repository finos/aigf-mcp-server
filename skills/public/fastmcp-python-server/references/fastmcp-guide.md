# FastMCP Guide

Last updated: 2026-01-21

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Version Notes](#2-version-notes)
3. [Core Concepts](#3-core-concepts)
4. [Context Features](#4-context-features)
5. [Background Tasks (v2.14.0+)](#5-background-tasks-v2140)
6. [Sampling with Tools (v2.14.1+)](#6-sampling-with-tools-v2141)
7. [Storage Backends](#7-storage-backends)
8. [Server Lifespan and ASGI Integration](#8-server-lifespan-and-asgi-integration)
9. [Middleware System](#9-middleware-system)
10. [Server Composition](#10-server-composition)
11. [OAuth and Authentication](#11-oauth-and-authentication)
12. [API Integration and Cloud Deployment](#12-api-integration-and-cloud-deployment)
13. [Compatibility and Common Errors](#13-compatibility-and-common-errors)
14. [Production Patterns and Testing](#14-production-patterns-and-testing)
15. [Key Takeaways](#15-key-takeaways)

## 1. Quick Start

Install:

```bash
pip install fastmcp
# or
uv pip install fastmcp
```

Minimal server:

```python
from fastmcp import FastMCP

# Keep this at module level for cloud/runtime discovery
mcp = FastMCP("My Server")

@mcp.tool()
async def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```

Run:

```bash
python server.py
fastmcp dev server.py
python server.py --transport http --port 8000
```

## 2. Version Notes

### v2.14.x

- `v2.14.0`: Background tasks, MCP 2025-11-25 support, SSE/event resumability updates.
- `v2.14.1`: Sampling with tools, `sample_step()`, Python 3.13 support.
- `v2.14.2`: MCP SDK pin `<2.x`, outputSchema `$ref` and OAuth/OpenAPI fixes.
- `v2.14.3+` recommended for known HTTP timeout and ASGI background-task context fixes.

### Breaking changes in v2.14.0

- `BearerAuthProvider` removed; use `JWTVerifier` or `OAuthProxy`.
- `Context.get_http_request()` removed.
- `from fastmcp import Image` removed; use `from fastmcp.utilities import Image`.
- Task toggles (`enable_docket`, `enable_tasks`) and several older run/app helpers removed.

### v3.0.0 beta (major refactor)

- Provider architecture: `FileSystemProvider`, `SkillsProvider`, `OpenAPIProvider`, `ProxyProvider`.
- Transforms: namespace, version filters, resources/prompts-as-tools.
- Component versioning and session-scoped state APIs.

Pin to v2 for stability:

```text
fastmcp<3
```

## 3. Core Concepts

### Tools

- Use precise names, strict type hints, and strong docstrings.
- Prefer `async def` for I/O-bound work.
- Return JSON-serializable output.

### Resources

- Always provide URI schemes (`data://`, `resource://`, `file://`, etc.).
- Match URI template variables to function parameter names exactly.

### Prompts

- Keep templates explicit and parameterized.

## 4. Context Features

Use typed `Context` injection for advanced behavior:

- Elicitation (`request_elicitation`) for user confirmation/input.
- Progress (`report_progress`) for long or batch jobs.
- Sampling (`sample`, `sample_step`) for model-in-the-loop workflows.

## 5. Background Tasks (v2.14.0+)

Enable with `@mcp.tool(task=True)` for long-running operations.

Use when:

- Runtime likely exceeds client timeout windows.
- Work is naturally chunked and benefits from progress updates.
- You need non-blocking server behavior.

Notes:

- Task states: `pending -> running -> completed/failed/cancelled`.
- In v2.14.x, progress status-message forwarding during polling may be limited in some clients.
- Tasks execute via Docket scheduler and are not proxy-executable in the documented behavior.

## 6. Sampling with Tools (v2.14.1+)

Use `ctx.sample(..., tools=[...])` for agentic workflows where model calls tools while reasoning.

- `AnthropicSamplingHandler` and `OpenAISamplingHandler` are available patterns.
- `sample_step()` is useful for single-step inspection and response metadata.
- Known community caveat: multi-server client setups may report sampling unsupported in some configurations.

## 7. Storage Backends

Common options:

- Memory: ephemeral, dev-focused.
- Disk: persistent single-instance.
- Redis: distributed production.
- Encrypted wrapper (`FernetEncryptionWrapper`) for sensitive state/tokens.

Recommendation:

- Use persistent encrypted storage for OAuth tokens, caching, and session state in production.

## 8. Server Lifespan and ASGI Integration

Use server lifespan for once-per-instance setup/teardown (DB pools, API clients).

- v2.13+ behavior is per-server-instance, not per-session.
- In FastAPI/Starlette, always wire `lifespan=mcp.lifespan`.
- Access lifespan context via `context.fastmcp_context.lifespan_context` in tools.

## 9. Middleware System

Recommended execution order:

1. Error handling
2. Timing
3. Logging
4. Rate limiting
5. Response caching

Order affects correctness and observability. Custom middleware should always delegate via `self.next(...)`.

## 10. Server Composition

Two patterns:

- `import_server()`: static copy, no runtime propagation.
- `mount()`: dynamic link with runtime delegation.

Use `import_server()` for frozen bundles and `mount()` for modular live composition.

## 11. OAuth and Authentication

Main patterns:

1. Token validation (`JWTVerifier`)
2. External IdP provider flows
3. OAuth proxy (`OAuthProxy`)
4. Full OAuth provider

Security defaults:

- Enable consent screens for proxy flows.
- Keep signing keys in env vars.
- Use encrypted persistent client/token storage.

## 12. API Integration and Cloud Deployment

API integration patterns:

- Manual `httpx.AsyncClient`
- OpenAPI conversion (`from_openapi`)
- FastAPI conversion (`from_fastapi`)

Cloud deployment requirements:

- Export server at module level (`mcp`, `server`, or `app`).
- Keep dependencies in package metadata (`requirements.txt`/`pyproject.toml`).
- Configure environment via env vars (never hardcode secrets).

## 13. Compatibility and Common Errors

Use this triage map:

1. Module-level server object missing.
2. Async/sync misuse.
3. Missing typed `Context` for expected injection.
4. Invalid resource URI scheme.
5. URI template/function parameter mismatch.
6. Pydantic/type validation mismatch.
7. Transport mismatch (stdio vs HTTP) or endpoint-path mismatch.
8. Import/install path problems.
9. Deprecated/removed API usage after upgrades.
10. Non-serializable return types (`datetime`, bytes, custom classes).
11. Lifespan not wired into ASGI app.
12. Middleware order/delegation errors.
13. `import_server()` vs `mount()` misuse.
14. OAuth proxy security misconfiguration (consent/signing key/storage).
15. FastAPI mount-path doubling (`/mcp/mcp`) from mounting strategy mismatch.
16. Background-task context errors in older versions; upgrade to `>=2.14.3`.

## 14. Production Patterns and Testing

Recommended implementation patterns:

- Centralized config + structured success/error helpers.
- Shared HTTP client/pool lifecycle.
- Retry with exponential backoff.
- Time-based caching.

Testing:

- Unit: local test client + `call_tool()` assertions.
- Integration: run server entrypoint, then validate tool/resource discovery and calls.

Useful CLI:

```bash
fastmcp dev server.py
fastmcp install server.py
FASTMCP_LOG_LEVEL=DEBUG fastmcp dev server.py
```

## 15. Key Takeaways

1. Keep module-level server export for discovery/deployment.
2. Prefer stable v2 (`>=2.14.3,<3`) unless v3 features are explicitly required.
3. Enforce strong typing/docstrings and JSON-serializable returns.
4. Wire lifespan correctly in ASGI integrations.
5. Keep middleware order deterministic.
6. Use persistent encrypted storage in production.
7. Choose composition mode intentionally (`import_server` vs `mount`).
8. Apply OAuth proxy security defaults (consent + signing key + encrypted storage).
9. Use background tasks for long operations and sampling tools for agentic flows.
10. Validate transport/path alignment early to avoid avoidable runtime failures.

## Official References

- https://github.com/jlowin/fastmcp
- https://fastmcp.cloud
- https://modelcontextprotocol.io
