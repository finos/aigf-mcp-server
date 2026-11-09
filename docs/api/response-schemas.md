# Response Schemas

How a result and a failure reach a client, for all 9 MCP tools in the FINOS AI
Governance MCP Server. The fields each tool returns are in the
[MCP Tools Reference](mcp-tools.md).

## Common Response Elements

### Base Response Structure

A tool that succeeds returns its data twice: as `structuredContent`, an object
whose fields are listed per tool in the [MCP Tools Reference](mcp-tools.md),
and as one text block holding the same object as JSON, for a client that does
not read structured content. `get_service_health`, as a client receives it:

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"status\":\"healthy\",\"uptime_seconds\":0.20524620899232104,\"version\":\"0.1.1rc2.dev116\",\"healthy_services\":4,\"total_services\":4}"
    }
  ],
  "structuredContent": {
    "status": "healthy",
    "uptime_seconds": 0.20524620899232104,
    "version": "0.1.1rc2.dev116",
    "healthy_services": 4,
    "total_services": 4
  },
  "isError": false
}
```

The uptime and the version are those of the session this was taken from.

### Error Response Structure

A failure reaches a client in one of two forms. Neither is a JSON object of
this server's own design:

- a **tool result** with `isError: true`, no structured content, and one text
  block that says what happened;
- a **JSON-RPC error** with a `code` and a `message`, for a resource read, a
  prompt, or a request the server refused before running it.

[Error Response Examples](#error-response-examples) shows each as a client
receives it.

## Error Response Examples

Each result below was taken from a client session against the server.

| What happened | Tool call | Resource read | Prompt |
|---|---|---|---|
| An argument is missing, unknown or out of range | `isError: true` | - | `-32603` |
| No document has the id | `isError: true` | `-32602` | `-32603` |
| The document exists and cannot be served | `isError: true` | `-32603` | `-32603` |
| GitHub is rate limiting this server | `isError: true` | `-32603` | `-32603` |
| The client is over this server's own limits | `-32000` | `-32000` | `-32000` |

### Invalid Arguments

An argument that is missing, not one the tool takes, or outside its bounds is
refused before the tool runs. `search_frameworks` with `limit: 99`:

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "1 validation error for call[search_frameworks]\nlimit\n  Input should be less than or equal to 20 [type=less_than_equal, input_value=99, input_type=int]\n    For further information visit https://errors.pydantic.dev/2.13/v/less_than_equal"
    }
  ]
}
```

The text is written by the validation library and names the argument and the
bound. Its wording follows the library's version, so read `isError`, not the
sentence.

---

### Unknown Id

`get_framework`, `get_risk` and `get_mitigation` answer an id that no document
has with a tool error, not with a document. The result carries `isError: true`,
no structured content, and one text block:

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "Error calling tool 'get_risk': No risk has the id 'does-not-exist'. Call list_risks for the valid ids."
    }
  ]
}
```

Reading `finos://risks/{risk_id}`, `finos://mitigations/{mitigation_id}` or
`finos://frameworks/{framework_id}` with such an id fails with JSON-RPC error
`-32602` and the same sentence as its message. `analyze_framework_compliance`
fails the same way for a framework that does not exist, with code `-32603`.

---

### Document Not Served

A document that is listed and cannot be served is a tool error as well. The
text names the document and says which of three things happened:

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "Error calling tool 'get_risk': The risk '10_prompt-injection' could not be loaded. Retry later."
    }
  ]
}
```

- `The risk '<id>' could not be loaded. Retry later.` The fetch failed. The
  same call can succeed later.
- `The risk '<id>' is too large for this server to return.` The document was
  fetched and is over the 1MB limit. Retrying does not help.
- `The risk '<id>' has no content.` The document was fetched and its body is
  empty. Retrying does not help.

A mitigation or a framework is named in place of the risk. Reading the
document's `finos://` resource fails with JSON-RPC error `-32603` and the same
sentence as its message, and so does `analyze_framework_compliance` for a
framework it could not read.

`search_frameworks` leaves out a framework it could not read and answers from
the others.

---

### Search Not Run

`search_frameworks` answers `total_found: 0` only when it read at least one
framework and none says the phrase. A search that did not run is a tool error
with one of two sentences:

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "Error calling tool 'search_frameworks': No framework could be read, so nothing was searched. Retry later."
    }
  ]
}
```

- `No framework could be read, so nothing was searched. Retry later.` Every
  framework was left out for one of the reasons under Document Not Served.
- `The search failed before it finished. Retry later.` The search stopped on
  an error the server did not expect. The detail is in the server log.

---

### GitHub Rate Limit

When GitHub is rate limiting the server, the three get tools and
`search_frameworks` return a tool error whose text says the failure is a
temporary throttle and not a missing document, and that setting
`FINOS_MCP_GITHUB_TOKEN` raises the limit. A resource read fails with JSON-RPC
error `-32603` and the same text.

The three listing tools do not fail when GitHub cannot be reached. They answer
from the list file the server last wrote, when there is one for the configured
repository (`"expired_cache"`), and otherwise from the built-in catalog
(`"static_fallback"`), and say which in `source`.

---

### Server Limits

A request over this server's own limits is refused before any tool, resource
or prompt runs, with JSON-RPC error `-32000`:

```json
{
  "code": -32000,
  "message": "Rate limit exceeded. Please slow down and try again later."
}
```

The rate and concurrency limits are in the
[tools reference](mcp-tools.md#rate-limiting).

---

## Response Patterns

### Pagination

`search_frameworks` takes a `limit` from 1 to 20, 5 by default. There is no
offset: `total_found` says how many frameworks say the phrase, and a larger
`limit` is the way to see more of them.

### Content Format

A result is JSON. The `content` field of `get_risk`, `get_mitigation` and
`get_framework` holds the document as Markdown. The `content` field of a
`search_frameworks` result is a passage cut from that Markdown.

### Caching Behavior

The server keeps two things:

| What is kept | Where | For how long |
|---|---|---|
| Each risk, mitigation and framework it has fetched | Memory | 1 hour by default. `FINOS_MCP_CACHE_TTL_SECONDS` sets it: `3600` by default, at least `60`, at most `86400` |
| The list of documents the repository holds | The file `github_discovery.json` in `FINOS_MCP_DISCOVERY_CACHE_DIR`, or in `finos-mcp/discovery` under `XDG_CACHE_HOME` or `~/.cache` when that is not set; in memory when the directory cannot be used | 1 hour, or 5 minutes when `FINOS_MCP_DEBUG_MODE` is `true` |

- Search results are not kept. `search_frameworks` reads every framework on
  each call, from memory when the framework is held there.
- `get_service_health` and `get_cache_stats` are worked out on each call.
- When the list file's time is up, the server lists the repository again:
  three GitHub API requests, one per directory.
- When the list file's time is up and GitHub cannot be asked, the server
  serves the list file as it is and a listing tool says
  `"source": "expired_cache"`.
  It waits before it asks GitHub again. The built-in catalog is used only when
  there is no list file for the configured repository.
- The list file is read as the server writes it and no further. A file larger
  than 256 KiB is not read. A name that is not a document name (a `ri-` or
  `mi-` prefix and `.md`, or `.yml`, and only letters, digits, `.`, `_` and
  `-` between) makes the file unreadable, and an unreadable file is replaced
  by the next listing. An expiry further away than the hour reads as past.
- `FINOS_MCP_ENABLE_CACHE=false` stops documents being kept in memory. The list
  file is still written.
- A restart empties the memory. It does not remove the list file, so a server
  started within the hour reads the list from it, and a listing tool then
  says `"source": "cache"`.
- A client cannot ask for a fresh copy. `get_cache_stats` counts reads of the
  documents in memory and does not count the list file.

---

## Response Performance

This page states no response times, because nothing in the repository measures
them. What a call has to do is known:

- The first read of a document fetches it from GitHub. Later reads come from
  memory until the document's hour is up.
- A listing tool reads the documents of its kind, because each entry carries
  the document's own description. The first listing after a start fetches
  them, up to 100, and stops at the first one that fails.
- `search_frameworks` reads every framework on each call.

---

## Tool Response Consistency

All 9 tools follow consistent response patterns:

1. **Structured Output**: Pydantic models ensure type safety
2. **Error Handling**: A failed call is a result with `isError: true` and a text block, on every tool
3. **Content Format**: Markdown for all document content
4. **Metadata**: Consistent field naming and types

This consistency makes integration easier and more predictable across all MCP clients.
