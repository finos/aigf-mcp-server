# 🔧 Troubleshooting

The commands below run from the directory you cloned the server into, with
the virtual environment the setup guide created in `venv/`.

## Where the server's log is

The server writes its log to stderr. On `stdio` your MCP client starts the
server and keeps that output:

- **Claude Desktop** writes it to `~/Library/Logs/Claude/mcp-server-<name>.log`
  on macOS and `%APPDATA%\Claude\logs\mcp-server-<name>.log` on Windows, where
  `<name>` is the key you gave the server in the client configuration.
- **Claude Code** shows the server's state with `/mcp`; start it with
  `claude --debug` to see the server's output.
- **Run the server yourself** to read the log in your terminal:
  ```bash
  venv/bin/finos-mcp
  ```
  It then waits for a client on stdin; stop it with Ctrl+C.

`FINOS_MCP_LOG_LEVEL=DEBUG` gives more detail.

## Common Issues

### Lists look old, or `source` is `static_fallback`

**Problem**: `list_frameworks`, `list_risks` or `list_mitigations` answers with
`"source": "static_fallback"` or `"source": "expired_cache"`, or a document you
know exists is not listed.

**Cause**: the server could not list the documents through the GitHub API, so
it answered from the list file it last wrote (`expired_cache`) or from the list
built into the server (`static_fallback`). The usual reason is GitHub's limit
of 60 API requests an hour for a client without a token, which several
servers or tests on one address share.

**Solution**: give the server a GitHub token. A token with no scopes is enough:
the server reads public files only. Create one at
<https://github.com/settings/tokens>, then put it in the `env` block of your
client configuration, because a variable exported in a shell does not reach a
server that a desktop client starts:

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "/absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp",
      "env": {
        "FINOS_MCP_GITHUB_TOKEN": "your-token-here"
      }
    }
  }
}
```

Restart the client. The next listing reports `"source": "github_api"`.

### "Command not found: finos-mcp"

**Problem**: After installation, the `finos-mcp` command is not found.

**Solutions**:
1. **Use the command in the virtual environment.** The install puts
   `finos-mcp` in `venv/bin/`, which is on your `PATH` only while the
   environment is active. Check that it is there:
   ```bash
   ls venv/bin/finos-mcp
   ```
   and use that path, or activate the environment with
   `source venv/bin/activate` (`venv\Scripts\activate` on Windows).
2. **Check the Python version** the environment was made with. It must be 3.11
   or newer:
   ```bash
   venv/bin/python --version
   ```
   If it is older, delete `venv/` and make it again with a newer Python, as
   the [setup guide](README.md) describes.
3. **Reinstall** into the environment:
   ```bash
   venv/bin/pip install -e .
   ```

### "Connection failed" or "No such file or directory" in the client

**Problem**: The client cannot start the server.

**Solutions**:
1. **Name the command by its absolute path.** A client does not start the
   server from your clone directory, so a relative path such as
   `venv/bin/finos-mcp` does not resolve. Print the absolute path:
   ```bash
   echo "$PWD/venv/bin/finos-mcp"
   ```
   and put it in the configuration:
   ```json
   {
     "mcpServers": {
       "finos-ai-governance": {
         "command": "/absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp"
       }
     }
   }
   ```
2. **Check that the package is installed** in that environment:
   ```bash
   venv/bin/python -c "import finos_mcp; print(finos_mcp.__version__)"
   ```
3. **Restart the client** after you change its configuration.

### Server starts but no tools available

**Problem**: The server runs but its tools do not appear.

**Solutions**:
1. **Read the server's log** for error messages; see
   [Where the server's log is](#where-the-servers-log-is).
2. **List the tools the server publishes**, without your client in between.
   The MCP Inspector runs through `npx`, so it needs
   [Node.js](https://nodejs.org/):
   ```bash
   npx @modelcontextprotocol/inspector --cli venv/bin/finos-mcp --method tools/list
   ```
3. **Restart the client** after configuration changes.

### Every request returns 401 after configuring a JWKS URI

**Problem**: JWT auth is enabled with `FINOS_MCP_MCP_AUTH_JWKS_URI`, the server starts
normally, but every request — including one carrying a token you know is valid — is
rejected with `401`.

**Cause**: the JWKS URI is fetched with SSRF protection by default, which permits only
HTTPS and only public unicast addresses. If the identity provider is an internal service,
the fetch is refused, no signing key is ever loaded, and every signature check fails. The
refusal is logged by FastMCP at `DEBUG`, so nothing appears at the default `INFO` level.

**Solutions**:

1. **Confirm the diagnosis** — restart with FastMCP's debug logging and look for the block:
   ```bash
   FASTMCP_LOG_LEVEL=DEBUG venv/bin/finos-mcp
   ```
   The line reads `JWKS fetch blocked by SSRF protection: ...`. It comes from
   FastMCP's own logger, which `FINOS_MCP_LOG_LEVEL` does not set.

2. **Preferred** — point `FINOS_MCP_MCP_AUTH_JWKS_URI` at a publicly resolvable HTTPS
   endpoint.

3. **If the identity provider really is internal** — opt out explicitly:
   ```bash
   export FINOS_MCP_ALLOW_INSECURE_JWKS_URI=true
   ```
   This permits plain HTTP and private addresses for the JWKS fetch, and logs an error on
   every startup. Over plain HTTP, anyone on the network path can substitute the signing
   keys and mint tokens the server will accept, so prefer HTTPS even internally.

Note that the statically detectable cases — a non-HTTPS URI, or a literal loopback,
link-local or private address — **fail at startup** with a message naming the setting
above, rather than reaching this symptom. A hostname that only resolves privately cannot
be detected without a DNS lookup, so it produces the `401` described here.

## Getting Help

Still having issues?

1. **Search the issues**, and open one if yours is not there:
   <https://github.com/finos/aigf-mcp-server/issues>
2. **Ask FINOS** at help@finos.org for questions about the project.
3. **Include this information**:
   - Python version (`venv/bin/python --version`)
   - Operating system
   - The MCP client you use
   - The full error message and the server's log
   - Your MCP configuration, with any token removed

---

**→ [Back to Setup Guide](README.md)**
