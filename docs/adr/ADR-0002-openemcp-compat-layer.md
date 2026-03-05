# ADR-0002: Internal OpenEMCP Compatibility Layer

- Status: Accepted
- Date: 2026-03-04

## Context

The project needs compatibility-oriented observability and canonical internal
status semantics without changing external MCP contracts.

## Decision

Implement an internal OpenEMCP-style compatibility layer with:

1. Canonical status normalization: `approved`, `rejected`, `modified`.
2. Internal envelope/event buffering for compatibility telemetry.
3. Risk-context projection from runtime signals.
4. Additive observability fields on monitoring tools only:
   - `get_service_health`
   - `get_cache_stats`

Non-goal:
- no conversion into a full OpenEMCP orchestration runtime.

## Consequences

- Compatibility semantics are available for internal flows and diagnostics.
- Existing MCP names, arguments, and required response fields remain backward compatible.
- Full cross-phase propagation remains incremental outside health/cache paths.
