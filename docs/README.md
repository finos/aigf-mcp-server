# 🤖 AI Governance MCP Server

**Simple access to AI governance content for your development tools.**

This independent project provides AI governance mitigations and risk assessments through the Model Context Protocol (MCP), making them available in Claude, VS Code, Cursor, and other supported tools.

## 🚀 Quick Start (5 minutes)

### 1. Install
```bash
# Clone and install
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
pip install -e .
```

### 2. Test
```bash
finos-mcp --help
```
✅ You should see the help message.

### 3. Connect to your editor
Choose your tool:
- **[Claude Desktop](#claude-desktop)** - Most popular
- **[VS Code](#vs-code)** - With Continue.dev extension
- **[Cursor](#cursor)** - Built-in MCP support
- **[Other clients](#other-clients)** - See full list

---

## 🔧 Client Setup

### Claude Desktop
1. Open Claude Desktop settings (⚙️ icon)
2. Add this configuration:
```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "finos-mcp",
      "args": []
    }
  }
}
```
3. Restart Claude Desktop
4. ✅ Test: Ask "Search for AI governance mitigations about data privacy"

### VS Code
1. Install the [Continue.dev extension](https://marketplace.visualstudio.com/items?itemName=Continue.continue)
2. Open Continue settings (Ctrl+Shift+P → "Continue: Open Config")
3. Add MCP server:
```json
{
  "mcpServers": [
    {
      "name": "finos-ai-governance",
      "command": "finos-mcp"
    }
  ]
}
```
4. ✅ Test: Use Continue chat to search governance content

### Cursor
1. Open Cursor settings
2. Go to "MCP Servers"
3. Add new server:
   - **Name**: `finos-ai-governance`
   - **Command**: `finos-mcp`
4. ✅ Test: Use @ to access governance tools

### Other Clients
This server works with any MCP-compatible client. See [MCP Client Directory](https://modelcontextprotocol.io/clients) for more options.

---

## 🛠️ What You Get

**10 Tools** for AI governance content:

| Tool | What it does | Example |
|------|--------------|---------|
| `search_mitigations` | Find governance strategies | "data privacy protection" |
| `search_risks` | Find AI risks | "prompt injection" |
| `get_mitigation_details` | Get full mitigation (mi-1 to mi-17) | Get mitigation "mi-1" |
| `get_risk_details` | Get full risk assessment (ri-1, ri-2, etc.) | Get risk "ri-2" |
| `list_all_mitigations` | Show all 17 mitigations | Browse all available |
| `list_all_risks` | Show all 17 risks | Browse all available |
| `get_service_health` | Check if server is working | Service status |
| `get_service_metrics` | Performance statistics | How fast is it? |
| `get_cache_stats` | Cache performance | Memory usage |
| `reset_service_health` | Reset error counters | Clear errors |

---

## 💡 Common Use Cases

### "I need to protect user data"
1. Ask your AI assistant: *"Search for data privacy mitigations"*
2. Get specific details: *"Show me mitigation mi-1"*
3. Check related risks: *"What are the data leakage risks?"*

### "I'm worried about prompt injection"
1. Search risks: *"Find prompt injection risks"*
2. Get details: *"Show me risk ri-2"*
3. Find protections: *"Search for input validation mitigations"*

### "I need a governance overview"
1. Browse content: *"List all mitigations and risks"*
2. Focus areas: *"Search for compliance-related content"*

---

## ⚙️ Configuration (Optional)

Set environment variables for better performance:

```bash
# Better GitHub API limits (optional)
export FINOS_MCP_GITHUB_TOKEN="your_github_token"

# Faster responses (optional)
export FINOS_MCP_CACHE_MAX_SIZE=2000
export FINOS_MCP_LOG_LEVEL=INFO
```

---

## 🔍 Content Details

- **17 AI Governance Mitigations** (mi-1 through mi-17)
- **17 AI Risk Assessments** (ri-1, ri-2, ri-3, ri-5-ri-16, ri-19, ri-23)
- Content from [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework)
- Licensed under CC BY 4.0

---

## 📚 More Information

- **[Tools Reference](tools-reference.md)** - Complete guide to all 10 tools
- **[Troubleshooting](troubleshooting.md)** - Fix common issues

## 🆘 Need Help?

- 🐛 [Report bugs](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 💬 [Ask questions](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 🔧 [Troubleshooting guide](troubleshooting.md)

---

**Ready to start?** Pick your editor above and follow the setup! 🚀
