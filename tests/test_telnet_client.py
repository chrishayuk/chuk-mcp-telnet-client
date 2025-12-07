"""
Comprehensive tests for the telnet client MCP server.

Tests cover:
- Tool functionality
- Session management
- Error handling
- Edge cases
- Performance characteristics
"""

import pytest
import telnetlib
import time
from unittest.mock import MagicMock

from chuk_mcp_telnet_client.models import (
    CommandResponse,
    TelnetClientInput,
    TelnetClientOutput,
)
from chuk_mcp_telnet_client.tools import (
    SessionCloseResponse,
    SessionInfo,
    SessionListResponse,
    SessionStore,
    TelnetCommand,
    TelnetDefaults,
    TelnetSession,
    _connect_telnet,
    _create_negotiation_callback,
    _execute_command,
    _session_store,
    _strip_command_echo,
    telnet_client_tool,
    telnet_close_session,
    telnet_list_sessions,
)


# ============================================================================
# Fixtures
# ============================================================================


class FakeTelnet:
    """Mock Telnet connection for testing."""

    def __init__(self):
        self.commands_sent = []
        self.closed = False
        self.host = None
        self.port = None
        self.callback = None

    def set_option_negotiation_callback(self, callback):
        """Set negotiation callback."""
        self.callback = callback

    def open(self, host, port, timeout):
        """Simulate opening a connection."""
        self.host = host
        self.port = port

    def write(self, data):
        """Simulate writing data."""
        cmd = data.decode("utf-8").strip()
        self.commands_sent.append(cmd)

    def read_very_eager(self):
        """Simulate reading available data."""
        if not self.commands_sent:
            return b"Welcome to FakeTelnet Server\r\n"

        last_cmd = self.commands_sent[-1].replace("\r\n", "")
        return f"{last_cmd}\r\nResponse to {last_cmd}\r\n".encode("utf-8")

    def read_some(self):
        """Simulate reading some data."""
        if not self.commands_sent:
            return b"Welcome to FakeTelnet Server\r\n"

        last_cmd = self.commands_sent[-1].replace("\r\n", "")
        return f"Response to {last_cmd}\r\n".encode("utf-8")

    def close(self):
        """Simulate closing connection."""
        self.closed = True


@pytest.fixture
def fake_telnet(monkeypatch):
    """Provide a fake telnet connection."""
    monkeypatch.setattr(telnetlib, "Telnet", lambda: FakeTelnet())
    # Clear session store
    _session_store._sessions.clear()
    yield
    _session_store._sessions.clear()


@pytest.fixture
def session_store():
    """Provide a fresh session store."""
    return SessionStore()


# ============================================================================
# Model Tests
# ============================================================================


def test_telnet_client_input_validation():
    """Test TelnetClientInput model validation."""
    # Valid input
    valid_input = TelnetClientInput(host="localhost", port=23, commands=["test"])
    assert valid_input.host == "localhost"
    assert valid_input.port == 23
    assert len(valid_input.commands) == 1

    # Invalid input - missing required fields
    with pytest.raises(Exception):  # Pydantic ValidationError
        TelnetClientInput(host="localhost")  # type: ignore


def test_command_response_model():
    """Test CommandResponse model."""
    response = CommandResponse(command="test", response="output")
    assert response.command == "test"
    assert response.response == "output"


def test_telnet_client_output_model():
    """Test TelnetClientOutput model."""
    output = TelnetClientOutput(
        host="localhost",
        port=23,
        initial_banner="Welcome",
        responses=[CommandResponse(command="test", response="output")],
        session_id="session123",
        session_active=True,
    )
    assert output.host == "localhost"
    assert output.session_active is True
    assert len(output.responses) == 1


def test_session_info_model():
    """Test SessionInfo model."""
    info = SessionInfo(
        session_id="test123",
        host="localhost",
        port=23,
        created_at=1000.0,
        age_seconds=100.5,
    )
    assert info.session_id == "test123"
    assert info.age_seconds == 100.5


def test_session_list_response_model():
    """Test SessionListResponse model."""
    response = SessionListResponse(
        active_sessions=1,
        sessions={
            "test": SessionInfo(
                session_id="test",
                host="localhost",
                port=23,
                created_at=1000.0,
                age_seconds=100.0,
            )
        },
    )
    assert response.active_sessions == 1
    assert "test" in response.sessions


def test_session_close_response_model():
    """Test SessionCloseResponse model."""
    response = SessionCloseResponse(success=True, message="Closed")
    assert response.success is True
    assert response.message == "Closed"


# ============================================================================
# Constants Tests
# ============================================================================


def test_telnet_command_constants():
    """Test TelnetCommand enum values."""
    assert TelnetCommand.IAC.value == bytes([255])
    assert TelnetCommand.DO.value == bytes([253])
    assert TelnetCommand.DONT.value == bytes([254])
    assert TelnetCommand.WILL.value == bytes([251])
    assert TelnetCommand.WONT.value == bytes([252])


def test_telnet_defaults():
    """Test TelnetDefaults class."""
    assert TelnetDefaults.CONNECTION_TIMEOUT == 10
    assert TelnetDefaults.INITIAL_BANNER_WAIT == 2.0
    assert TelnetDefaults.COMMAND_DELAY == 1.0
    assert TelnetDefaults.RESPONSE_WAIT == 1.5
    assert TelnetDefaults.READ_TIMEOUT == 5


# ============================================================================
# Session Store Tests
# ============================================================================


@pytest.mark.asyncio
async def test_session_store_operations(session_store):
    """Test session store CRUD operations."""
    fake_tn = FakeTelnet()
    session = TelnetSession(
        telnet=fake_tn,
        host="localhost",
        port=23,
        created_at=time.time(),
        session_id="test123",
    )

    # Store
    await session_store.store(session)
    assert len(session_store._sessions) == 1

    # Get
    retrieved = await session_store.get("test123")
    assert retrieved is not None
    assert retrieved.session_id == "test123"

    # List
    all_sessions = await session_store.list_all()
    assert len(all_sessions) == 1

    # Delete
    await session_store.delete("test123")
    assert len(session_store._sessions) == 0


@pytest.mark.asyncio
async def test_session_store_delete_nonexistent(session_store):
    """Test deleting a non-existent session doesn't raise error."""
    await session_store.delete("nonexistent")  # Should not raise


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_create_negotiation_callback():
    """Test negotiation callback creation."""
    callback = _create_negotiation_callback()
    assert callable(callback)

    # Mock socket
    mock_sock = MagicMock()

    # Test DO command
    callback(mock_sock, TelnetCommand.DO.value, b"\x01")
    mock_sock.sendall.assert_called()

    # Test WILL command
    callback(mock_sock, TelnetCommand.WILL.value, b"\x01")
    assert mock_sock.sendall.call_count >= 2


def test_strip_command_echo():
    """Test command echo stripping."""
    # Test exact match
    assert _strip_command_echo("test\r\noutput", "test") == "\r\noutput"

    # Test CRLF variant
    assert _strip_command_echo("test\r\n\r\noutput", "test") == "\r\n\r\noutput"

    # Test no match
    assert _strip_command_echo("output", "test") == "output"

    # Test partial match in middle
    result = _strip_command_echo("prefix test suffix", "test")
    assert "test" not in result or len(result) < len("prefix test suffix")


@pytest.mark.asyncio
async def test_connect_telnet(fake_telnet):
    """Test telnet connection establishment."""
    tn, banner = await _connect_telnet("localhost", 23)

    assert tn is not None
    assert isinstance(banner, str)
    assert "FakeTelnet" in banner


@pytest.mark.asyncio
async def test_connect_telnet_failure(monkeypatch):
    """Test telnet connection failure handling."""

    class FailingTelnet:
        def set_option_negotiation_callback(self, callback):
            pass

        def open(self, host, port, timeout):
            raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr(telnetlib, "Telnet", lambda: FailingTelnet())

    with pytest.raises(RuntimeError) as exc_info:
        await _connect_telnet("localhost", 23)

    assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_command(fake_telnet):
    """Test command execution."""
    tn = FakeTelnet()
    tn.open("localhost", 23, 10)

    response = await _execute_command(
        tn=tn, command="test", command_delay=0.1, response_wait=0.1, strip_echo=True
    )

    assert isinstance(response, CommandResponse)
    assert response.command == "test"
    assert len(response.response) > 0


# ============================================================================
# Integration Tests - Main Tool Functions
# ============================================================================


@pytest.mark.asyncio
async def test_telnet_client_tool_basic(fake_telnet):
    """Test basic telnet client tool functionality."""
    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["ls", "pwd"],
        command_delay=0.1,
        response_wait=0.1,
    )

    assert isinstance(result, TelnetClientOutput)
    assert result.host == "localhost"
    assert result.port == 23
    assert len(result.responses) == 2
    assert result.session_active is True
    assert "FakeTelnet" in result.initial_banner


@pytest.mark.asyncio
async def test_telnet_client_tool_invalid_input(fake_telnet):
    """Test telnet client tool with invalid input."""
    with pytest.raises(ValueError) as exc_info:
        await telnet_client_tool(
            host="localhost",
            port="invalid",  # type: ignore
            commands=["test"],
        )

    assert "Invalid input" in str(exc_info.value)


@pytest.mark.asyncio
async def test_telnet_client_tool_session_reuse(fake_telnet):
    """Test session reuse across multiple calls."""
    # First call
    result1 = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["cmd1"],
        command_delay=0.1,
        response_wait=0.1,
    )
    session_id = result1.session_id

    # Second call with same session
    result2 = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["cmd2"],
        telnet_session_id=session_id,
        command_delay=0.1,
        response_wait=0.1,
    )

    assert result2.session_id == session_id
    assert result2.initial_banner == ""  # No banner for reused session
    assert result2.session_active is True


@pytest.mark.asyncio
async def test_telnet_client_tool_auto_close(fake_telnet):
    """Test automatic session closing."""
    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["test"],
        close_session=True,
        command_delay=0.1,
        response_wait=0.1,
    )

    assert result.session_active is False


@pytest.mark.asyncio
async def test_telnet_client_tool_echo_stripping(fake_telnet):
    """Test command echo stripping."""
    # With stripping enabled
    result_with = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["echo_test"],
        strip_command_echo=True,
        command_delay=0.1,
        response_wait=0.1,
    )

    # With stripping disabled
    _session_store._sessions.clear()
    result_without = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["echo_test"],
        strip_command_echo=False,
        command_delay=0.1,
        response_wait=0.1,
    )

    # Response without stripping should be different
    assert result_with.responses[0].response != result_without.responses[0].response


@pytest.mark.asyncio
async def test_telnet_close_session_tool(fake_telnet):
    """Test session closing tool."""
    # Create a session
    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["test"],
        command_delay=0.1,
        response_wait=0.1,
    )
    session_id = result.session_id

    # Close it
    close_result = await telnet_close_session(session_id)

    assert isinstance(close_result, SessionCloseResponse)
    assert close_result.success is True
    assert session_id in close_result.message


@pytest.mark.asyncio
async def test_telnet_list_sessions_tool(fake_telnet):
    """Test session listing tool."""
    # Start with no sessions
    result1 = await telnet_list_sessions()
    assert result1.active_sessions == 0

    # Create a session
    client_result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["test"],
        command_delay=0.1,
        response_wait=0.1,
    )

    # List sessions
    result2 = await telnet_list_sessions()
    assert result2.active_sessions == 1
    assert client_result.session_id in result2.sessions

    # Verify session info
    session_info = result2.sessions[client_result.session_id]
    assert isinstance(session_info, SessionInfo)
    assert session_info.host == "localhost"
    assert session_info.port == 23


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_telnet_client_empty_commands(fake_telnet):
    """Test handling of empty command list."""
    result = await telnet_client_tool(
        host="localhost", port=23, commands=[], command_delay=0.1, response_wait=0.1
    )

    assert len(result.responses) == 0
    assert result.session_active is True


@pytest.mark.asyncio
async def test_telnet_client_many_commands(fake_telnet):
    """Test handling of many commands."""
    commands = [f"cmd{i}" for i in range(10)]

    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=commands,
        command_delay=0.01,
        response_wait=0.01,
    )

    assert len(result.responses) == 10
    for i, response in enumerate(result.responses):
        assert response.command == f"cmd{i}"


@pytest.mark.asyncio
async def test_telnet_client_custom_timeouts(fake_telnet):
    """Test custom timeout parameters."""
    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["test"],
        read_timeout=1,
        command_delay=0.05,
        response_wait=0.05,
    )

    assert result.session_active is True


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_telnet_client_timing(fake_telnet):
    """Test that delays are respected."""
    start_time = time.time()

    await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["cmd1", "cmd2"],
        command_delay=0.2,
        response_wait=0.1,
    )

    elapsed = time.time() - start_time

    # Should take at least (command_delay + response_wait) * 2 commands
    # Plus initial banner wait, but we use shorter values in tests
    assert elapsed >= 0.4  # (0.2 + 0.1) * 2 - some tolerance


# ============================================================================
# Cleanup Tests
# ============================================================================


@pytest.mark.asyncio
async def test_session_cleanup_on_close(fake_telnet):
    """Test that closing a session cleans up resources."""
    result = await telnet_client_tool(
        host="localhost",
        port=23,
        commands=["test"],
        command_delay=0.1,
        response_wait=0.1,
    )
    session_id = result.session_id

    # Verify session exists
    sessions = await telnet_list_sessions()
    assert session_id in sessions.sessions

    # Close session
    await telnet_close_session(session_id)

    # Verify session is gone
    sessions = await telnet_list_sessions()
    assert session_id not in sessions.sessions
