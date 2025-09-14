"""
Developer productivity tools for MCP development.
Live reload server and interactive testing CLI.
"""

import asyncio
import json
import os
import shlex
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any


class FileWatcher:
    """Watch files for changes and trigger callbacks."""

    def __init__(
        self,
        watch_paths: list[Path],
        patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
        on_change: Callable | None = None,
        debounce_delay: float = 0.1
    ):
        """Initialize file watcher."""
        self.watch_paths = watch_paths
        self.patterns = patterns or ["*.py"]
        self.ignore_patterns = ignore_patterns or ["__pycache__/**", "*.pyc", ".git/**"]
        self.on_change = on_change
        self.debounce_delay = debounce_delay
        self.is_running = False
        self._last_change_times = {}

    async def start(self):
        """Start watching for file changes."""
        self.is_running = True

        # Simple polling-based file watcher (KISS approach)
        file_stats = {}

        # Initialize file stats
        for watch_path in self.watch_paths:
            for file_path in self._get_watched_files(watch_path):
                try:
                    stat = file_path.stat()
                    file_stats[str(file_path)] = stat.st_mtime
                except (OSError, FileNotFoundError):
                    pass

        # Poll for changes
        while self.is_running:
            try:
                current_files = set()

                for watch_path in self.watch_paths:
                    for file_path in self._get_watched_files(watch_path):
                        current_files.add(str(file_path))

                        try:
                            stat = file_path.stat()
                            current_mtime = stat.st_mtime

                            # Check if file was modified
                            if str(file_path) in file_stats:
                                if current_mtime != file_stats[str(file_path)]:
                                    if not self._should_debounce(str(file_path)):
                                        self._last_change_times[str(file_path)] = time.time()
                                        file_stats[str(file_path)] = current_mtime

                                        if self.on_change:
                                            await self.on_change(file_path)
                            else:
                                # New file
                                file_stats[str(file_path)] = current_mtime
                                if not self._should_debounce(str(file_path)):
                                    self._last_change_times[str(file_path)] = time.time()

                                    if self.on_change:
                                        await self.on_change(file_path)

                        except (OSError, FileNotFoundError):
                            # File was deleted
                            if str(file_path) in file_stats:
                                del file_stats[str(file_path)]
                                if self.on_change:
                                    await self.on_change(file_path)

                # Remove stats for files that no longer exist
                to_remove = [f for f in file_stats.keys() if f not in current_files]
                for f in to_remove:
                    del file_stats[f]

                await asyncio.sleep(0.5)  # Poll every 500ms

            except Exception:
                # Gracefully handle watcher errors
                await asyncio.sleep(1.0)

    def _get_watched_files(self, watch_path: Path) -> list[Path]:
        """Get all files in watch path that match patterns."""
        files = []

        try:
            for root, dirs, filenames in os.walk(watch_path):
                # Filter directories by ignore patterns
                dirs[:] = [d for d in dirs if not any(
                    Path(root) / d == Path(root) / pattern.replace('/**', '')
                    for pattern in self.ignore_patterns
                    if '/**' in pattern
                )]

                for filename in filenames:
                    file_path = Path(root) / filename
                    if self._should_watch_file(file_path):
                        files.append(file_path)
        except (OSError, PermissionError):
            pass

        return files

    async def stop(self):
        """Stop watching files."""
        self.is_running = False

    def _should_watch_file(self, file_path: Path) -> bool:
        """Check if file should be watched based on patterns."""
        # Check ignore patterns first
        for ignore_pattern in self.ignore_patterns:
            if file_path.match(ignore_pattern):
                return False

        # Check if matches any watch pattern
        for pattern in self.patterns:
            if file_path.match(pattern):
                return True

        return False

    def _should_debounce(self, file_path: str) -> bool:
        """Check if file change should be debounced."""
        if file_path not in self._last_change_times:
            return False
        last_change = self._last_change_times[file_path]
        return (time.time() - last_change) < self.debounce_delay


class LiveReloadServer:
    """Live reload server for MCP development."""

    def __init__(
        self,
        mcp_command: list[str],
        watch_paths: list[Path],
        restart_delay: float = 1.0
    ):
        """Initialize live reload server."""
        self.mcp_command = mcp_command
        self.watch_paths = watch_paths
        self.restart_delay = restart_delay
        self.process = None
        self.is_running = False
        self.file_watcher = None
        self.registered_sessions = []
        self.log_handler = None
        self._restart_pending = False

    async def start(self):
        """Start the live reload server."""
        self.is_running = True

        # Start MCP process
        await self.start_mcp_process()

        # Start file watcher
        self.file_watcher = FileWatcher(
            watch_paths=self.watch_paths,
            patterns=["*.py", "*.toml", "*.json"],
            on_change=self._on_file_change
        )

        # Start watching files
        task = asyncio.create_task(self.file_watcher.start())
        # Store reference to prevent garbage collection
        self._watcher_task = task

    async def start_mcp_process(self):
        """Start the MCP process."""
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.mcp_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Start output handling
            task = asyncio.create_task(self._handle_process_streams())
            # Store reference to prevent garbage collection
            self._stream_task = task

            self._log("INFO", f"Started MCP process: {' '.join(self.mcp_command)}")
        except Exception as e:
            self._log("ERROR", f"Failed to start MCP process: {e}")

    async def stop_mcp_process(self):
        """Stop the MCP process."""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
                self._log("INFO", "Stopped MCP process")
            except Exception as e:
                self._log("ERROR", f"Error stopping MCP process: {e}")
            finally:
                self.process = None

    async def restart_mcp_process(self):
        """Restart the MCP process."""
        if self._restart_pending:
            return  # Avoid multiple concurrent restarts

        self._restart_pending = True

        try:
            self._log("INFO", "Restarting MCP process...")

            # Stop current process
            await self.stop_mcp_process()

            # Wait a bit before restarting
            await asyncio.sleep(self.restart_delay)

            # Start new process
            await self.start_mcp_process()

            # Notify registered sessions
            for session in self.registered_sessions:
                try:
                    await session.reconnect()
                except Exception:
                    pass  # Ignore session reconnection errors

        finally:
            self._restart_pending = False

    async def _on_file_change(self, file_path: Path):
        """Handle file change events."""
        self._log("INFO", f"File changed: {file_path}")

        # Restart MCP process (with simple debouncing)
        if not self._restart_pending:
            self._restart_pending = True
            # Small delay to collect multiple changes
            await asyncio.sleep(0.1)
            task = asyncio.create_task(self.restart_mcp_process())
            # Store reference to prevent garbage collection
            self._restart_task = task

    async def _handle_process_streams(self):
        """Handle MCP process stdout/stderr."""
        if not self.process:
            return

        async def read_stream(stream, level):
            while True:
                try:
                    line = await stream.readline()
                    if not line:
                        break
                    self._handle_process_output(line.decode().strip())
                except Exception:
                    break

        # Start reading both streams
        await asyncio.gather(
            read_stream(self.process.stdout, "INFO"),
            read_stream(self.process.stderr, "ERROR"),
            return_exceptions=True
        )

    def _handle_process_output(self, line: str):
        """Handle a line of process output."""
        if not line:
            return

        # Simple log level detection
        level = "INFO"
        if any(keyword in line.upper() for keyword in ["ERROR", "EXCEPTION", "FAILED"]):
            level = "ERROR"
        elif any(keyword in line.upper() for keyword in ["WARN", "WARNING"]):
            level = "WARN"

        self._log(level, line)

    def register_session(self, session):
        """Register a session for restart notifications."""
        self.registered_sessions.append(session)

    def set_log_handler(self, handler):
        """Set custom log handler."""
        self.log_handler = handler

    def _log(self, level: str, message: str):
        """Log a message."""
        if self.log_handler:
            self.log_handler(level, message)
        else:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

    async def shutdown(self):
        """Gracefully shutdown the server."""
        self.is_running = False

        if self.file_watcher:
            await self.file_watcher.stop()

        await self.stop_mcp_process()


class TestSession:
    """Interactive testing session for MCP tools."""

    def __init__(self, mcp_server_url: str):
        """Initialize test session."""
        self.server_url = mcp_server_url
        self.history = []
        self.current_context = {}
        self.connected = False
        self._available_tools = []

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return the result."""
        try:
            client = await self._get_mcp_client()
            result = await client.call_tool(tool_name, arguments)

            # Add to history
            self.history.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })

            return result

        except Exception as e:
            error_result = {"error": str(e), "type": type(e).__name__}

            # Add error to history
            self.history.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": error_result,
                "timestamp": datetime.now().isoformat()
            })

            return error_result

    async def _get_mcp_client(self):
        """Get MCP client (mock for now)."""
        # In real implementation, this would create an actual MCP client
        # For testing, we'll use a mock
        from unittest.mock import AsyncMock
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = {"content": [{"type": "text", "text": "Mock response"}]}
        mock_client.list_tools.return_value = {"tools": []}
        return mock_client

    def set_context(self, key: str, value: Any):
        """Set context value for session."""
        self.current_context[key] = value

    def get_context(self, key: str) -> Any:
        """Get context value from session."""
        return self.current_context.get(key)

    async def reconnect(self):
        """Reconnect to MCP server after restart."""
        # In real implementation, this would reconnect to the server
        self.connected = True

    def to_dict(self) -> dict:
        """Serialize session to dictionary."""
        return {
            "server_url": self.server_url,
            "history": self.history,
            "current_context": self.current_context,
            "connected": self.connected
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestSession":
        """Create session from dictionary."""
        session = cls(data["server_url"])
        session.history = data.get("history", [])
        session.current_context = data.get("current_context", {})
        session.connected = data.get("connected", False)
        return session


class InteractiveCLI:
    """Interactive command-line interface for testing MCP tools."""

    def __init__(self, mcp_server_url: str, session_file: Path | None = None):
        """Initialize interactive CLI."""
        self.server_url = mcp_server_url
        self.session_file = session_file or Path("mcp_session.json")
        self.session = TestSession(mcp_server_url)
        self.command_history = []
        self.running = False
        self._available_tools = []

    def parse_command(self, command_line: str) -> tuple[str, dict]:
        """Parse command line into command and arguments."""
        parts = shlex.split(command_line)
        if not parts:
            return "help", {}

        command = parts[0].lower()

        if command == "call" and len(parts) >= 2:
            tool_name = parts[1]
            args = {}

            # Parse key=value arguments
            for part in parts[2:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    # Remove quotes if present
                    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                        value = value[1:-1]
                    args[key] = value

            return "call", {"tool": tool_name, **args}

        elif command == "list" and len(parts) >= 2:
            return "list", {"type": parts[1]}

        elif command == "help":
            return "help", {}

        elif command == "history":
            return "history", {}

        elif command == "context":
            if len(parts) >= 3:
                return "context", {"action": "set", "key": parts[1], "value": parts[2]}
            elif len(parts) >= 2:
                return "context", {"action": "get", "key": parts[1]}
            else:
                return "context", {"action": "list"}

        else:
            return "unknown", {"command": command}

    async def handle_list_command(self, list_type: str) -> str:
        """Handle list command."""
        if list_type == "tools":
            try:
                client = await self.session._get_mcp_client()
                tools_response = await client.list_tools()
                tools = tools_response.get("tools", [])

                if not tools:
                    return "No tools available."

                result = "Available tools:\n"
                for tool in tools:
                    result += f"  {tool['name']}: {tool.get('description', 'No description')}\n"

                return result
            except Exception as e:
                return f"Error listing tools: {e}"

        return f"Unknown list type: {list_type}"

    async def call_tool_interactive(self, tool_name: str, schema: dict) -> dict:
        """Call tool with interactive parameter prompting."""
        arguments = {}

        # Get parameters from schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for param_name, param_info in properties.items():
            prompt = f"Enter {param_name}"
            if "description" in param_info:
                prompt += f" ({param_info['description']})"

            default = param_info.get("default")
            if default is not None:
                prompt += f" [default: {default}]"

            prompt += ": "

            try:
                value = input(prompt)
                if not value and default is not None:
                    value = str(default)

                # Type conversion
                param_type = param_info.get("type", "string")
                if param_type == "integer":
                    value = int(value)
                elif param_type == "number":
                    value = float(value)
                elif param_type == "boolean":
                    value = value.lower() in ("true", "yes", "1", "y")

                arguments[param_name] = value

            except (ValueError, EOFError):
                if param_name in required:
                    print(f"Error: {param_name} is required")
                    return None

        # Execute tool
        return await self.session.execute_tool(tool_name, arguments)

    def save_session(self):
        """Save session to file."""
        try:
            with open(self.session_file, "w") as f:
                json.dump(self.session.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving session: {e}")

    def load_session(self):
        """Load session from file."""
        try:
            if self.session_file.exists():
                with open(self.session_file) as f:
                    data = json.load(f)
                self.session = TestSession.from_dict(data)
        except Exception as e:
            print(f"Error loading session: {e}")

    def get_completions(self, text: str) -> list[str]:
        """Get command completions for text."""
        if text.startswith("call "):
            # Tool name completion
            prefix = text[5:]  # Remove "call "
            return [tool for tool in self._available_tools if tool.startswith(prefix)]

        commands = ["call", "list", "help", "history", "context", "quit", "exit"]
        return [cmd for cmd in commands if cmd.startswith(text)]

    def add_to_history(self, command: str):
        """Add command to history."""
        self.command_history.append(command)

        # Keep history size manageable
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]

    def search_history(self, pattern: str) -> list[str]:
        """Search command history."""
        return [cmd for cmd in self.command_history if pattern.lower() in cmd.lower()]

    async def run(self):
        """Run the interactive CLI."""
        self.running = True
        print("MCP Interactive Testing CLI")
        print(f"Connected to: {self.server_url}")
        print("Type 'help' for available commands or 'quit' to exit\n")

        # Load previous session
        self.load_session()

        while self.running:
            try:
                command_line = input("mcp> ").strip()
                if not command_line:
                    continue

                # Add to history
                self.add_to_history(command_line)

                # Parse and execute command
                command, args = self.parse_command(command_line)

                if command in ("quit", "exit"):
                    break
                elif command == "help":
                    self._show_help()
                elif command == "list":
                    result = await self.handle_list_command(args["type"])
                    print(result)
                elif command == "call":
                    result = await self.session.execute_tool(args["tool"], {k: v for k, v in args.items() if k != "tool"})
                    print(f"Result: {result}")
                elif command == "history":
                    self._show_history()
                elif command == "context":
                    self._handle_context_command(args)
                else:
                    print(f"Unknown command: {command}")

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"Error: {e}")

        # Save session before exit
        self.save_session()
        print("\nSession saved. Goodbye!")

    def _show_help(self):
        """Show help information."""
        help_text = """
Available commands:
  call <tool> [param=value ...]  - Execute a tool with parameters
  list tools                     - List available tools
  history                        - Show command history
  context [key [value]]          - Manage session context
  help                          - Show this help
  quit/exit                     - Exit the CLI

Examples:
  call search_documents query='AI governance'
  list tools
  context current_doc doc_123
"""
        print(help_text)

    def _show_history(self):
        """Show execution history."""
        if not self.session.history:
            print("No execution history.")
            return

        print("Execution History:")
        for i, entry in enumerate(self.session.history[-10:], 1):  # Show last 10
            print(f"  {i}. {entry['tool']} - {entry['timestamp']}")

    def _handle_context_command(self, args: dict):
        """Handle context management commands."""
        action = args.get("action", "list")

        if action == "list":
            if not self.session.current_context:
                print("No context variables set.")
            else:
                print("Context variables:")
                for key, value in self.session.current_context.items():
                    print(f"  {key} = {value}")
        elif action == "get":
            key = args["key"]
            value = self.session.get_context(key)
            if value is not None:
                print(f"{key} = {value}")
            else:
                print(f"Context variable '{key}' not found.")
        elif action == "set":
            key = args["key"]
            value = args["value"]
            self.session.set_context(key, value)
            print(f"Set {key} = {value}")

