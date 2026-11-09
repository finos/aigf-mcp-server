# Integration Guide

How to call the FINOS AI Governance MCP Server from your own code. An MCP
client such as Claude Desktop needs none of this; see the
[Setup Guide](../README.md) for those.

## A client in Python

The server's own install includes the `fastmcp` client, so the virtual
environment from the [Quick Start](../../README.md#quick-start) can run this
script. It starts the server over stdio, lists the risks, chooses the ones
whose name says "injection", and gets each of them:

```python
"""List the risks, choose by name, get each chosen document."""

import asyncio
import os

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp import MCPError

SERVER = "/absolute/path/to/aigf-mcp-server/venv/bin/finos-mcp"
RATE_LIMITED = -32000  # this server's own rate or concurrency limit


async def retrying(request):
    """Run a call; wait and retry only when this server's limit refused it."""
    for attempt in range(3):
        try:
            return await request()
        except MCPError as error:
            if error.code != RATE_LIMITED or attempt == 2:
                raise
            await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


def checked(result) -> dict:
    """The structured result, or the error text the server wrote."""
    if result.is_error:
        # A missing id or an oversized document does not change on a retry,
        # so a tool error is not retried here.
        raise RuntimeError(result.content[0].text)
    return result.structured_content


async def main() -> None:
    transport = StdioTransport(
        command=SERVER,
        args=[],
        env={"FINOS_MCP_GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
    )
    async with Client(transport) as client:
        listing = checked(await retrying(
            lambda: client.call_tool("list_risks", {}, raise_on_error=False)
        ))
        print(f"{listing['total_count']} risks, listed from {listing['source']}")

        chosen = [
            risk for risk in listing["documents"]
            if "injection" in risk["name"].lower()
        ]
        for risk in chosen:
            document = checked(await retrying(
                lambda risk=risk: client.call_tool(
                    "get_risk", {"risk_id": risk["id"]}, raise_on_error=False
                )
            ))
            print(document["title"], "-", len(document["content"]), "characters")


asyncio.run(main())
```

Run it with the server's Python, after you change `SERVER` to your absolute
path:

```bash
venv/bin/python governance_client.py
```

It prints the number of risks, where the list came from, and the title and
length of each chosen document.

## What the script relies on

- **List, choose, get.** The list tools give every document with its id, name
  and description; the get tools take the id. The workflow and the id forms
  are in the [MCP Tools Reference](mcp-tools.md#workflow-list-choose-get).
- **A failed tool call is a result, not an exception.** With
  `raise_on_error=False`, `result.is_error` is true and the one text block says
  what happened. A missing id, an oversized document and an empty document do
  not change on a retry; "could not be loaded" and a GitHub rate limit can.
  [Response Schemas](response-schemas.md#error-response-examples) lists every
  message.
- **This server's own limit is a JSON-RPC error.** A client over the rate or
  concurrency limit gets `MCPError` with code `-32000` before the tool runs.
  That is the only error the script waits on and retries. The limits are in
  [Rate Limiting](mcp-tools.md#rate-limiting).
- **The token goes in the server's environment.** `FINOS_MCP_GITHUB_TOKEN`
  raises the GitHub API limit; the script passes it from `GITHUB_TOKEN`.

## A server run over HTTP

For a server started with `FINOS_MCP_MCP_TRANSPORT=http` and auth on, give
the client the URL and a token from your identity provider in place of the
transport:

```python
Client("https://mcp.example.com/mcp", auth=token)
```

`auth` takes the token itself and sends it as `Authorization: Bearer`. The
[Deployment Guide](../deployment.md#run-on-http) covers the server side.
