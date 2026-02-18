---
name: fastmcp-python-server
description: Build, debug, migrate, and deploy FastMCP-based Model Context Protocol servers in Python. Use when requests involve creating or updating FastMCP tools/resources/prompts, choosing v2.14.x vs v3 architecture, fixing FastMCP runtime/transport/schema/auth/lifespan issues, configuring sampling or background tasks, or hardening FastMCP servers for production/cloud deployment.
---

# FastMCP Python Server

Use this skill to implement or maintain FastMCP servers with predictable structure, version-safe decisions, and production-ready defaults.

## Quick Workflow

1. Detect FastMCP version requirements first.
2. Scaffold or update a module-level server export (`mcp = FastMCP("...")`).
3. Implement tools/resources/prompts with strict type hints and docstrings.
4. Add context-driven features only when required: elicitation, progress, sampling, or tasks.
5. Apply production layers in order: lifespan, auth, middleware, storage, observability.
6. Validate transport/client wiring and common failure modes.
7. Run targeted tests and provide runnable commands.

## Version Gate

1. Default to `fastmcp>=2.14.3,<3` unless user explicitly asks for v3 beta features.
2. If server already uses v2 decorators and works, keep v2-compatible patterns.
3. If user needs providers/transforms/versioned components, design for v3 architecture.
4. Call out version-specific breaking changes before editing code.

## Implementation Rules

1. Keep the server object at module level for cloud/runtime discovery.
2. Use `async def` for I/O-bound tools and avoid blocking calls in event loop paths.
3. Add explicit type hints for all tool parameters and return values.
4. Write task-focused docstrings because LLM clients read them.
5. Return JSON-serializable outputs (dict/list/primitive/Pydantic), not custom class instances.
6. For resource templates, match URI variables to function argument names exactly.
7. Use `Context` injection only when advanced runtime behavior is needed.

## FastAPI / ASGI Rules

1. Always pass `lifespan=mcp.lifespan` to FastAPI/Starlette.
2. Mount with path awareness (`/` vs `/mcp`) to avoid doubled endpoint paths.
3. If using background tasks (`task=True`), prefer FastMCP versions with context propagation fixes (`>=2.14.3`).

## Production Defaults

1. Use persistent storage for auth/cache/state (Disk or Redis; encrypt where possible).
2. Keep middleware order deterministic:
   Error handling -> timing -> logging -> rate limiting -> caching.
3. Use retries/backoff and shared HTTP clients for external API calls.
4. Load secrets from environment variables; never hardcode credentials.
5. Add health checks and observable progress/logging for long-running flows.

## Troubleshooting Process

1. Classify the error: import, schema validation, serialization, transport, auth, lifecycle, or mounting.
2. Check version-specific breaking changes first.
3. Verify server export + client transport config + endpoint path.
4. Minimize to a smallest reproducible tool and retest.
5. Apply fix, then document the root cause and prevention note.

## References

1. Read `references/fastmcp-guide.md` for detailed examples, migration notes, v2.14/v3 changes, and the 30-error troubleshooting map.
2. Use only sections relevant to the current task to keep context small.
