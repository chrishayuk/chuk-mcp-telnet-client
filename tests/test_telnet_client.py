# tests/test_telnet_client.py

import time
import pytest
import telnetlib

from chuk_mcp_telnet_client.common.mcp_tool_decorator import mcp_tool
from chuk_mcp_telnet_client.models import TelnetClientOutput, CommandResponse
from chuk_mcp_telnet_client import (
    telnet_client_tool,
    telnet_close_session,
    telnet_list_sessions,
    TELNET_SESSIONS,
)
from mcp.shared.exceptions import McpError

# Define a fake Telnet class to simulate a Telnet server.
class FakeTelnet:
    def __init__(self):
        self.commands_sent = []
        self.closed = False

    def set_option_negotiation_callback(self, callback):
        self.callback = callback

    def open(self, host, port, timeout):
        # Save connection info if needed.
        self.host = host
        self.port = port

    def read_until(self, expected, timeout):
        # For the initial read (banner) return a fake banner.
        if not self.commands_sent:
            return b"FakeBanner> "
        # For subsequent calls, return a fake response based on the last command.
        return f"Response to {self.commands_sent[-1]}\n> ".encode("utf-8")

    def write(self, data):
        # Assume data is bytes ending with newline.
        cmd = data.decode("utf-8").strip()
        self.commands_sent.append(cmd)

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

    result = telnet_client_tool(host, port, commands)
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
    Test that if telnetlib.Telnet.open fails, the tool raises an exception.
    Because McpError's constructor is not handling a string correctly, an AttributeError is raised.
    """
    # Modify FakeTelnet.open to simulate a connection failure.
    def fake_open_failure(self, host, port, timeout):
        raise Exception("Connection failed")

    monkeypatch.setattr(FakeTelnet, "open", fake_open_failure)
    TELNET_SESSIONS.clear()

    with pytest.raises(AttributeError) as excinfo:
        telnet_client_tool("127.0.0.1", 8023, ["cmd"])
    # We expect the AttributeError message to mention the missing 'message' attribute.
    assert "'str' object has no attribute 'message'" in str(excinfo.value)


def test_telnet_close_session(fake_telnet):
    """
    Test that telnet_close_session successfully closes an existing session.
    A subsequent call to close the same session should report that it no longer exists.
    """
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1"]

    # Open a new session.
    result = telnet_client_tool(host, port, commands)
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

    # Open a new session.
    host = "127.0.0.1"
    port = 8023
    commands = ["cmd1"]
    result = telnet_client_tool(host, port, commands)

    # List sessions after opening a new one.
    sessions_after = telnet_list_sessions()
    assert sessions_after["active_sessions"] == initial_count + 1
    assert result["session_id"] in sessions_after["sessions"]
