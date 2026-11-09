# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The first release since 0.1.0, and a rewrite of most of the server. The
detail of each change is in the git history and the issue it names.

### Upgrade notes

- **Python 3.11 or newer is required.** 3.10 is no longer accepted.
- **The server publishes 9 tools.** `search_risks` and `search_mitigations`
  are gone: a client lists the risks or mitigations and chooses from them.
- **`search_frameworks` finds an exact phrase.** It no longer ranks, falls
  back to single words or matches inside longer words; results come in
  catalog order, with an `occurrences` count.
- **Changed fields.** `get_framework` reports its count as `entry_count`
  (it was `sections`); `last_modified` on list entries and `last_updated` on
  `get_framework` are gone (they were always `null`).
- **Six settings are gone**: `FINOS_MCP_CACHE_SECRET`,
  `FINOS_MCP_CHECK_STATIC_FALLBACK`, `FINOS_MCP_DOS_REQUEST_TIMEOUT_SECONDS`,
  `FINOS_MCP_ENABLE_SHA_VALIDATION`, `FINOS_MCP_GITHUB_API_TIMEOUT` and
  `FINOS_MCP_SERVER_VERSION`. Set in the environment, they are ignored; in
  the dotenv file, any one of them stops startup, so delete those lines.
- **A dotenv file is read only when `FINOS_MCP_ENV_FILE` names it**, by
  absolute path. A `.env` in the working directory is no longer read.
- **A network transport requires authentication.** `http`,
  `streamable-http` and `sse` do not start without
  `FINOS_MCP_MCP_AUTH_ENABLED=true`, unless `FINOS_MCP_ALLOW_INSECURE_HTTP=true`
  is set for local development. Tokens must be RS256 and carry `exp` and `sub`.
- **The list file moved** to `finos-mcp/discovery` under `XDG_CACHE_HOME`,
  or `~/.cache`, readable by the server's user only.
  `FINOS_MCP_DISCOVERY_CACHE_DIR` still overrides it.

### Added

- **Resources**: every framework, risk and mitigation is listed as a
  `finos://` resource, served as Markdown.
- **The get tools accept the short ids the documents use**: `ri-10` and `10`
  serve `10_prompt-injection`; `mi-13` and `ct-13` serve mitigation 13.
- **HTTP transports** (`http`, `streamable-http`, `sse`), chosen by
  `FINOS_MCP_MCP_TRANSPORT`; `stdio` stays the default.
- **JWT authentication at the MCP boundary**, from a JWKS URI or a static RSA
  public key, with issuer, audience and scope checks.
- **Sign-in discovery**: with `FINOS_MCP_MCP_AUTH_BASE_URL` set, a `401`
  points clients to the server's OAuth protected-resource metadata (RFC 9728).
- **Health URLs** `/healthz` and `/readyz`, without a token, on every
  transport except `stdio`.
- **Rate and concurrency limits** for each caller, 600 requests a minute and
  10 at once by default, applied to every MCP request.
- **One log line for every tool call, resource read and prompt request**,
  with the caller and the outcome.
- **The listings survive a GitHub outage**: from the list file the server
  last wrote (`expired_cache`), else from the built-in catalog
  (`static_fallback`), and say which in `source`.
- **Releases**: built only from a pushed `v` tag, marked prerelease by their
  version, with a build provenance attestation on every file.
- **Documentation**: a deployment guide, a release-process guide, a security
  policy, and a FINOS CALM 1.2 architecture file (`calm/architecture.json`).

### Changed

- **A listing describes each document in the document's own words**, from
  its Summary or Purpose section; nothing is generated from the name.
- **The risk and mitigation prompts embed the whole catalog**, and every
  span a prompt does not write itself is enclosed in a labelled untrusted
  block.
- **A document is served as written**: no Unicode normalisation of the body,
  and a framework, kept upstream as YAML, is rendered as Markdown.
- **A configuration the server cannot use stops startup** with exit code 1
  and the reason, without a traceback; a port in use exits with code 3.
- **`initialize` reports the server's own version**, and the server no longer
  contacts `pypi.org` at startup.
- **FINOS holds the copyright and the package authorship**, and security
  reports go to security@finos.org.
- **The documentation keeps each topic in one place** and the tool reference
  documents the list, choose, get workflow and the document ids.
- **Dependencies**: fastmcp 4.1.2 or newer and the `mcp` SDK 2.

### Fixed

- **SIGTERM and SIGINT stop the server**, idle or busy, on every transport.
- **A throttled get tool says the failure is temporary**, not that the
  document does not exist.
- **`get_service_health` stays `healthy` with the cache turned off**, and
  `/readyz` notices a content host that stopped answering within seconds.
- **The parser serves documents it used to refuse or damage**: no
  frontmatter, only frontmatter, deep nesting, impossible dates, UTF-32 and
  invisible leading characters.
- **The log line says `refused` only for this server's limits**; any other
  failure is `error`.
- **A damaged list file, one owned by another user, or one an earlier
  version wrote** no longer breaks or steers the listing.

### Removed

- **`search_risks` and `search_mitigations`**, and the six settings listed in
  the upgrade notes.
- **The GitHub Contents API fallback for document bodies**: bodies come from
  the content host only.
- **Code and files nothing ran**: an unused health package, security helpers
  and exception types, a container definition that could not build, stale
  requirement files and a slide deck.

### Security

- **The JWKS URI is fetched with SSRF protection**: HTTPS and public
  addresses only, unless `FINOS_MCP_ALLOW_INSECURE_JWKS_URI=true`.
- **A base URL the fetch client would refuse stops startup**, and the fetch
  client requests only the content host and the GitHub API.
- **Sizes are bounded**: a response body as it arrives, a document at 1 MB,
  a tool response at 5 MB, and every parameter at a declared length.
- **A client reads only the error sentences the server writes**; an
  exception's own words stay in the log. GitHub tokens and other secrets are
  redacted from the log.
- **A look-alike bracket cannot end an untrusted block** in a prompt.

## 0.1.0 - 2024-12-06

### Added
- Initial development version
- Basic MCP server functionality
- FINOS AI Governance Framework integration
- Risk and mitigation content serving

[Unreleased]: https://github.com/finos/aigf-mcp-server/commits/main
