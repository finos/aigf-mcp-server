# Framework System Architecture

How this server is put together: what assembles the published surface, how a
tool call reaches a document, and where each concern lives.

Every symbol named here exists in `src/`, and
`tests/unit/test_docs_truth.py` fails the build if one stops existing.

---

## Assembly

The server is one `FastMCP` instance, built once and decorated from several
modules.

- **`app.py`** constructs it. It builds the authentication provider, applies the
  DoS middleware, and passes `SERVER_TRUST_INSTRUCTIONS` as the server
  instructions, which the client receives in the `initialize` result.
- **`fastmcp_server.py`** assembles it. It imports the modules that register
  tools, resources and prompts, and re-exports the finished `mcp` object.

**Importing a domain module is what registers its surface.** Each one decorates
the single `mcp` object from `app.py`, so those imports are not tidy-up: dropping
one removes its tools from the published server while leaving every name
importable. That failure happened during the decomposition, which is why
`tests/unit/test_published_surface.py` pins every tool by name and
parameter.

Reach the assembled server through `fastmcp_server`, not `app`. Both expose the
same object, but at import time `app.mcp` has not yet had the domain modules
applied to it, so it publishes nothing.

## The published surface

| Module | Registers |
|---|---|
| `documents/tools.py` | the document tools — a list and a get, for each of the three document types |
| `search/tools.py` | `search_frameworks`, the one search tool |
| `health_tools.py` | the service tools — health and cache statistics |
| `resources.py` | the document resources |
| `prompts.py` | the analysis prompts |
| `http_health.py` | the two HTTP routes `/healthz` and `/readyz`, which are not part of the MCP surface and need no token; see the [deployment guide](../deployment.md#health-checking) |

The shape is deliberate: the document types are parallel, so the document tools
are too, and a fourth type would add a list and a get to the first module rather
than a new subsystem. Search exists for frameworks alone: the risk and
mitigation catalogs are small enough for a caller to choose from their listings,
while the framework bodies are too long to be chosen by title.

`docs/api/mcp-tools.md` is the per-tool contract, and this page deliberately does
not repeat the inventory.

## How a tool call reaches a document

Taking `get_framework` as the example — the other document tools follow the same
path:

1. **Middleware.** `DoSProtectionMiddleware` admits or rejects the call, using
   `DoSProtector` for rate and concurrency limits and `RequestSizeValidator` for
   payload size.
2. **Parameter validation.** FastMCP checks the argument against the bound
   the tool's parameter declares (a maximum length for every identifier) and
   refuses it before the tool runs.
3. **Service acquisition.** `get_service()` in `finos_mcp/service.py` returns the shared
   `ContentService`.
4. **Discovery.** `GitHubDiscoveryService` lists the files the upstream
   repository holds, and the tool picks the one whose name gives the
   identifier. An identifier is the filename without its prefix and extension,
   so `nist-ai-600-1` stops working if upstream renames that file.
5. **Retrieval.** `ContentService.get_document()` returns the document, from
   cache when it can and over HTTP when it cannot.

Nothing in that path is a framework-specific code path. Frameworks, risks and
mitigations are three document types over one pipeline.

## Content pipeline

`ContentService` in `content/service.py` is the façade. Its public surface is
exactly:

`get_document`, `get_health_status`, `get_service_diagnostics`,
`content_host_breaker`, `close`.

`get_document` takes `doc_type` and `filename`, with optional `ttl_override` and
`correlation_id`, and returns `None` when a document cannot be produced —
callers must test for it. It raises in three cases: `GitHubRateLimitError`
when the content host throttled the fetch and said when to retry,
`ContentValidationError` when the fetched document cannot be parsed, and
`ValueError` for a `doc_type` it does not know.

Behind the façade:

| Module | Role |
|---|---|
| `content/discovery.py` | `GitHubDiscoveryService` lists the upstream corpus; `DiscoveryServiceManager` owns its lifetime. The tools in `documents/tools.py` map an id to its filename |
| `content/fetch.py` | `HTTPClient` and `HTTPClientManager` — one pooled httpx client, retries and a per-host circuit breaker |
| `content/parse.py` | `FrontmatterParser` splits YAML frontmatter from body text |
| `content/cache.py` | `TTLCache`, an in-process dict with a time to live and an LRU bound, managed by `CacheManager` |

## Search

Search is a separate package because finding text is a separate concern from
retrieval. It is a literal find: nothing is scored or ranked, and results come
back in catalog order.

- **`search/engine.py`** searches one framework document.
- **`search/ranking.py`** finds a phrase as whole words, counts its occurrences
  and cuts the passage that appears in a result. The module keeps the name it
  had when it ranked.

## Data models

`models.py` holds ten Pydantic models. The ones a caller sees most:

```python
class Framework(BaseModel):
    id: str
    name: str
    description: str | None = None
```

`FrameworkList` wraps `Framework` values with a `total_count` and a `source`
field recording where the data came from — `github_api`, `cache`, `expired_cache` or
`static_fallback`. `FrameworkContent`, `SearchResult`, `SearchResults`,
`DocumentInfo`, `DocumentList`, `DocumentContent`, `ServiceHealth` and
`CacheStats` complete the set.

`source` is worth watching in tests: a response that is well-formed but served
from `static_fallback` or `expired_cache` means live retrieval failed.

## Security

| Module | Provides |
|---|---|
| `security/dos_middleware.py` | `DoSProtectionMiddleware` — the only place DoS limits are enforced, because a guard inside a tool body is swallowed by that tool's own error handling |
| `security/request_validator.py` | `DoSProtector`, `RequestSizeValidator` |
| `security/tool_call_log.py` | `ToolCallLogMiddleware` — one log line per tool call, resource read and prompt request, with the caller, the name and the outcome; registered before the DoS middleware so a refused call is logged too |
| `security/content_filter.py` | `ContentSecurityValidator` — the body size limit and the fetch-target allowlist |
| `security/prompt_safety.py` | `SERVER_TRUST_INSTRUCTIONS` — the trust boundary stated to every client at `initialize` |
| `security/repo_target.py` | `RepoTarget` — the upstream repository a request is allowed to read |

- **Input limits.** Every tool, prompt and resource parameter declares a
  maximum length, and fastmcp refuses a longer value before the function runs.
- **Error disclosure.** A client reads only the error sentences this server
  writes for it; an exception's own words stay in the log.

## Resilience

- **`error_boundary.py`** — `CircuitBreaker`, kept per host by the HTTP
  client and read by `/readyz` and `get_service_health`, and
  `error_boundary`, which reports a failure in the structured form before
  re-raising it. Retries live in the HTTP client (tenacity, three attempts
  when a request gets no answer).
- **`loop_binding.py`** — `must_rebind` decides when a cached client belongs to a
  dead event loop and has to be rebuilt.

## The CALM architecture file

`calm/architecture.json` describes the same server in FINOS CALM 1.2: the
client and the deployment platform as actors; the server with its stdio, HTTP
and SSE interfaces, the two health URLs and the sign-in metadata document; the
content host, the GitHub REST API and the authorization server as the systems
it talks to; the list file, the document cache and the built-in catalog as the
data it keeps; one flow for the normal path and one for the path taken when
GitHub cannot be asked; and three controls, each with a requirement schema under
`calm/controls/` written for this repository, because FINOS publishes none for
an MCP server. The file is for tooling that reads CALM; this page is for
people.

`tests/unit/test_calm_architecture.py` compares the file with the code on
every run: the transports the settings accept, the routes the server mounts,
the listen address, the hosts the content client may reach, every setting the
file names and the built-in catalog's lists. A route, host or transport that
changes without the file fails the build. The CALM schema check itself needs
Node and runs by hand; `docs/development.md` has the command.

## Extending it

Adding a document type means adding a type to the content pipeline and a tool
module that registers against `mcp`, not a new subsystem: discovery, fetching,
parsing and caching are already shared across all three existing types.

There is no plugin interface and no export feature. If you need either, they do
not exist yet — this page previously described both, and neither was ever built.
