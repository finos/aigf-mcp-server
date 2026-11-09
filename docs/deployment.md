# Deployment Guide

How to install, configure, start, check, stop and upgrade this server.

The commands on this page were run, and the behaviour it describes was
measured, on 2026-10-11 against an install made from a fresh clone (Python
3.12, macOS). A statement that comes from reading the code or from the test
suite says so. What was not tested is listed under [Not tested](#not-tested).

Every setting is in [Settings](#settings), and the token rules are in
[Authentication](#authentication).

## Choose a transport

| | `stdio` (default) | `http` |
|---|---|---|
| Who starts the process | The MCP client, one process per client | You, one process for many clients |
| Network port | None | `FINOS_MCP_MCP_HOST`:`FINOS_MCP_MCP_PORT`, `127.0.0.1:8000` by default |
| Authentication | None; there is no network boundary | Required, or the server does not start (`FINOS_MCP_ALLOW_INSECURE_HTTP=true` overrides this for local development) |

`FINOS_MCP_MCP_TRANSPORT` also accepts `streamable-http`, which serves the same
`/mcp` endpoint as `http`, and `sse`, which serves `/sse` and `/messages/` and
no `/mcp`.

## Install

There is no PyPI package and no container image. Install from a clone as the
[Quick Start](../README.md#quick-start) in the project README says, in the
directory the server will run from, for example `/opt/aigf-mcp-server`.

The version comes from git, so install from a clone. From a copy of the files without the `.git` directory,
a downloaded archive for example, the install fails with `setuptools-scm was
unable to detect version`. An install from a
commit that carries no release tag reports a development version such as
`0.1.dev312`; see the [release process](release-process.md#version-scheme).

The server is started by `venv/bin/finos-mcp`. It takes no arguments; all
configuration comes from the environment and, when `FINOS_MCP_ENV_FILE` names
one, a dotenv file.

## Run on stdio

The client starts the server; the configuration for each client is in the
[Setup Guide](README.md). Nothing else is needed. The client stops the process
by closing its input, and the process then exits with code 0.

## Run on HTTP

### Minimum configuration

```bash
export FINOS_MCP_MCP_TRANSPORT=http
export FINOS_MCP_MCP_AUTH_ENABLED=true
export FINOS_MCP_MCP_AUTH_ISSUER=https://auth.example.com
export FINOS_MCP_MCP_AUTH_AUDIENCE=finos-mcp-server
export FINOS_MCP_MCP_AUTH_JWKS_URI=https://auth.example.com/.well-known/jwks.json
```

Recommended in addition:

```bash
# The public URL clients use; lets them discover where to sign in.
export FINOS_MCP_MCP_AUTH_BASE_URL=https://mcp.example.com
# Scopes every token must carry, comma-separated.
export FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES=governance:read
# An absolute path, so the location does not depend on the working directory.
export FINOS_MCP_DISCOVERY_CACHE_DIR=/var/cache/finos-mcp/discovery
# A GitHub token with read access to public repositories, here taken from
# GITHUB_TOKEN. Raises the GitHub API limit from 60 requests an hour to 5000.
export FINOS_MCP_GITHUB_TOKEN="$GITHUB_TOKEN"
```

Tokens must be signed with RS256 and carry `exp` and `sub`; the full rules,
and the static-key alternative to a JWKS URI, are in
[Authentication](#authentication).

The server reads a dotenv file only when `FINOS_MCP_ENV_FILE` names it, by
absolute path; a `.env` in the working directory is not read, because on
`stdio` that directory is the client's. A named file that does not exist
stops startup. A variable set in the environment wins over the same variable
in the file. A name without the `FINOS_MCP_` prefix is skipped, so the file
can be shared with other programs; a `FINOS_MCP_` name that is not a setting
stops startup. When a
`.env` is in the working directory and the variable is unset, startup logs one
warning saying the file is not read.

### Start

```bash
venv/bin/finos-mcp
```

A configuration the server cannot use ends the process with exit code 1 before
it listens. The output names each problem, with no traceback; measured with
`FINOS_MCP_MCP_TRANSPORT=http` and nothing else set:

```text
❌ Configuration Error: Failed to load configuration: Configuration validation failed:
  - mcp_transport=http exposes a network endpoint, so FINOS_MCP_MCP_AUTH_ENABLED=true is required. For local development only, set FINOS_MCP_ALLOW_INSECURE_HTTP=true to override.

💡 Check your environment variables, or the file FINOS_MCP_ENV_FILE names.
```

### Check that it started

A request without a token is refused, and the refusal says where to sign in:

```bash
curl -s -i http://127.0.0.1:8000/mcp
```

```text
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer scope="governance:read", resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"
```

The `resource_metadata` part appears only when `FINOS_MCP_MCP_AUTH_BASE_URL`
is set. That URL must be `https`: an `http` one stops startup, since the
document would send clients' tokens to an unencrypted address, unless
`FINOS_MCP_ALLOW_INSECURE_HTTP=true`. The document it points to is served
without a token:

```bash
curl -s http://127.0.0.1:8000/.well-known/oauth-protected-resource/mcp
```

```json
{"resource":"https://mcp.example.com/mcp","authorization_servers":["https://auth.example.com"],"scopes_supported":["governance:read"],"bearer_methods_supported":["header"],"resource_name":"finos-ai-governance"}
```

With a token from your identity provider in `TOKEN`, the server answers an MCP
`initialize` request with its name and version:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

A token the server does not accept, for example one without a required scope,
gets `401` with `error="invalid_token"`.

### Connect a client

A client needs the URL and a token. For a client that reads the `mcpServers`
format, with the token sent as a header:

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

This form was checked with Claude Code against a local server: it connected,
listed the 9 tools and made seven tool calls without an error.

## What the process does

- **Listens** on one port, in plain HTTP. It has no TLS setting; terminate TLS
  in front of it.
- **Serves** `/mcp`, the two health URLs `/healthz` and `/readyz` (see
  [Health checking](#health-checking)), and the sign-in document when a base
  URL is set. Every other path, including `/` and `/health`, answers `404`.
- **Connects out** over HTTPS to `raw.githubusercontent.com` for documents and
  `api.github.com` for the list of documents, and, according to the code, to the JWKS
  URI when one is set. It honours the standard proxy variables (`HTTPS_PROXY`, `ALL_PROXY`); a
  proxy setting it cannot use ends startup with exit code 1.
- **Refuses at startup a `FINOS_MCP_BASE_URL` it would never fetch from**: one
  that is not `https`, names `localhost` or a private, loopback or link-local
  address written as a number, or carries a query or fragment. The refusal
  gives the reason. A mirror must be reachable as `https` on a public address.
- **Lists the documents through the GitHub API only when `FINOS_MCP_BASE_URL`
  names GitHub.** A base URL on a host the GitHub API cannot address, a
  mirror, is always listed from the built-in catalog: the names upstream
  `main` held on the date `src/finos_mcp/content/static_catalog.py` records,
  reported as `"source": "static_fallback"` on every call. A mirror must hold
  the same names; a document it adds is not listed, and one it lacks is
  listed but fails on get. A pinned ref of the upstream repository is listed
  live, but is served from the same catalog while GitHub is throttling the
  address and no list file exists yet.
- **Asks the content host for one file, waits 30 seconds and asks again**, on
  every transport except `stdio`: `index.md` under `FINOS_MCP_BASE_URL`,
  1.3 kB. The answer decides what `/readyz` says.
  `FINOS_MCP_READINESS_PROBE_INTERVAL_SECONDS` changes the wait (5 to 3600).
- **Writes one file of its own**, `github_discovery.json`, the list of
  documents, in `FINOS_MCP_DISCOVERY_CACHE_DIR`. When that is unset the file
  goes to `finos-mcp/discovery` under `XDG_CACHE_HOME`, or under `~/.cache`.
  The directory is created for the server's user only, and one owned by
  another user or writable by others is not used: the server then keeps the
  list in memory and says so once. Fetched documents are held in memory only.
- **Logs** to standard error, and writes one access line per request to
  standard output (client address, method, path, status). At the default level
  the token sent by the client appeared in neither stream. The server's own lines are JSON, one object per line; the
  lines from the HTTP layer underneath it are plain text. At the default `INFO`
  level each document fetched from GitHub is logged with its URL, and so is
  each request for `index.md` described above, as one plain-text line.
  `FINOS_MCP_LOG_LEVEL=WARNING` removes the `INFO` lines except one start line
  from the FastMCP library and the HTTP layer's own start, stop and access lines.
- **Logs one line for every tool call, resource read and prompt request**, at
  `INFO`, as the `message` of a JSON line whose `logger` ends in
  `tool_call_log`:
  `Tool call tool='get_risk' caller=jwt:alice outcome=ok request_id=4`,
  `Resource read uri='finos://risks/10_prompt-injection' caller=jwt:alice outcome=ok request_id=5`,
  `Prompt request prompt='analyze_framework_compliance' caller=jwt:alice outcome=ok request_id=6`.
  - `tool`, `uri` or `prompt` is the name the client sent, in quotes. A name
    the server does not have is logged too.
  - `caller` is the identity the rate limit is counted under: `jwt:` and the
    token's `sub` claim when auth is on, `ip:` and the client address on a
    networked transport without a token, `mcp_client` on `stdio`.
  - `outcome` is `ok` when the tool returned a result, `refused` when the rate
    or concurrency limit refused the call, `cancelled` when the call was
    cancelled and `error` for every other failure, such as an unknown tool, an
    argument the tool does not accept or a response over the size limit. A
    tool that could not reach GitHub and answered from its catalog returned a
    result, so its line says `ok`.
  - `request_id` is the JSON-RPC id the client chose for the call. Two
    clients can use the same id.

  Argument values are not on the line. `FINOS_MCP_LOG_LEVEL=WARNING` removes
  it.

## Health checking

On every transport except `stdio` the server answers two URLs without a
token. Both answer `GET` and `HEAD` with an empty body and
`Cache-Control: no-store`. Measured on `http` and `sse` with auth on, next to
`401` from `/mcp` (`/sse` on `sse`):

| URL | Answer |
|---|---|
| `GET /healthz` | `200` while the process is serving |
| `GET /readyz` | `200` when the server can fetch documents as far as it knows, `503` otherwise |

`/healthz` is for a process supervisor or a liveness check: restart the
process when it stops answering. It answered `200` in every situation below.

`/readyz` is for a load balancer: stop sending calls to an instance that
answers `503`. It answers `503` in three situations:

- **The server has just started.** The first request to the content host has
  not finished. With GitHub reachable, `/readyz` answered `200` 0.1 to 0.3
  seconds after the port opened.
- **The content host did not answer the last request.** The server asks the
  host of `FINOS_MCP_BASE_URL`, `raw.githubusercontent.com` unless that
  setting was changed, for one small file, and asks again 30 seconds after
  each request has finished. No answer within 5 seconds, a `429` or a `5xx`
  counts as not answering; any other status, `404` included, counts as
  answering. `FINOS_MCP_HTTP_TIMEOUT` does not change the 5 seconds. A request
  that gets no answer after one that did is repeated once, 2 seconds later,
  and `/readyz` changes only if that one gets no answer either. With the
  interval set to 5 seconds, `/readyz` changed to `503` about 7 seconds after
  the host became unreachable and back to `200` within 5 seconds of its
  return, three times out of three. According to the code, a host that
  accepts a request and sends nothing is noticed after two waits of 5 seconds
  and the 2 seconds between them.
- **Document fetches from the content host keep failing.** `/readyz` answered
  `503` from the fifth failed `get_risk` call in a row, and `200` again 60
  seconds after the last failed call, with no call in between. According to
  the code, from then on each further failed fetch brings `503` back for 60
  seconds, until one fetch succeeds. A fetch counts as failed here when the
  host gives no answer, a `429` or a `5xx`; an answer such as `404` or an
  empty document is the host serving, and resets the count, so a caller
  asking for a document the host does not have cannot bring an instance to
  `503`.

Each change of the second kind is logged once, as a `WARNING` when the host
stops answering and as an `INFO` line when it answers again.

What `/readyz` does not tell:

- **It reports `503` on an instance that can still answer some calls.**
  Documents already in memory are served without GitHub: with the host
  unreachable, a `get_risk` call for a document fetched earlier was answered.
  Every instance depends on the same GitHub, so an outage there makes all
  instances answer `503` at once. Check what the load balancer does when no
  instance is ready.
- **It says nothing about `api.github.com`**, which supplies the list of
  documents and nothing else: a document body comes from the content host
  only. When `api.github.com` cannot be reached the server lists documents
  from its list file or from its built-in catalog, and according to the
  code `/readyz` stays `200`.
- **It changes at the pace of the server's own requests, not of the
  checker's.** Once two requests in a row have gone unanswered, `/readyz`
  answers `503` until the next request, 30 seconds later by default, however
  often it is asked.

Neither URL is rate limited: 1,400 requests in under a second were all
answered, where MCP requests are limited to 600 a minute for each client. Each
request to them writes an access line to standard output like any other. A
bearer header sent to them is still verified, although they do not need one:
with a JWKS URI, a token naming a key the server does not hold makes it fetch
the key set, at most once a minute. Rate limit unauthenticated
requests at the proxy.

The MCP tool `get_service_health` is separate from both URLs. It needs a token
like every other tool. It reports `status`, `uptime_seconds`, `version` and
how many of its internal services are healthy, and according to the code it
makes no request of its own and does not read the result of the request to
the content host. Its status becomes `degraded` after five document fetches in
a row have failed, and stays so until a later fetch is attempted, so it can
say `degraded` while `/readyz` answers `200`.

On `stdio` there are no URLs and the server sends no such request.

## Stopping and restarting

`SIGTERM` and `SIGINT` both stop the server. Measured on HTTP:

| Situation | Result |
|---|---|
| Idle, or with client sessions open | The process ends at once, exit code 0 |
| A tool call is running | The call is cut off. The client gets an error (`SSE stream ended without a response`), not an answer. The process ends at once, exit code 0 |

A second stop signal that arrives while the server is closing its resources
ends the process without waiting for them, with exit code 1. That case is
covered by `tests/integration/test_signal_shutdown.py` and was not measured
again for this page.

**Running calls are not waited for.** For a restart that clients do not notice,
take the instance out of the load balancer first, wait for its calls to finish,
then send the signal.

A session lives in the memory of the process that created it. After a restart,
a request that carries the old session id gets `404` with `Session not found`,
and the client has to start a new session. For the same reason, two instances
behind one address need a load balancer that keeps each client on one instance.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Stopped by `SIGTERM`, `SIGINT`, or the stdio client closing its input |
| 1 | Configuration refused at startup; the HTTP client could not be built; a second stop signal during cleanup; or an unexpected server error |
| 3 | The port is already in use |

## Behind a reverse proxy

The server was probed directly with the requests a proxy would send. What the
proxy has to do:

- **Route `/mcp` to the server.** Responses are streamed
  (`text/event-stream`), so turn response buffering off for this path. The
  server sends `X-Accel-Buffering: no` itself.
- **Route `/.well-known/oauth-protected-resource/` to the server**, without a
  token check, when `FINOS_MCP_MCP_AUTH_BASE_URL` is set.
- **Route `/healthz` and `/readyz` only if the health checker reaches the
  server through the proxy.** They need no token and are not rate limited.
- **Keep the server on loopback** (`FINOS_MCP_MCP_HOST=127.0.0.1`, the default)
  when the proxy runs on the same host. With auth on and any other bind host
  the server logs one `WARNING` at startup, since it cannot see whether the
  proxy terminates TLS; a container that must bind `0.0.0.0` still starts.
- **Set `FINOS_MCP_DOS_TRUSTED_PROXIES`** to the proxy's address, for example
  `127.0.0.1/32`, if you want `X-Forwarded-For` to be read. Unset, the header
  is ignored. According to the code this setting has no effect while auth is
  on: requests are counted only after the token check, and then per token
  subject, not per address. It matters for a server run without auth
  (`FINOS_MCP_ALLOW_INSECURE_HTTP=true`). The counting was not measured for
  this page.

The server accepts any Host header and any Origin header. It does not use
either to decide what to serve.

If the public URL has a path, for example
`FINOS_MCP_MCP_AUTH_BASE_URL=https://mcp.example.com/gov`, the server still
serves MCP at `/mcp`, so the proxy has to remove the `/gov` prefix. The sign-in
document is then served at `/.well-known/oauth-protected-resource/gov/mcp`, and
the proxy has to pass that path through unchanged.

## Settings

All configuration comes from environment variables, and from a dotenv file
when `FINOS_MCP_ENV_FILE` names one. `.env.example` has a comment on each
setting.

| Variable | Default | Required | Purpose / Guidance |
|---|---|---|---|
| `FINOS_MCP_ENV_FILE` | unset | No | Absolute path of the dotenv file to read. Unset, no file is read, not even a `.env` in the working directory; a named file that does not exist stops startup. |
| `FINOS_MCP_MCP_TRANSPORT` | `stdio` | No | Runtime transport. Use `stdio` for local clients; use `http` or `streamable-http` for network exposure. |
| `FINOS_MCP_MCP_HOST` | `127.0.0.1` | For non-stdio | Bind host for network transports. Keep loopback unless behind controlled ingress. |
| `FINOS_MCP_MCP_PORT` | `8000` | For non-stdio | Bind port for network transports. |
| `FINOS_MCP_MCP_AUTH_ENABLED` | `false` | **For non-stdio** | Enables JWT boundary authentication. Required for `http`/`streamable-http`/`sse` — startup fails without it. |
| `FINOS_MCP_ALLOW_INSECURE_HTTP` | `false` | No | Development-only override permitting a non-stdio transport with auth disabled. Logs an error each startup. Never set in a reachable deployment. |
| `FINOS_MCP_MCP_AUTH_ISSUER` | _(none)_ | If auth enabled | Expected JWT `iss` claim. |
| `FINOS_MCP_MCP_AUTH_AUDIENCE` | _(none)_ | If auth enabled | Expected JWT `aud` claim. |
| `FINOS_MCP_MCP_AUTH_JWKS_URI` | _(none)_ | One of verifier pair | Recommended verifier source (supports key rotation). Fetched with SSRF protection unless the next row is set. |
| `FINOS_MCP_ALLOW_INSECURE_JWKS_URI` | `false` | No | Removes SSRF protection from the JWKS fetch, permitting plain HTTP and loopback/link-local/private addresses. Only for an internal identity provider. Logs an error each startup. |
| `FINOS_MCP_MCP_AUTH_PUBLIC_KEY` | _(none)_ | One of verifier pair | Static PEM verifier source, an RSA public key. Loaded at startup: a value that does not load, is not an RSA public key or is a private key stops startup with the reason. A literal `\n` in the value is read as a line break. Do not set with `JWKS_URI`. |
| `FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES` | _(none)_ | No | Comma-separated required scopes for all requests. |
| `FINOS_MCP_MCP_AUTH_BASE_URL` | _(none)_ | No | Public URL clients use to reach this server, `https`. When set on a non-stdio transport with auth enabled, the server publishes OAuth protected-resource metadata so clients can discover the authorization server. An `http` URL stops startup unless `FINOS_MCP_ALLOW_INSECURE_HTTP=true`. |
| `FINOS_MCP_HTTP_TIMEOUT` | `30` | No | Seconds one outbound request may take in all, retries and body included. |
| `FINOS_MCP_ENABLE_CACHE` | `true` | No | In-memory content cache toggle. |
| `FINOS_MCP_CACHE_MAX_SIZE` | `1000` | No | Max entries in cache. Increase carefully with memory limits. |
| `FINOS_MCP_CACHE_TTL_SECONDS` | `3600` | No | Cache TTL in seconds. |
| `FINOS_MCP_GITHUB_TOKEN` | _(none)_ | Recommended | Raises GitHub API limits and stability for dynamic content sync. |
| `FINOS_MCP_LOG_LEVEL` | `INFO` | No | Runtime log verbosity. |
| `FINOS_MCP_DEBUG_MODE` | `false` | No | Enables verbose diagnostics; avoid in production unless troubleshooting. |
| `FINOS_MCP_BASE_URL` | `https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs` | No | Where documents are read from; the repository, ref and path are taken from it. See [What the process does](#what-the-process-does) for the hosts it accepts. |
| `FINOS_MCP_DISCOVERY_CACHE_DIR` | unset | No | Absolute path of the directory for the list file. Unset, `finos-mcp/discovery` under `XDG_CACHE_HOME`, or under `~/.cache`. |
| `FINOS_MCP_DOS_MAX_REQUESTS_PER_MINUTE` | `600` | No | Requests each client may make in a minute (10 to 2000). |
| `FINOS_MCP_DOS_MAX_CONCURRENT_REQUESTS` | `10` | No | Requests each client may have running at once (1 to 200). |
| `FINOS_MCP_DOS_TRUSTED_PROXIES` | unset | No | Comma-separated CIDRs of your reverse proxies, whose `X-Forwarded-For` is then read. See [Behind a reverse proxy](#behind-a-reverse-proxy). |
| `FINOS_MCP_READINESS_PROBE_INTERVAL_SECONDS` | `30` | No | Seconds between the requests that decide what `/readyz` answers (5 to 3600). |
| `FINOS_MCP_SERVER_NAME` | `finos-ai-governance` | No | The server name sent to clients in the `initialize` answer. |

Parsed documents are held in process memory, one entry each, for
`FINOS_MCP_CACHE_TTL_SECONDS` (an hour by default) and at most
`FINOS_MCP_CACHE_MAX_SIZE` entries. Nothing persists the cache and no setting
protects it.

## Authentication

Auth is JWT validation at the MCP boundary (FastMCP `JWTVerifier`). The
minimum settings are in [Minimum configuration](#minimum-configuration).

- **Any non-stdio transport requires auth.** Starting with `FINOS_MCP_MCP_TRANSPORT` set to
  `http`, `streamable-http` or `sse` while `FINOS_MCP_MCP_AUTH_ENABLED` is `false` fails startup,
  rather than silently serving every tool and prompt without a token.
- Set exactly one of `FINOS_MCP_MCP_AUTH_JWKS_URI` or `FINOS_MCP_MCP_AUTH_PUBLIC_KEY`.
- When auth is enabled, missing issuer/audience/verifier settings fail startup.
- Clients must send `Authorization: Bearer <JWT>`.
- **Tokens must be signed with RS256.** The verifier is built for that algorithm alone: a token
  with any other `alg`, `none` and HS256 included, gets `401`, and a JWKS key of another type is
  not used. The static key must be an RSA public key.
- **Tokens must carry `exp`.** A token without an expiry gets `401`; expiry is the only revocation
  this server has. `nbf` is honoured when present: a token not yet valid gets `401`.
- **Tokens must carry `sub`.** Rate limits and the per-call log line are keyed on the subject, so a
  token without one gets `401`; `client_id` or `azp` alone is not accepted in its place.
- **Set `FINOS_MCP_MCP_AUTH_BASE_URL` to let clients find where to sign in.** It is the public URL
  clients use to reach this server, for example `https://mcp.example.com`. With it, the `401` sent
  to a request without a valid token gives the address of a metadata document, and the server
  publishes that document under `/.well-known/oauth-protected-resource/` without requiring a token
  (RFC 9728). A reverse proxy in front of the server has to pass that path through. The document
  names `FINOS_MCP_MCP_AUTH_ISSUER` as the authorization server, so the issuer must be an HTTP or
  HTTPS URL or startup fails. Without the setting the server publishes neither, and a client
  has to be given its token by other means; the server does not derive the URL from its bind
  address, which is not the address clients use behind a proxy. Which tokens are accepted is the
  same either way.
- **Tokens must not travel over plain HTTP.** The public URL must be `https`: an `http` one stops
  startup, since the metadata document would send clients' tokens to an unencrypted address. The
  server cannot see whether the platform terminates TLS in front of its port, so when auth is on
  and `FINOS_MCP_MCP_HOST` is not loopback it logs one warning at startup and carries on; a
  container needs that bind.
- `FINOS_MCP_ALLOW_INSECURE_HTTP=true` overrides the first rule, and the `https` rule, for local
  development. It logs an
  error on every startup and must never be set where anything else can reach the port. stdio does
  not need it — it has no network boundary to authenticate.
- **The JWKS URI is fetched with SSRF protection by default.** It is operator-supplied config that
  this process retrieves to verify tokens (FastMCP keeps the key set for up to an hour, and fetches again for a token that names a key it does not hold, at most once a minute: inside that minute an unknown key id is refused from the last set fetched, without a request), and the document it returns decides which
  signatures are trusted, so the fetch is restricted to HTTPS and to public unicast addresses, with
  DNS pinned against rebinding. Loopback, link-local (including cloud metadata endpoints) and
  private ranges are refused.
- `FINOS_MCP_ALLOW_INSECURE_JWKS_URI=true` removes that protection, for deployments whose identity
  provider really is an internal service. It also re-permits plain HTTP, where anyone on the network
  path can substitute the signing keys and mint tokens this server will accept. It logs an error on
  every startup naming the URI.
- If SSRF protection is on and the configured JWKS URI can never satisfy it — not HTTPS, or a
  literal loopback/link-local/private address — **startup fails**. Without that check the
  misconfiguration would surface only as every token being rejected with a bare `401`, since the
  underlying block is logged at `DEBUG`. A hostname that resolves privately cannot be detected
  without a DNS lookup, so it is accepted at startup and refused at fetch time.

## Upgrading

```bash
git fetch origin
git checkout <tag or commit>
venv/bin/pip install .
```

Then restart the process. `pip install .` copies the code into the virtual
environment, so a running server keeps the old code until it is restarted. The
version the running server reports is in the `initialize` answer and in
`get_service_health`.

Read the **Upgrade notes** of the release in `CHANGELOG.md` before upgrading;
removed tools and settings, and changed fields, are listed there.

## Not tested

- **A mirror of the content.** The server was run against
  `raw.githubusercontent.com` only; the catalog limit above is read from the
  code.
- **A container image.** The repository has no Dockerfile and publishes no image.
- **A systemd unit, or any other supervisor.** What a supervisor needs is on
  this page: the command, the environment, the signals and the exit codes.
- **A specific reverse proxy.** The server's side was measured; no nginx,
  Envoy or cloud load balancer configuration was run against it.
- **Windows.**
- **The `sse` transport beyond its endpoints**, and more than one instance
  behind one address.
