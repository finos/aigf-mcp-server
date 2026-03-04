# ADR-0001: Layered Runtime Architecture

- Status: Accepted
- Date: 2026-03-04

## Context

`fastmcp_server.py` originally concentrated MCP registration, orchestration, and
operational logic in a single module. This increased coupling and made targeted
changes riskier.

## Decision

Adopt and maintain a layered runtime structure:

1. `api`: MCP-facing registration/handlers.
2. `application`: use-cases and orchestration services.
3. `domain`: contracts and stable core abstractions.
4. `infrastructure`: repository adapters and external service wiring.
5. `compat`: internal compatibility layer concerns.
6. `bootstrap`: composition root and dependency assembly.

Dependency rule:
- `api` must not directly depend on `infrastructure` or `content` modules.

## Consequences

- Improved modularity and testability.
- Safer localized refactors.
- Added architecture guard tests to prevent direct API-to-infrastructure coupling regressions.
