# 🔧 Troubleshooting

## Common Issues

### "Command not found: finos-mcp"

**Problem**: After installation, `finos-mcp` command doesn't work.

**Solutions**:
1. **Check Python version**: Need Python 3.10+
   ```bash
   python --version  # Should be 3.10+
   ```

2. **Use full path**: Find where it was installed
   ```bash
   # If using virtual environment
   .venv/bin/finos-mcp --help
   
   # Or find it
   which finos-mcp
   ```

3. **Reinstall**: Clean install
   ```bash
   pip uninstall finos-ai-governance-mcp-server
   pip install -e .
   ```

### "Connection failed" in editor

**Problem**: Editor can't connect to MCP server.

**Solutions**:
1. **Restart your editor** after adding MCP configuration
2. **Check command path** in your MCP config:
   ```json
   {
     "mcpServers": {
       "finos-ai-governance": {
         "command": "/full/path/to/finos-mcp",  // Use full path
         "args": []
       }
     }
   }
   ```
3. **Test command manually**:
   ```bash
   finos-mcp --help  # Should work
   ```

### "No such file or directory"

**Problem**: MCP configuration points to wrong path.

**Solutions**:
1. **Find correct path**:
   ```bash
   which finos-mcp
   # Copy the full path to your MCP config
   ```

2. **Use virtual environment path**:
   ```json
   {
     "command": "/path/to/your/project/.venv/bin/finos-mcp"
   }
   ```

### Server starts but no tools available

**Problem**: MCP server runs but tools don't appear.

**Solutions**:
1. **Check server logs** - look for error messages
2. **Verify tools are loaded**:
   ```bash
   finos-mcp --help  # Should list available tools
   ```
3. **Restart editor** after configuration changes

## Getting Help

Still having issues?

1. **Check existing issues**: Open an issue on GitHub if needed
2. **Ask for help**: Use GitHub Discussions for questions
3. **Include this info** when asking for help:
   - Python version (`python --version`)
   - Operating system
   - Editor/client you're using
   - Error messages (full text)
   - Your MCP configuration

---

**→ [Back to Setup Guide](README.md)**