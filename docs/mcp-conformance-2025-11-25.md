# MCP Conformance Matrix (2025-11-25 Baseline)

This matrix records conformance of the current runtime against MCP capabilities
used by this project. It is intended as an auditable implementation snapshot.

## Status Legend

- Implemented: supported in runtime and covered by tests/docs.
- Partial: implemented for some flows only.
- Out of Scope: intentionally not part of project scope.

## Core Runtime Capabilities

| Capability | Status | Notes |
|---|---|---|
| MCP tool registration and invocation | Implemented | 11 tools exposed via FastMCP server runtime. |
| MCP resources | Implemented | `finos://frameworks/{id}`, `finos://risks/{id}`, `finos://mitigations/{id}`. |
| MCP prompts | Implemented | 3 prompt templates for compliance/risk/mitigation analysis. |
| Structured tool output models | Implemented | Pydantic models used for tool responses. |
| Tool annotations/hints | Implemented | `title`, read-only/idempotent/destructive/open-world hints are set. |
| Resource metadata annotations | Implemented | audience/priority annotations configured. |
| Prompt metadata | Implemented | titles and descriptions configured. |

## Security and Operational Controls

| Capability | Status | Notes |
|---|---|---|
| Optional JWT boundary authentication | Implemented | Configurable via `FINOS_MCP_MCP_AUTH_*`. |
| DoS/rate limiting guardrails | Implemented | Configurable defaults via `FINOS_MCP_DOS_*`. |
| Request size validation | Implemented | Parameter payload size checks enforced. |
| Response/resource size validation | Implemented | Tool/resource payload size checks enforced. |
| Error sanitization | Implemented | Safe external error messages with redaction strategy. |

## Data Access and Degraded Mode

| Capability | Status | Notes |
|---|---|---|
| Live discovery-based framework/risk/mitigation catalogs | Implemented | Runtime discovery against configured upstream repository paths. |
| Explicit unavailable signaling | Implemented | `source=\"unavailable\"` + `message` for list/search failures. |
| Static filename fallback catalogs | Out of Scope | Removed from runtime behavior intentionally. |

## Internal Compatibility Layer (OpenEMCP-Aligned)

| Capability | Status | Notes |
|---|---|---|
| Canonical status normalization (`approved/rejected/modified`) | Implemented | Internal normalization in compatibility and observability flows. |
| Internal envelope/event buffering | Implemented | Buffered compatibility event service in runtime. |
| Additive observability projection on system tools | Implemented | `get_service_health` and `get_cache_stats` include optional `observability`. |
| Cross-phase compatibility propagation for all tools | Partial | Fully active on health/cache, partial elsewhere. |
| Dedicated external compatibility event API | Out of Scope | Not exposed as dedicated MCP tool/resource currently. |

## Scope Boundaries

The following are explicitly outside current project scope:

1. Full OpenEMCP orchestration runtime behavior across all phases.
2. HITL negotiation workflow enforcement as protocol-level behavior.
3. Agent identity fabric (SPIRE/SVID) and mTLS trust mesh.
4. Blockchain anchoring/audit ledger integrations.

## Change Management

When MCP-facing behavior changes, update this file and the API docs:

1. `docs/api/mcp-tools.md`
2. `docs/api/response-schemas.md`
3. `docs/api/error-handling.md`

