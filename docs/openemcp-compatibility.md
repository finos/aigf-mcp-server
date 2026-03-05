# OpenEMCP Compatibility Profile (Internal Layer)

This document describes the current internal compatibility subset implemented in this repository.
It is additive and does not redefine this project as a full OpenEMCP orchestrator.

## Scope

- Internal envelope and phase primitives.
- Canonical status normalization for validation outcomes.
- Internal risk context model and signal-based adapter.
- Additive observability fields on `get_service_health` and `get_cache_stats`.

## Compatibility Matrix

### Implemented

1. Canonical phase identifiers (internal use):
   - `contract_management`
   - `planning_negotiation`
   - `validation_compliance`
   - `execution_resilience`
   - `context_state_management`
   - `communication_delivery`
2. Internal envelope fields:
   - `message_id`
   - `phase`
   - `correlation_id`
   - `timestamp`
   - `payload`
   - `metadata`
3. Canonical validation status normalization:
   - `approved`
   - `rejected`
   - `modified`
4. Internal `risk_context` model:
   - `composite_risk_score` and canonical risk tier
   - dimension scores and weights
   - risk flags/events
   - circuit breaker trip count
5. Additive observability output on:
   - `get_service_health`
   - `get_cache_stats`

### Partial

1. Cross-phase risk propagation:
   - implemented for internal health/cache telemetry paths
   - not yet implemented across all tool flows
2. Compatibility event emission:
   - implemented as in-memory buffered envelopes
   - not yet exported via dedicated API/resource

### Not Implemented

1. Full six-phase orchestration runtime.
2. Negotiation/HITL workflow enforcement as OpenEMCP protocol behavior.
3. Agent registry, SPIRE/SVID identity, and mTLS trust fabric.
4. Blockchain audit anchoring.

## Non-Breaking Contract Statement

Existing MCP tool names, inputs, and required response fields remain unchanged.
The compatibility layer adds optional fields and internal telemetry structures only.

