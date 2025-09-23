# 🔍 Governance Framework Reference System

**Comprehensive governance framework reference system for your development tools.**

This independent project provides access to governance frameworks, compliance analysis, and risk assessments through the Model Context Protocol (MCP), making them available in Claude, VS Code, Cursor, and other supported tools.

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
4. ✅ Test: Use Continue chat to search framework content and compliance analysis

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

**21 Tools** for governance framework access:

| Tool | What it does | Example |
|------|--------------|---------|
| **Framework Tools** | | |
| `search_frameworks` | Cross-framework search | "risk management" |
| `list_frameworks` | Show supported frameworks | Browse available frameworks |
| `get_framework_details` | Get framework information | Get "nist-ai-rmf" details |
| `get_compliance_analysis` | Compliance metrics | Framework coverage analysis |
| `search_framework_references` | Framework-specific search | "injection" in OWASP |
| **Cross-Framework Navigation** | | |
| `get_related_controls` | Find equivalent controls | Map NIST control to EU AI Act |
| `get_framework_correlations` | Analyze framework relationships | NIST ↔ EU AI Act correlations |
| `find_compliance_gaps` | Identify compliance gaps | Gap analysis for multiple frameworks |
| **Advanced Search & Export** | | |
| `advanced_search_frameworks` | Advanced multi-criteria search | Complex filtering across frameworks |
| `export_framework_data` | Export framework data | JSON/CSV/Markdown export |
| `bulk_export_frameworks` | Bulk export operations | Multiple framework datasets |
| **FINOS Tools** | | |
| `search_mitigations` | Find governance strategies | "data privacy protection" |
| `search_risks` | Find AI risks | "prompt injection" |
| `get_mitigation_details` | Get full mitigation (mi-1 to mi-17) | Get mitigation "mi-1" |
| `get_risk_details` | Get full risk assessment (ri-1, ri-2, etc.) | Get risk "ri-2" |
| `list_all_mitigations` | Show all 17 mitigations | Browse all available |
| `list_all_risks` | Show all 17 risks | Browse all available |
| **System Tools** | | |
| `get_service_health` | Check if server is working | Service status |
| `get_service_metrics` | Performance statistics | How fast is it? |
| `get_cache_stats` | Cache performance | Memory usage |
| `reset_service_health` | Reset error counters | Clear errors |

---

## 💡 Common Use Cases

### "I need framework compliance guidance"
1. Ask your AI assistant: *"List all supported governance frameworks"*
2. Search across frameworks: *"Search frameworks for 'data protection'"*
3. Get detailed analysis: *"Get compliance analysis for my requirements"*

### "I'm researching specific governance areas"
1. Cross-framework search: *"Search frameworks for 'risk management'"*
2. Framework-specific: *"Search NIST AI RMF for 'testing'"*
3. Get framework details: *"Get framework details for eu-ai-act"*

### "I need legacy FINOS content"
1. Search mitigations: *"Search for data privacy mitigations"*
2. Get specific details: *"Show me mitigation mi-1"*
3. Find related risks: *"Find prompt injection risks"*

### "I need a governance overview"
1. Browse frameworks: *"List all frameworks and their coverage"*
2. Analyze compliance: *"Get compliance analysis across all frameworks"*

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

- **[Tools Reference](tools-reference.md)** - Complete guide to all 15 tools
- **[Troubleshooting](troubleshooting.md)** - Fix common issues

## 🆘 Need Help?

- 🐛 [Report bugs](https://github.com/hugo-calderon/finos-mcp-server/issues)
- 💬 [Ask questions](https://github.com/hugo-calderon/finos-mcp-server/discussions)
- 🔧 [Troubleshooting guide](troubleshooting.md)

---

**Ready to start?** Pick your editor above and follow the setup! 🚀
