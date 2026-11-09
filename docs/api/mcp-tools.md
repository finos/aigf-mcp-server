# MCP Tools Reference

The reference for all 9 MCP tools the FINOS AI Governance MCP Server
publishes: what each one takes, what it returns, and how it fails. This is the
only page that documents the tools one by one; the others link here.

## Overview

The server provides 9 tools organized in 3 categories:
- **Framework Access Tools** (3 tools): List, retrieve, and search governance frameworks
- **Risk & Mitigation Tools** (4 tools): List and retrieve AI governance risks and mitigations
- **System Monitoring Tools** (2 tools): Service health and cache performance monitoring

Every tool returns structured content, and each **Input Schema** below is the
schema the server publishes for that tool. A tool that takes no arguments
refuses any it is given. Prompts and resources are documented in the
[Prompts and Resources Reference](../tools-reference.md).

---

## Workflow: list, choose, get

The server does not rank or interpret documents; the client's model does.

1. **List.** `list_frameworks`, `list_risks` or `list_mitigations` gives every
   document of that kind, each with its id, its own name and its own
   description.
2. **Choose.** The model picks the documents that answer the question from
   those names and descriptions. Each catalog is small enough to read whole.
   For frameworks, `search_frameworks` also finds an exact phrase in the text.
3. **Get.** `get_framework`, `get_risk` or `get_mitigation` returns the whole
   document, by the id the list gave.

## Document ids

One document has one id, which every tool and resource takes:

| Kind | Id, as the list tool gives it | Also accepted by the get tool | Resource URI |
|---|---|---|---|
| Framework | `eu-ai-act` | (none) | `finos://frameworks/eu-ai-act` |
| Risk | `10_prompt-injection` | `ri-10`, `10` | `finos://risks/10_prompt-injection` |
| Mitigation | `13_providing-citations-and-source-traceability-for-ai-generated-information` | `mi-13`, `ct-13`, `13` | `finos://mitigations/13_providing-citations-and-source-traceability-for-ai-generated-information` |

The id is the document's filename without its extension and, for a risk or
a mitigation, without the `ri-` or `mi-` prefix. The short forms are the ones
the documents use to refer to each other; they are not case-sensitive, and a
number matches whole, so `1` is not `10`. A resource URI takes the same ids
as the get tool. The resources are documented in the
[Prompts and Resources Reference](../tools-reference.md).

---

## Framework Access Tools

### list_frameworks

List every AI governance framework in the catalog.

**Name**: `list_frameworks`

**Description**: Returns every framework the server can serve, each named and described by its own file. The frameworks are listed in the [project README](../../README.md#supported-content).

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Response Fields**:
- `frameworks` (array): One object per framework
  - `id` (string): Framework identifier; pass it to `get_framework`
  - `name` (string): The name the framework declares for itself
  - `description` (string or null): The framework file's own `description`.
    Null when the file could not be read or declares none; never generated
    from the name
- `total_count` (integer): Number of frameworks listed
- `source` (string): Where the listing came from: `"github_api"`, `"cache"`,
  `"expired_cache"` when GitHub could not be reached and a list file past its
  time was used, or `"static_fallback"` when the built-in catalog was used:
  GitHub could not be reached and no list file exists for this base URL, or
  the base URL names a host the GitHub API cannot address (a mirror), which
  is always listed from the built-in catalog of upstream `main` and must
  hold the same names

**Example**:
```
list_frameworks()
→ Returns the currently available framework catalog from FINOS
```

---

### get_framework

Get the complete content of one framework.

**Name**: `get_framework`

**Description**: Returns one framework as a Markdown document, with the number of entries it lists.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "framework_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "description": "Framework identifier from list_frameworks() (e.g. nist-ai-600-1)."
    }
  },
  "required": ["framework_id"],
  "additionalProperties": false
}
```

**Response Fields**:
- `framework_id` (string): The framework identifier
- `title` (string): The name the framework document declares for itself. Falls
  back to a built-in name when the document declares none. A framework that
  could not be served is an error, not a record with a title that says so.
- `content` (string): The framework as a Markdown document: its title, its
  description and source, then each entry as a list item under its id, with
  its name, link and any other field the file gives it, each value as the
  file wrote it. A comment above a group of entries in the file is a `##`
  heading, and a comment after the last entry closes the document, unless
  it is an entry commented out with its `title` and `url`. A comment anywhere
  else in the file is not written out. A file
  that cannot be read as a framework, or that would be longer written out
  than the server will send, is served as written, in a code fence.
- `entry_count` (integer): Number of entries the framework lists. Zero when
  the file is not shaped like a framework. (`sections` is the risk and
  mitigation documents' list of section titles.)

**Example**:
```
get_framework("eu-ai-act")
→ Returns the EU AI Act as a Markdown document
```

---

### search_frameworks

Find an exact phrase in the framework documents.

**Name**: `search_frameworks`

**Description**: Finds the query as one phrase of whole words in every framework document and returns one result per framework that says it, in the order `list_frameworks` gives them. Case is ignored, and hyphens and underscores count as spaces, so "third party" finds "third-party".

This is a literal find, not a ranked search:

- The query is one phrase of whole words. Words of the query that appear apart
  are not a match, and neither is a word inside a longer one ("act" is not
  found in "practice").
- What is searched is the document `get_framework` returns for a framework. Link
  addresses in it are not searched.
- Results are not ordered by quality. Use `occurrences` and the passages to
  choose which framework to read with `get_framework`.
- An empty result means no framework says that phrase. Try a shorter phrase or
  a single word.
- It covers frameworks only. Risks and mitigations are listed and read with the
  Risk & Mitigation Tools below.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512,
      "description": "The exact phrase to find in the framework documents. Case is ignored; hyphens and underscores count as spaces."
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 5,
      "description": "Maximum number of frameworks to return (1-20), taken in catalog order. At most one passage per framework. total_found counts every framework that says the phrase, including those this limit left out."
    }
  },
  "required": ["query"],
  "additionalProperties": false
}
```

**Response Fields**:
- `query` (string): The phrase that was looked for
- `results` (array): One object per framework, in the order `list_frameworks`
  gives them. Not ranked.
  - `document_id` (string): Framework that says the phrase; pass it to `get_framework`
  - `section` (string): The `##` heading the entry holding the first occurrence
    is under in the document `get_framework` serves, or the framework's name
    when it is under none: an entry above the first heading, the description,
    the note a file closes with, or a file served as written
  - `content` (string): The passage around the first occurrence, cut between words
  - `occurrences` (integer): Times the framework document says the phrase, as
    whole words and outside link addresses.
- `total_found` (integer): Number of frameworks that say the phrase, including
  those `limit` left out

**Example**:
```
search_frameworks("risk management", 5)
→ Returns the first 5 frameworks, in catalog order, that say "risk management"
```

---

## Risk & Mitigation Tools

There is no search tool for risks or mitigations. Each catalog is small enough
to read whole, and an entry carries a description taken from its document
whenever that document could be read: list, choose, then get.

### list_risks

List every risk document.

**Name**: `list_risks`

**Description**: Returns every AI governance risk document, each with the opening of its own summary as its description.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Response Fields**:
- `documents` (array): One object per risk document
  - `id` (string): Risk identifier; pass it to `get_risk`
  - `name` (string): Human-readable risk name
  - `filename` (string): The document's filename in the repository
  - `description` (string or null): The first paragraph of the document's
    opening `## Summary` section, on one line and at most 500 characters; a
    longer paragraph is cut at a word and ends in `...`. Null when the document
    could not be read or does not open with a summary; never generated from the
    name
- `total_count` (integer): Number of risk documents listed
- `document_type` (string): Always `"risk"`
- `source` (string): Where the listing came from: `"github_api"`, `"cache"`,
  `"expired_cache"` when GitHub could not be reached and a list file past its
  time was used, or `"static_fallback"` when the built-in catalog was used:
  GitHub could not be reached and no list file exists for this base URL, or
  the base URL names a host the GitHub API cannot address (a mirror), which
  is always listed from the built-in catalog of upstream `main` and must
  hold the same names

**Example**:
```
list_risks()
→ Returns risk documents from FINOS AI Governance Framework
```

---

### get_risk

Get the complete content of one risk document.

**Name**: `get_risk`

**Description**: Returns one risk document in Markdown, with the titles of its sections.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "risk_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256,
      "description": "Risk document identifier from list_risks(), e.g. 10_prompt-injection; the short form the documents use, ri-10 or 10, is accepted too."
    }
  },
  "required": ["risk_id"],
  "additionalProperties": false
}
```

**Response Fields**:
- `document_id` (string): The risk document identifier as `list_risks` publishes
  it, whichever accepted form the request used
- `title` (string): The title the document declares in its frontmatter. Falls
  back to the filename stem when the document declares none. A document that
  could not be served is an error, not a record with a title that says so.
- `content` (string): The complete risk document, in Markdown
- `sections` (array of strings): The document's section titles

**Example**:
```
get_risk("10_prompt-injection")
→ Returns complete prompt injection risk documentation
```

---

### list_mitigations

List every mitigation document.

**Name**: `list_mitigations`

**Description**: Returns every AI governance mitigation document, each with the opening of its own purpose section as its description.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Response Fields**:
- `documents` (array): One object per mitigation document
  - `id` (string): Mitigation identifier; pass it to `get_mitigation`
  - `name` (string): Human-readable mitigation name
  - `filename` (string): The document's filename in the repository
  - `description` (string or null): The first paragraph of the document's
    opening `## Purpose` section, bounded as for `list_risks`. Null when the
    document could not be read or does not open with one
- `total_count` (integer): Number of mitigation documents listed
- `document_type` (string): Always `"mitigation"`
- `source` (string): Where the listing came from, as for `list_risks`

**Example**:
```
list_mitigations()
→ Returns mitigation documents from FINOS AI Governance Framework
```

---

### get_mitigation

Get the complete content of one mitigation document.

**Name**: `get_mitigation`

**Description**: Returns one mitigation document in Markdown, with the titles of its sections.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "mitigation_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256,
      "description": "Mitigation document identifier from list_mitigations(), e.g. 13_providing-citations-and-source-traceability-for-ai-generated-information; the short form the documents use, mi-13, ct-13 or 13, is accepted too."
    }
  },
  "required": ["mitigation_id"],
  "additionalProperties": false
}
```

**Response Fields**:
- `document_id` (string): The mitigation document identifier as
  `list_mitigations` publishes it, whichever accepted form the request used
- `title` (string): The title the document declares, as for `get_risk`
- `content` (string): The complete mitigation document, in Markdown
- `sections` (array of strings): The document's section titles

**Example**:
```
get_mitigation("1_ai-data-leakage-prevention-and-detection")
→ Returns complete mitigation documentation
```

---

## System Monitoring Tools

### get_service_health

Get the service's health status.

**Name**: `get_service_health`

**Description**: Reports whether the server's subsystems are working, how long it has been up, and its version.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Response Fields**:
- `status` (string): `"healthy"` when every subsystem is working, `"degraded"`
  when at least one is not or the status could not be determined
- `uptime_seconds` (number): Server uptime in seconds
- `version` (string): MCP server version
- `healthy_services` (integer): Number of subsystems that are working
- `total_services` (integer): Number of subsystems checked

**Example**:
```
get_service_health()
→ Returns: status=healthy, uptime=3600s, services=4/4
```

---

### get_cache_stats

Get cache statistics.

**Name**: `get_cache_stats`

**Description**: Returns how many cache requests the server has handled and how many were answered from the cache.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

**Response Fields**:
- `total_requests` (integer): Total number of cache requests processed
- `cache_hits` (integer): Number of requests answered from the cache
- `cache_misses` (integer): Number of requests the cache could not answer
- `hit_rate` (number): Cache hit rate as a decimal (0.0 to 1.0)

**Example**:
```
get_cache_stats()
→ Returns the request, hit and miss counts and the hit rate
```

---

## Error Handling

A tool that fails returns a result with `isError: true`, no structured content,
and one text block that says what happened. It does not return an error object.

| What happened | What the client receives |
|---|---|
| An argument is missing, unknown or out of range | `isError: true`; the text names the argument and the bound |
| No document has the id | `isError: true`; the text names the listing tool that holds the valid ids |
| The document exists and cannot be served | `isError: true`; the text says whether it could not be loaded, is too large, or is empty |
| GitHub is rate limiting the server | `isError: true`; the text says the throttle is temporary |
| The client is over this server's rate or concurrency limit | JSON-RPC error `-32000`, before the tool runs |

Resources and prompts fail with a JSON-RPC error instead: `-32602` for an id no
document has, `-32603` for a document that could not be served.
[Response Schemas](response-schemas.md#error-response-examples) shows each
result as a client receives it.

## Rate Limiting

One budget per caller, drawn on by every MCP request the server receives:
tool calls, resource reads, prompt requests, listings and the handshake alike.
There is no separate allowance for any kind of request.

- **Requests**: 600 a minute per caller (`FINOS_MCP_DOS_MAX_REQUESTS_PER_MINUTE`)
- **Concurrent requests**: 10 per caller (`FINOS_MCP_DOS_MAX_CONCURRENT_REQUESTS`)
- **Content retrieval**: a document fetched for a call draws on no budget of
  its own; the cache reduces upstream fetches but does not bypass the boundary
- **Sizes**: a document over 1 MB is not served, and a tool response over
  5 MB, counting both its content blocks and its structured content, is
  refused. No setting changes either limit

The caller is the token's subject when auth is on, otherwise the client's
address; [deployment.md](../deployment.md) says how the address is resolved
behind a proxy.

## Caching

A fetched document is kept in memory for an hour by default, and the list of
documents is kept in a file for an hour. Search results are not kept.
[Response Schemas](response-schemas.md#caching-behavior) has the settings and
what a restart does. No response times are stated here, because nothing in the
repository measures them.
