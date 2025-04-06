# tests/test_telnet_client.py

import time
import pytest
import telnetlib

from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_telnet_client.models import TelnetClientOutput, CommandResponse
from chuk_mcp_telnet_client import (
    telnet_client_tool,
    telnet_close_session,
    telnet_list_sessions,
    TELNET_SESSIONS,
)
from chuk_mcp_runtime.common.errors import ChukMcpRuntimeError

# Define a fake Telnet class to simulate a Telnet server.
class FakeTelnet:
    def __init__(self):
        self.commands_sent = []
        self.closed = False
        self._data_available = True  # Flag to simulate data availability

    def set_option_negotiation_callback(self, callback):
        self.callback = callback

    def open(self, host, port, timeout):
        # Save connection info if needed.
        self.host = host
        self.port = port

    def read_until(self, expected, timeout):
        # For the initial read (banner) return a fake banner.
        if not self.commands_sent:
            return b"FakeBanner\r\n"
        # For subsequent calls, return a fake response based on the last command.
        return f"Response to {self.commands_sent[-1]}\r\n".encode("utf-8")

    def write(self, data):
        # Decode and clean up the command
        cmd = data.decode("utf-8").strip()
        if cmd.endswith("\r"):
            cmd = cmd[:-1]
        if cmd.endswith("\n"):
            cmd = cmd[:-1]
        self.commands_sent.append(cmd)

    def read_very_eager(self):
        # This is the primary method used by the new client
        if not self.commands_sent:
            return b"FakeBanner\r\n"
        
        # Return a response including the command echo
        last_cmd = self.commands_sent[-1]
        return f"{last_cmd}\r\nResponse to {last_cmd}\r\n".encode("utf-8")

    def read_some(self):
        # Fallback method used by the client
        if not self.commands_sent:
            return b"FakeBanner\r\n"
        
        last_cmd = self.commands_sent[-1]
        return f"Response to {last_cmd}\r\n".encode("utf-8")

    def sock_avail(self):
        # Always return False to indicate no more data
        return False

    def close(self):
        self.closed = True


# Fixture to monkeypatch telnetlib.Telnet with our FakeTelnet.
@pytest.fixture
def fake_telnet(monkeypatch):
    monkeypatch.setattr(telnetlib, "Telnet", lambda: FakeTelnet())
    # Clear any pre-existing sessions before each test.
    TELNET_SESSIONS.clear()
    yield
    TELNET_SESSIONS.clear()


def test_telnet_client_tool_valid(fake_telnet):
    """
    Test that telnet_client_tool returns the expected dict when given valid input.
    It should include the initial banner and a proper response for each command.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1", "cmd2"]

    # Use minimal delays for faster tests
    result = telnet_client_tool(
        host, port, commands, 
        command_delay=0.1, 
        response_wait=0.1
    )
    
    assert isinstance(result, dict)
    # Check for expected top-level keys.
    for key in ("host", "port", "initial_banner", "responses", "session_id", "session_active"):
        assert key in result, f"Missing key '{key}' in result"

    # The initial banner should come from our FakeTelnet.
    assert "FakeBanner" in result["initial_banner"]

    # Check that the responses list has one response per command.
    assert len(result["responses"]) == len(commands)
    for cmd, response in zip(commands, result["responses"]):
        assert response["command"] == cmd
        # Our FakeTelnet returns "Response to <cmd>" as part of the response.
        assert f"Response to {cmd}" in response["response"]


def test_telnet_client_tool_invalid_input(fake_telnet):
    """
    Test that passing an invalid input (e.g. wrong port type) raises a ValueError,
    as the input validation using Pydantic should fail.
    """
    # Use an invalid port (string instead of int)
    with pytest.raises(ValueError):
        telnet_client_tool("127.0.0.1", "invalid_port", ["cmd"])


def test_telnet_client_tool_connection_failure(monkeypatch):
    """
    Test that if telnetlib.Telnet.open fails, the tool raises a ChukMcpRuntimeError.
    """
    class FailingTelnet:
        def __init__(self):
            pass
        
        def set_option_negotiation_callback(self, callback):
            pass
        
        def open(self, host, port, timeout):
            raise Exception("Connection failed")

    monkeypatch.setattr(telnetlib, "Telnet", lambda: FailingTelnet())
    TELNET_SESSIONS.clear()

    with pytest.raises(ChukMcpRuntimeError) as excinfo:
        telnet_client_tool("127.0.0.1", 8023, ["cmd"])
    assert "Failed to connect" in str(excinfo.value)

# Just the fixed test

def test_telnet_client_strip_command_echo(fake_telnet):
    """
    Test that the telnet client properly strips command echo from responses
    when strip_command_echo is enabled.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["echo_test"]

    # With echo stripping enabled (default)
    result_with_strip = telnet_client_tool(
        host, port, commands,
        command_delay=0.1, 
        response_wait=0.1
    )
    
    # We're still asserting the response contains the expected text
    assert "Response to echo_test" in result_with_strip["responses"][0]["response"]
    
    # With echo stripping disabled
    TELNET_SESSIONS.clear()  # Clear sessions for a fresh test
    result_without_strip = telnet_client_tool(
        host, port, commands, 
        strip_command_echo=False,
        command_delay=0.1, 
        response_wait=0.1
    )
    
    # The response with echo stripping disabled should be longer 
    # or contain more instances of the command
    stripped_length = len(result_with_strip["responses"][0]["response"])
    unstripped_length = len(result_without_strip["responses"][0]["response"])
    
    # Either the unstripped response should be longer, or it should 
    # contain command text that the stripped version doesn't
    assert (unstripped_length > stripped_length or 
            result_without_strip["responses"][0]["response"].count("echo_test") > 
            result_with_strip["responses"][0]["response"].count("echo_test")), \
           "Echo stripping doesn't appear to be working"
    
def test_telnet_client_read_timeout(fake_telnet):
    """
    Test that the telnet client respects the read_timeout parameter.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd"]

    # With a very short timeout
    start_time = time.time()
    result_short_timeout = telnet_client_tool(
        host, port, commands, 
        read_timeout=1, 
        command_delay=0.1, 
        response_wait=0.1
    )
    end_time = time.time()
    
    # The command should still succeed but take less time
    assert "Response to cmd" in result_short_timeout["responses"][0]["response"]
    assert end_time - start_time < 3, "Short timeout test took too long"

    # Clear sessions for a fresh test
    TELNET_SESSIONS.clear()

    # With a longer timeout
    start_time = time.time()
    result_long_timeout = telnet_client_tool(
        host, port, commands, 
        read_timeout=2, 
        command_delay=0.5, 
        response_wait=0.5
    )
    end_time = time.time()
    
    # The command should succeed and take more time due to longer delays
    assert "Response to cmd" in result_long_timeout["responses"][0]["response"]
    assert end_time - start_time > 0.5, "Long timeout test was too quick"


def test_telnet_close_session(fake_telnet):
    """
    Test that telnet_close_session successfully closes an existing session.
    A subsequent call to close the same session should report that it no longer exists.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1"]

    # Open a new session with minimal delays
    result = telnet_client_tool(
        host, port, commands,
        command_delay=0.1, 
        response_wait=0.1
    )
    session_id = result["session_id"]

    # Close the session.
    close_result = telnet_close_session(session_id)
    assert close_result["success"] is True

    # Attempt to close the session again; should return not found.
    close_result2 = telnet_close_session(session_id)
    assert close_result2["success"] is False


def test_telnet_list_sessions(fake_telnet):
    """
    Test that telnet_list_sessions returns the correct number of active sessions
    and the session information is present.
    """
    # Start with no active sessions.
    sessions_before = telnet_list_sessions()
    initial_count = sessions_before["active_sessions"]

    # Open a new session with minimal delays
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1"]
    result = telnet_client_tool(
        host, port, commands,
        command_delay=0.1, 
        response_wait=0.1
    )

    # List sessions after opening a new one.
    sessions_after = telnet_list_sessions()
    assert sessions_after["active_sessions"] == initial_count + 1
    assert result["session_id"] in sessions_after["sessions"]


def test_telnet_client_persistent_session(fake_telnet):
    """
    Test that a session can be reused across multiple calls.
    """
    host = "127.0.0.1"
    port = 8023
    
    # First call - create a new session
    result1 = telnet_client_tool(
        host, port, ["cmd1"],
        command_delay=0.1, 
        response_wait=0.1
    )
    session_id = result1["session_id"]
    
    # Second call - reuse the session
    result2 = telnet_client_tool(
        host, port, ["cmd2"], 
        session_id=session_id,
        command_delay=0.1, 
        response_wait=0.1
    )
    
    # Verify the session is the same
    assert result2["session_id"] == session_id
    assert result2["session_active"] is True
    
    # Verify both commands were processed
    telnet_obj = TELNET_SESSIONS[session_id]["telnet"]
    assert "cmd1" in telnet_obj.commands_sent
    assert "cmd2" in telnet_obj.commands_sent


def test_telnet_client_auto_close_session(fake_telnet):
    """
    Test that setting close_session=True automatically closes the session after commands.
    """
    host = "127.0.0.1"
    port = 8023
    
    # Open and immediately close a session
    result = telnet_client_tool(
        host, port, ["cmd"], 
        close_session=True,
        command_delay=0.1, 
        response_wait=0.1
    )
    session_id = result["session_id"]
    
    # Verify the session is closed
    assert result["session_active"] is False
    assert session_id not in TELNET_SESSIONS


def test_telnet_client_command_delay(fake_telnet):
    """
    Test that the command_delay parameter affects the execution time.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1", "cmd2"]
    
    # With minimal delay
    start_time = time.time()
    telnet_client_tool(
        host, port, commands, 
        command_delay=0.1, 
        response_wait=0.1
    )
    short_delay_time = time.time() - start_time
    
    # Clear sessions for a fresh test
    TELNET_SESSIONS.clear()
    
    # With longer delay
    start_time = time.time()
    telnet_client_tool(
        host, port, commands, 
        command_delay=0.3, 
        response_wait=0.1
    )
    long_delay_time = time.time() - start_time
    
    # The longer delay should take more time
    assert long_delay_time > short_delay_time, "Longer command_delay should take more time"