# 🔍 Governance Framework Reference System

**Comprehensive governance framework reference system for your development tools.**

This independent project provides access to governance frameworks and risk assessments through the Model Context Protocol (MCP), making them available in Claude, VS Code, Cursor, and other supported tools.

## 🚀 Quick Start (5 minutes)

### 1. Install
```bash
# Clone and install
git clone https://github.com/finos/aigf-mcp-server.git
cd aigf-mcp-server
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
4. ✅ Test: Ask "List all supported governance frameworks" or "Search frameworks for risk management"

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
4. ✅ Test: Use Continue chat to search framework content and AI governance risks

### Cursor
1. Open Cursor settings
2. Go to "MCP Servers"
3. Add new server:
   - **Name**: `finos-ai-governance`
   - **Command**: `finos-mcp`
4. ✅ Test: Use @ to access framework and governance tools

### Other Clients
This server works with any MCP-compatible client. See [MCP Client Directory](https://modelcontextprotocol.io/clients) for more options.

---

## 🛠️ What You Get

**11 MCP Tools** for AI governance framework access:

| Tool | What it does | Example |
|------|--------------|---------|
| **Framework Access Tools (5)** | | |
| `list_frameworks` | List all available AI governance frameworks | Browse supported frameworks (NIST, EU AI Act, ISO 42001, etc.) |
| `get_framework` | Get complete content of a specific framework | Retrieve complete framework document |
| `search_frameworks` | Search for text within framework documents | Find "risk management" across frameworks |
| `list_risks` | List all available risk documents | Get overview of AI governance risks |
| `get_risk` | Get complete content of specific risk documents | Retrieve detailed risk documentation |
| **Risk & Mitigation Tools (4)** | | |
| `search_risks` | Search within risk documentation | Find specific risks by keyword |
| `list_mitigations` | List all available mitigation documents | Get overview of mitigation strategies |
| `get_mitigation` | Get complete content of mitigation documents | Retrieve detailed mitigation strategies |
| `search_mitigations` | Search within mitigation documentation | Find specific mitigations by keyword |
| **System Monitoring Tools (2)** | | |
| `get_service_health` | Get service health status and metrics | Monitor system availability |
| `get_cache_stats` | Get cache performance statistics | Monitor cache efficiency |

---

## 💡 Common Use Cases

### Framework Research
1. *"List all supported governance frameworks"* → Uses `list_frameworks`
2. *"Search frameworks for 'risk management'"* → Uses `search_frameworks`
3. *"Get the EU AI Act framework content"* → Uses `get_framework`

### Risk Management
1. *"List all AI governance risks"* → Uses `list_risks`
2. *"Search risks for 'prompt injection'"* → Uses `search_risks`
3. *"Get details on model-inversion risk"* → Uses `get_risk`

### Mitigation Planning
1. *"List all available mitigations"* → Uses `list_mitigations`
2. *"Search for data privacy mitigations"* → Uses `search_mitigations`
3. *"Get details on data-encryption mitigation"* → Uses `get_mitigation`

### System Monitoring
1. *"Check service health"* → Uses `get_service_health`
2. *"Show cache performance"* → Uses `get_cache_stats`

---

## ⚙️ Configuration (Optional)

Set environment variables for better performance:

```bash
# Faster responses (optional)
export FINOS_MCP_CACHE_MAX_SIZE=2000
export FINOS_MCP_LOG_LEVEL=INFO
```

---

## 🔍 Content Details

**Framework Support:**
- **NIST AI Risk Management Framework** (6 references, 4 sections)
- **EU AI Act** (5 references, 4 sections)
- **OWASP LLM Top 10** (5 references, 4 sections)
- **Total**: 200+ governance references across multiple frameworks

**FINOS Content:**
- **17 AI Governance Mitigations** (mi-1 through mi-17)
- **17 AI Risk Assessments** (ri-1, ri-2, ri-3, ri-5-ri-16, ri-19, ri-23)
- Content from [FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework)
- Licensed under CC BY 4.0

**Performance:**
- Sub-0.1ms cached response times
- Advanced search indexing and caching
- Multi-level data validation

---

## 📚 More Information

- **[Tools Reference](tools-reference.md)** - Complete guide to all 11 tools
- **[Troubleshooting](troubleshooting.md)** - Fix common issues

## 🆘 Need Help?

- 🐛 [Report bugs](https://github.com/finos/aigf-mcp-server/issues)
- 💬 [Ask questions](https://github.com/finos/aigf-mcp-server/discussions)
- 🔧 [Troubleshooting guide](troubleshooting.md)

---

**Ready to start?** Pick your editor above and follow the setup! 🚀
