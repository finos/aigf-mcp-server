# Setup Guide

How to connect an MCP client to the FINOS AI Governance MCP Server, and how to
check that it works.

## Before you start

Install the server as the [Quick Start](../README.md#quick-start) in the
project README says. Then, from the `aigf-mcp-server` directory, print the
absolute path of the server's command:

```bash
echo "$PWD/venv/bin/finos-mcp"
```

A client starts the server itself, from its own working directory and without
your virtual environment active, so every configuration below names the
command by that absolute path. Use it wherever
`/absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp` appears.

## Give the server a GitHub token

Strongly recommended. The server asks the GitHub API which documents the
framework repository holds. Without a token it shares GitHub's limit of 60
requests an hour for each address; when that is spent, the `list_*` tools answer
from the list the server last saved (`"source": "expired_cache"`) or from its
built-in catalog (`"source": "static_fallback"`), and either can lag the
repository. A token raises the limit to 5,000 requests an hour. Document bodies
come from `raw.githubusercontent.com`, which this limit does not count.

A token with no scopes is enough: the server reads public files only. Create
one at <https://github.com/settings/tokens>.

Put the token in the client configuration, as the examples below show. A
variable you export in a shell does not reach a server that a desktop client
starts.

## Connect your client

### Claude Desktop

1. Open **Settings → Developer → Edit Config**. This opens
   `claude_desktop_config.json`: on macOS
   `~/Library/Application Support/Claude/claude_desktop_config.json`, on
   Windows `%APPDATA%\Claude\claude_desktop_config.json`.
2. Add the server:
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
3. Quit Claude Desktop completely and start it again.

### Claude Code

```bash
claude mcp add --scope user finos-ai-governance \
  --env FINOS_MCP_GITHUB_TOKEN=your-token-here \
  -- /absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp
```

`--scope user` makes the server available in every project; without it, it is
added for the current project only. `/mcp` in Claude Code shows whether it
connected.

### VS Code

VS Code reads MCP servers from `.vscode/mcp.json` in a workspace, or from your
user configuration (**MCP: Open User Configuration** in the Command Palette).
Its format uses `servers`, not `mcpServers`:

```json
{
  "servers": {
    "finos-ai-governance": {
      "type": "stdio",
      "command": "/absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp",
      "env": {
        "FINOS_MCP_GITHUB_TOKEN": "your-token-here"
      }
    }
  }
}
```

The tools are then available in Copilot Chat's agent mode.

### Cursor

Add the server to `~/.cursor/mcp.json` for every project, or to
`.cursor/mcp.json` in one project:

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

### Other clients

The server speaks MCP over stdio and works with any client that does. The
[MCP client list](https://modelcontextprotocol.io/clients) names more; give
each one the absolute command path and the token as above. To serve many
clients from one process over HTTP, see the
[Deployment Guide](deployment.md).

## Check that it works

Ask your client to check the service health. It calls `get_service_health`,
which answers like this:

```json
{
  "status": "healthy",
  "uptime_seconds": 12.4,
  "version": "0.1.dev443",
  "healthy_services": 4,
  "total_services": 4
}
```

Then ask it to list the frameworks. The answer's `source` is `"github_api"`
or `"cache"` when the server reached GitHub. If the client cannot start the
server, or `source` is `"static_fallback"`, see
[Troubleshooting](troubleshooting.md).

## What to ask

The server gives the documents; your client's model chooses and reads them.
For example:

- *"List the AI governance frameworks"* → `list_frameworks`
- *"Which frameworks say 'human oversight'?"* → `search_frameworks`
- *"Get the EU AI Act"* → `get_framework`
- *"Which risks cover prompt injection?"* → `list_risks`, then `get_risk`
- *"Which mitigations deal with data leakage?"* → `list_mitigations`, then `get_mitigation`

The [MCP Tools Reference](api/mcp-tools.md) documents each tool and the
list, choose, get workflow.

---

**→ [Back to the project README](../README.md)**
