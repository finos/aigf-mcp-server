# Architecture Layers

This project uses a layered architecture to improve modularity and long-term maintainability while preserving MCP contracts.

## Layers

1. `api`
- MCP-facing handlers for tools, resources, and prompts.
- Handles request/response mapping and delegation only.

2. `application`
- Use-case orchestration and service-level business flows.
- Depends on `domain` and ports/interfaces.

3. `domain`
- Core entities, enums, and contracts.
- No MCP transport or infrastructure dependencies.

4. `infrastructure`
- Concrete adapters for external services (GitHub, cache, logging, etc).
- Implements interfaces used by `application`.

5. `compat`
- Internal compatibility helpers (OpenEMCP-style envelope/status/risk logic).

6. `bootstrap`
- Wiring and assembly of runtime dependencies.

## Dependency Rules

1. `api` may depend on `application`, `domain`, and `compat`.
2. `application` may depend on `domain` and interface contracts.
3. `domain` must not depend on other project layers.
4. `infrastructure` may depend on all lower-level primitives but should not be imported directly by `api`.
5. `bootstrap` composes dependencies and should be the primary assembly boundary.

## Compatibility Goal

Layering is internal; MCP tool names, arguments, and required response fields remain backward compatible.

## Guard Rails

Automated checks enforce these boundaries:

1. `tests/unit/test_architecture_guards.py` rejects direct `api -> infrastructure/content` imports.
2. `tests/unit/test_architecture_guards.py` ensures prompt/resource registrations are not reintroduced inline in `fastmcp_server.py`.
