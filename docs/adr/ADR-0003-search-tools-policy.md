# ADR-0003: Search Tools Policy

- Status: Accepted
- Date: 2026-03-04

## Context

A simplification option considered removing search tools in favor of list/get
only access. That would reduce feature surface but increase client-side effort
and reduce UX for discovery workflows.

## Decision

Keep search tools enabled and first-class:

1. `search_frameworks`
2. `search_risks`
3. `search_mitigations`

Guardrails:
- bounded `limit` parameter (1..20)
- explicit degraded behavior when discovery is unavailable
- additive-only contract evolution

## Consequences

- Better user productivity and lower agent friction for governance lookups.
- Slightly larger API surface and test matrix.
- Simplicity concerns are addressed with strict parameter bounds and deterministic degraded responses.
