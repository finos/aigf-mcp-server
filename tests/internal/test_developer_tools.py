"""
Tests for developer productivity tools.
Live reload server and interactive testing CLI for MCP development.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finos_mcp.internal.developer_tools import (
    FileWatcher,
    InteractiveCLI,
    LiveReloadServer,
    TestSession,
)


class TestFileWatcher:
    """Test file watching functionality."""

    def test_watcher_creation(self):
        """Test creating file watcher."""
        watcher = FileWatcher(watch_paths=[Path("src")], patterns=["*.py"])
        assert watcher.watch_paths == [Path("src")]
        assert "*.py" in watcher.patterns
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_file_change_detection(self):
        """Test detecting file changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("# Initial content")

            changes = []

            async def on_change(file_path):
                changes.append(file_path)

            watcher = FileWatcher(
                watch_paths=[Path(temp_dir)], patterns=["*.py"], on_change=on_change
            )

            # Start watching
            watch_task = asyncio.create_task(watcher.start())
            await asyncio.sleep(0.01)  # Let watcher initialize

            # Modify file
            test_file.write_text("# Modified content")
            await asyncio.sleep(0.6)  # Wait for polling cycle (500ms + buffer)

            # Stop watching
            await watcher.stop()
            watch_task.cancel()

            # Should have detected change
            assert len(changes) > 0
            assert test_file in [Path(p) for p in changes]

    @pytest.mark.asyncio
    async def test_multiple_file_patterns(self):
        """Test watching multiple file patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / "test.py"
            toml_file = Path(temp_dir) / "config.toml"
            txt_file = Path(temp_dir) / "readme.txt"

            py_file.write_text("print('test')")
            toml_file.write_text("[tool.test]")
            txt_file.write_text("Not watched")

            changes = []

            async def on_change(file_path):
                changes.append(Path(file_path).name)

            watcher = FileWatcher(
                watch_paths=[Path(temp_dir)],
                patterns=["*.py", "*.toml"],
                on_change=on_change,
            )

            # Start watching
            watch_task = asyncio.create_task(watcher.start())
            await asyncio.sleep(0.01)

            # Modify watched files
            py_file.write_text("print('modified')")
            toml_file.write_text("[tool.modified]")
            txt_file.write_text("Still not watched")

            await asyncio.sleep(0.6)
            await watcher.stop()
            watch_task.cancel()

            # Should detect .py and .toml changes, but not .txt
            change_names = set(changes)
            assert "test.py" in change_names
            assert "config.toml" in change_names
            assert "readme.txt" not in change_names

    def test_debounce_functionality(self):
        """Test change event debouncing."""
        watcher = FileWatcher(watch_paths=[Path(".")], debounce_delay=0.1)
        assert watcher.debounce_delay == 0.1

        # Test debounce logic
        assert watcher._should_debounce("test.py") is False
        watcher._last_change_times["test.py"] = time.time()
        assert watcher._should_debounce("test.py") is True

    @pytest.mark.asyncio
    async def test_ignore_patterns(self):
        """Test ignoring certain file patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            watched_file = Path(temp_dir) / "important.py"
            ignored_file = Path(temp_dir) / "__pycache__" / "cached.pyc"
            ignored_file.parent.mkdir()

            watched_file.write_text("important")
            ignored_file.write_text("cached")

            changes = []

            async def on_change(file_path):
                changes.append(Path(file_path).name)

            watcher = FileWatcher(
                watch_paths=[Path(temp_dir)],
                patterns=["*.py", "*.pyc"],
                ignore_patterns=["__pycache__/**"],
                on_change=on_change,
            )

            watch_task = asyncio.create_task(watcher.start())
            await asyncio.sleep(0.01)

            watched_file.write_text("modified important")
            ignored_file.write_text("modified cached")

            await asyncio.sleep(0.6)
            await watcher.stop()
            watch_task.cancel()

            # Should only detect the non-ignored file
            assert "important.py" in changes
            assert "cached.pyc" not in changes


class TestLiveReloadServer:
    """Test live reload server functionality."""

    @pytest.mark.asyncio
    async def test_server_creation(self):
        """Test creating live reload server."""
        server = LiveReloadServer(
            mcp_command=["python", "-m", "finos_mcp"], watch_paths=[Path("src")]
        )

        assert server.mcp_command == ["python", "-m", "finos_mcp"]
        assert server.watch_paths == [Path("src")]
        assert server.process is None
        assert not server.is_running

    @pytest.mark.asyncio
    async def test_mcp_process_management(self):
        """Test starting and stopping MCP process."""
        server = LiveReloadServer(mcp_command=["echo", "test"], watch_paths=[Path(".")])

        # Mock process creation
        mock_process = Mock()
        future = asyncio.get_event_loop().create_future()
        future.set_result(0)
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.terminate = Mock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await server.start_mcp_process()
            assert server.process == mock_process

            await server.stop_mcp_process()
            mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_restart_on_file_change(self):
        """Test automatic restart when files change."""
        restart_count = 0

        async def mock_restart():
            nonlocal restart_count
            restart_count += 1

        server = LiveReloadServer(mcp_command=["echo", "test"], watch_paths=[Path(".")])
        server.restart_mcp_process = mock_restart

        # Simulate file change
        await server._on_file_change("test.py")
        await asyncio.sleep(0.01)  # Let restart complete

        assert restart_count == 1

    @pytest.mark.asyncio
    async def test_restart_debouncing(self):
        """Test that rapid file changes are debounced."""
        restart_count = 0

        async def mock_restart():
            nonlocal restart_count
            restart_count += 1

        server = LiveReloadServer(mcp_command=["echo", "test"], watch_paths=[Path(".")])
        server.restart_mcp_process = mock_restart

        # Rapid file changes
        await server._on_file_change("test1.py")
        await server._on_file_change("test2.py")
        await server._on_file_change("test3.py")

        # Should only restart once due to debouncing
        await asyncio.sleep(0.2)
        assert restart_count == 1

    def test_log_output_handling(self):
        """Test MCP process log output handling."""
        server = LiveReloadServer(mcp_command=["echo", "test"], watch_paths=[Path(".")])

        logs = []

        def mock_log_handler(level, message):
            logs.append((level, message))

        server.set_log_handler(mock_log_handler)
        server._handle_process_output("INFO: Server started")
        server._handle_process_output("ERROR: Connection failed")

        assert len(logs) == 2
        assert logs[0][0] == "INFO"
        assert "Server started" in logs[0][1]
        assert logs[1][0] == "ERROR"

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful server shutdown."""
        server = LiveReloadServer(mcp_command=["sleep", "10"], watch_paths=[Path(".")])

        # Mock components
        server.file_watcher = Mock()
        server.file_watcher.stop = AsyncMock()
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()
        server.process = mock_process

        await server.shutdown()

        server.file_watcher.stop.assert_called_once()
        mock_process.terminate.assert_called_once()


class TestTestSession:
    """Test interactive testing session."""

    def test_session_creation(self):
        """Test creating test session."""
        session = TestSession(mcp_server_url="stdio://mcp-server")
        assert session.server_url == "stdio://mcp-server"
        assert len(session.history) == 0
        assert session.current_context == {}

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test executing tools in session."""
        session = TestSession(mcp_server_url="test://server")

        # Mock MCP client
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = {
            "content": [{"type": "text", "text": "Tool result"}]
        }

        with patch.object(session, "_get_mcp_client", return_value=mock_client):
            result = await session.execute_tool("search_documents", {"query": "test"})

            assert "Tool result" in str(result)
            mock_client.call_tool.assert_called_once_with(
                "search_documents", {"query": "test"}
            )

    @pytest.mark.asyncio
    async def test_session_history_tracking(self):
        """Test session history tracking."""
        session = TestSession(mcp_server_url="test://server")

        # Mock successful execution
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = {
            "content": [{"type": "text", "text": "Success"}]
        }

        with patch.object(session, "_get_mcp_client", return_value=mock_client):
            await session.execute_tool("test_tool", {"param": "value"})

        assert len(session.history) == 1
        assert session.history[0]["tool"] == "test_tool"
        assert session.history[0]["arguments"] == {"param": "value"}
        assert "Success" in str(session.history[0]["result"])

    @pytest.mark.asyncio
    async def test_error_handling_in_session(self):
        """Test error handling during tool execution."""
        session = TestSession(mcp_server_url="test://server")

        # Mock client that raises error
        mock_client = AsyncMock()
        mock_client.call_tool.side_effect = Exception("Tool execution failed")

        with patch.object(session, "_get_mcp_client", return_value=mock_client):
            result = await session.execute_tool("failing_tool", {})

        # Should handle error gracefully
        assert "error" in result
        assert "Tool execution failed" in str(result["error"])

    def test_session_context_management(self):
        """Test session context for stateful interactions."""
        session = TestSession(mcp_server_url="test://server")

        # Set context
        session.set_context("current_document", "doc_123")
        session.set_context("user_preferences", {"theme": "dark"})

        assert session.get_context("current_document") == "doc_123"
        assert session.get_context("user_preferences")["theme"] == "dark"
        assert session.get_context("nonexistent") is None

    def test_session_serialization(self):
        """Test saving and loading session state."""
        session = TestSession(mcp_server_url="test://server")
        session.set_context("test_key", "test_value")
        session.history.append(
            {
                "tool": "test_tool",
                "arguments": {},
                "result": "test_result",
                "timestamp": "2025-01-01T00:00:00Z",
            }
        )

        # Serialize session
        serialized = session.to_dict()

        # Create new session from serialized data
        new_session = TestSession.from_dict(serialized)

        assert new_session.server_url == session.server_url
        assert new_session.get_context("test_key") == "test_value"
        assert len(new_session.history) == 1
        assert new_session.history[0]["tool"] == "test_tool"


class TestInteractiveCLI:
    """Test interactive CLI functionality."""

    def test_cli_creation(self):
        """Test creating interactive CLI."""
        cli = InteractiveCLI(
            mcp_server_url="stdio://server", session_file=Path("test_session.json")
        )

        assert cli.server_url == "stdio://server"
        assert cli.session_file == Path("test_session.json")
        assert cli.session is not None

    @pytest.mark.asyncio
    async def test_command_parsing(self):
        """Test parsing CLI commands."""
        cli = InteractiveCLI(mcp_server_url="test://server")

        # Test tool execution command
        cmd, args = cli.parse_command("call search_documents query='test query'")
        assert cmd == "call"
        assert args["tool"] == "search_documents"
        assert args["query"] == "test query"

        # Test list command
        cmd, args = cli.parse_command("list tools")
        assert cmd == "list"
        assert args["type"] == "tools"

        # Test help command
        cmd, args = cli.parse_command("help")
        assert cmd == "help"

    @pytest.mark.asyncio
    async def test_tool_listing(self):
        """Test listing available tools."""
        cli = InteractiveCLI(mcp_server_url="test://server")

        # Mock MCP client
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = {
            "tools": [
                {"name": "search_documents", "description": "Search documents"},
                {"name": "get_document", "description": "Get document by ID"},
            ]
        }

        with patch.object(cli.session, "_get_mcp_client", return_value=mock_client):
            result = await cli.handle_list_command("tools")

        assert "search_documents" in result
        assert "get_document" in result
        assert "Search documents" in result

    @pytest.mark.asyncio
    async def test_interactive_tool_calling(self):
        """Test interactive tool calling with prompts."""
        cli = InteractiveCLI(mcp_server_url="test://server")

        # Mock tool execution
        cli.session.execute_tool = AsyncMock(return_value={"result": "Success"})

        with patch("builtins.input", side_effect=["test query", "10"]):
            result = await cli.call_tool_interactive(
                "search_documents",
                {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Result limit",
                        "default": 5,
                    },
                },
            )

        assert result is not None
        cli.session.execute_tool.assert_called_once()

    def test_session_persistence(self):
        """Test saving and loading CLI sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / "test_session.json"

            # Create CLI and modify session
            cli = InteractiveCLI(
                mcp_server_url="test://server", session_file=session_file
            )
            cli.session.set_context("test", "value")

            # Save session
            cli.save_session()
            assert session_file.exists()

            # Load session in new CLI
            new_cli = InteractiveCLI(
                mcp_server_url="test://server", session_file=session_file
            )
            new_cli.load_session()

            assert new_cli.session.get_context("test") == "value"

    @pytest.mark.asyncio
    async def test_auto_completion(self):
        """Test command auto-completion."""
        cli = InteractiveCLI(mcp_server_url="test://server")

        # Mock available tools
        cli._available_tools = ["search_documents", "get_document", "list_users"]

        completions = cli.get_completions("call search")
        assert "search_documents" in completions
        assert "get_document" not in completions  # Doesn't match prefix

        completions = cli.get_completions("call ")
        assert len(completions) == 3  # All tools available

    def test_command_history(self):
        """Test command history management."""
        cli = InteractiveCLI(mcp_server_url="test://server")

        # Add commands to history
        cli.add_to_history("list tools")
        cli.add_to_history("call search_documents query='test'")
        cli.add_to_history("help")

        assert len(cli.command_history) == 3
        assert cli.command_history[0] == "list tools"

        # Test history search
        search_results = cli.search_history("search")
        assert len(search_results) == 1
        assert "search_documents" in search_results[0]


class TestIntegration:
    """Test integration between developer tools."""

    @pytest.mark.asyncio
    async def test_live_reload_with_cli_session(self):
        """Test live reload server with active CLI session."""
        # Mock CLI session
        mock_session = Mock()
        mock_session.reconnect = AsyncMock()

        # Create live reload server
        server = LiveReloadServer(mcp_command=["echo", "test"], watch_paths=[Path(".")])
        server.register_session(mock_session)

        # Mock restart method to track calls
        restart_called = False

        async def mock_restart():
            nonlocal restart_called
            restart_called = True
            # Simulate notifying sessions
            for session in server.registered_sessions:
                await session.reconnect()

        server.restart_mcp_process = mock_restart

        # Simulate restart
        await server._on_file_change("test.py")
        await asyncio.sleep(0.2)

        # Session should be notified to reconnect
        assert restart_called
        mock_session.reconnect.assert_called()

    @pytest.mark.asyncio
    async def test_full_development_workflow(self):
        """Test complete development workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test environment
            test_file = Path(temp_dir) / "mcp_tool.py"
            test_file.write_text("def test_tool(): return 'v1'")

            session_file = Path(temp_dir) / "session.json"

            # Create live reload server
            server = LiveReloadServer(
                mcp_command=["python", "-c", "print('MCP Server Started')"],
                watch_paths=[Path(temp_dir)],
            )

            # Create CLI session
            cli = InteractiveCLI(
                mcp_server_url="stdio://server", session_file=session_file
            )

            # Register CLI with server for reload notifications
            server.register_session(cli.session)

            # Start components (mock actual startup)
            server.is_running = True
            cli.session.connected = True

            # Simulate development cycle
            restart_called = False

            async def mock_restart():
                nonlocal restart_called
                restart_called = True

            server.restart_mcp_process = mock_restart

            # Modify file (simulating development)
            test_file.write_text("def test_tool(): return 'v2'")
            await server._on_file_change(str(test_file))
            await asyncio.sleep(0.01)

            # Should trigger restart
            assert restart_called is True

            # CLI session should be ready for testing
            assert cli.session is not None
