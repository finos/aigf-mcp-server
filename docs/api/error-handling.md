# Error Handling

Runtime-accurate guide to error behavior for the FINOS AI Governance MCP Server.

## Error Behavior Model

The server returns errors through two practical paths:

1. MCP/runtime-level call failures
- Invalid inputs can fail schema validation before tool logic runs.
- Transport/auth/rate-limit failures can stop tool execution.

2. Tool-level safe responses
- Tool handlers return sanitized user-facing error text.
- Discovery-dependent tools signal degraded state explicitly using
  `source: "unavailable"` and a `message` field.

## Discovery-Unavailable Semantics

When live repository discovery fails:

- `list_frameworks`, `list_risks`, `list_mitigations`:
  - `source` is `"unavailable"`
  - `message` explains retry guidance
  - `frameworks`/`documents` are empty arrays

- `search_frameworks`, `search_risks`, `search_mitigations`:
  - `total_found` is `0`
  - `results` is an empty array
  - `message` explains discovery is unavailable

- `get_framework`, `get_risk`, `get_mitigation`:
  - Response still returns normal model fields
  - `content` contains a safe user-facing unavailable message

## Validation Behavior

Validation is enforced via Pydantic/FastMCP constraints in tool signatures.
Common constraints include:

- search `limit`: minimum `1`, maximum `20`
- query and identifier string length limits

Use list tools first to retrieve valid IDs and avoid not-found flows.

## Sanitized Errors

Unexpected internal failures are sanitized before returning externally.
The server avoids leaking sensitive internals (paths, tokens, stack details)
and returns safe text that may include a short request ID.

Implementation reference:
- `src/finos_mcp/security/error_handler.py`

## Rate Limiting And Request Guardrails

DoS guardrails are configuration-driven:

- `FINOS_MCP_DOS_MAX_REQUESTS_PER_MINUTE` (default: `600`)
- `FINOS_MCP_DOS_MAX_CONCURRENT_REQUESTS` (default: `10`)
- `FINOS_MCP_DOS_REQUEST_TIMEOUT_SECONDS` (default: `30`)

Payload-size guardrails are also enforced:

- tool result size validation: 5MB default
- resource/document payload validation: 1MB default
- request parameter payload validation: 100KB default

## Client Recommendations

1. Treat `source: "unavailable"` responses as retryable.
2. Back off and retry on rate-limit/time-based failures.
3. Do not parse human-readable `content` for program logic.
4. Prefer structured fields (`source`, `message`, `results`, `total_found`) for control flow.
5. Call `get_service_health` and `get_cache_stats` during incident diagnosis.

## Practical Debug Steps

1. Confirm tool availability in client.
2. Run `get_service_health` to inspect runtime status and observability fields.
3. Run `get_cache_stats` to inspect cache pressure and hit/miss behavior.
4. Retry list/search calls after transient upstream or network failures.
