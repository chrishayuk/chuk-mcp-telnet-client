"""
Telnet client tools for MCP server.

Provides async telnet connectivity with session management.
"""

import asyncio
import logging
import telnetlib  # nosec B401 - telnet is the purpose of this MCP server
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from chuk_mcp_server import tool
from pydantic import BaseModel, ValidationError

from chuk_mcp_telnet_client.models import (
    CommandResponse,
    TelnetClientInput,
    TelnetClientOutput,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================


class TelnetCommand(bytes, Enum):
    """Telnet protocol command constants."""

    IAC = bytes([255])  # Interpret As Command
    DONT = bytes([254])  # Don't perform option
    DO = bytes([253])  # Do perform option
    WONT = bytes([252])  # Won't perform option
    WILL = bytes([251])  # Will perform option


class TelnetDefaults:
    """Default values for telnet operations."""

    CONNECTION_TIMEOUT: int = 10
    INITIAL_BANNER_WAIT: float = 2.0
    COMMAND_DELAY: float = 1.0
    RESPONSE_WAIT: float = 1.5
    READ_TIMEOUT: int = 5


# ============================================================================
# Session Models
# ============================================================================


@dataclass
class TelnetSession:
    """Represents an active telnet connection session."""

    telnet: telnetlib.Telnet
    host: str
    port: int
    created_at: float
    session_id: str


class SessionInfo(BaseModel):
    """Information about a telnet session."""

    session_id: str
    host: str
    port: int
    created_at: float
    age_seconds: float


class SessionListResponse(BaseModel):
    """Response for listing active sessions."""

    active_sessions: int
    sessions: dict[str, SessionInfo]
    note: str = (
        "Active connections shown. Sessions persist when using HTTP/SSE transport."
    )


class SessionCloseResponse(BaseModel):
    """Response for closing a session."""

    success: bool
    message: str


# ============================================================================
# Session Storage
# ============================================================================


class SessionStore:
    """In-memory storage for active telnet connections."""

    def __init__(self):
        self._sessions: dict[str, TelnetSession] = {}

    async def store(self, session: TelnetSession) -> None:
        """Store a telnet session."""
        self._sessions[session.session_id] = session

    async def get(self, session_id: str) -> Optional[TelnetSession]:
        """Retrieve a telnet session."""
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        """Delete a telnet session and close connection."""
        session = self._sessions.get(session_id)
        if session:
            try:
                await asyncio.to_thread(session.telnet.close)
            except Exception as e:
                logger.warning(f"Error closing telnet connection: {e}")
            del self._sessions[session_id]

    async def list_all(self) -> list[TelnetSession]:
        """List all active sessions."""
        return list(self._sessions.values())


# Global session store instance
_session_store = SessionStore()


# ============================================================================
# Telnet Operations
# ============================================================================


def _create_negotiation_callback():
    """Create a telnet option negotiation callback."""

    def callback(sock, cmd, opt):
        """Handle telnet option negotiation."""
        if cmd == TelnetCommand.DO.value:
            sock.sendall(TelnetCommand.IAC.value + TelnetCommand.WONT.value + opt)
        elif cmd == TelnetCommand.WILL.value:
            sock.sendall(TelnetCommand.IAC.value + TelnetCommand.DONT.value + opt)

    return callback


async def _connect_telnet(host: str, port: int) -> tuple[telnetlib.Telnet, str]:
    """
    Establish a new telnet connection.

    Args:
        host: Hostname or IP address
        port: Port number

    Returns:
        Tuple of (telnet connection, initial banner)

    Raises:
        RuntimeError: If connection fails
    """
    tn = telnetlib.Telnet()  # nosec B312 - telnet is the purpose of this MCP server
    tn.set_option_negotiation_callback(_create_negotiation_callback())

    try:
        # Run blocking open() in thread pool
        await asyncio.to_thread(tn.open, host, port, TelnetDefaults.CONNECTION_TIMEOUT)
    except Exception as ex:
        raise RuntimeError(f"Failed to connect to Telnet server at {host}:{port}: {ex}")

    # Read initial banner
    await asyncio.sleep(TelnetDefaults.INITIAL_BANNER_WAIT)

    # Run blocking read operations in thread pool
    initial_data = await asyncio.to_thread(tn.read_very_eager)

    # Try to read some data if nothing received
    if not initial_data:
        initial_data = await asyncio.to_thread(tn.read_some)

    initial_banner = initial_data.decode("utf-8", errors="ignore")
    return tn, initial_banner


def _strip_command_echo(response: str, command: str) -> str:
    """
    Remove command echo from telnet response.

    Args:
        response: Raw telnet response
        command: Command that was sent

    Returns:
        Response with command echo removed
    """
    # Try different variants of command echo
    variants = [
        command,
        command + "\r\n",
        command + "\n",
        "\r\n" + command,
        "\n" + command,
    ]

    for variant in variants:
        if response.startswith(variant):
            return response[len(variant) :]

    # Check for command in the middle of response
    for variant in variants:
        if variant in response:
            parts = response.split(variant, 1)
            if len(parts) > 1:
                return parts[0] + parts[1]

    return response


async def _execute_command(
    tn: telnetlib.Telnet,
    command: str,
    command_delay: float,
    response_wait: float,
    strip_echo: bool,
    raw_input: bool = False,
) -> CommandResponse:
    """
    Execute a single command on the telnet connection.

    Args:
        tn: Active telnet connection
        command: Command to execute
        command_delay: Delay after sending command
        response_wait: Time to wait for complete response
        strip_echo: Whether to strip command echo
        raw_input: If True, send command as-is without adding CRLF (for interactive apps)

    Returns:
        CommandResponse with command and its response
    """
    # Send command with or without CRLF depending on mode
    if raw_input:
        cmd_bytes = command.encode("utf-8")
    else:
        cmd_bytes = command.encode("utf-8") + b"\r\n"
    await asyncio.to_thread(tn.write, cmd_bytes)

    # Give server time to process
    await asyncio.sleep(command_delay)

    # Read response in chunks
    data = b""

    # Read immediately available data
    initial_chunk = await asyncio.to_thread(tn.read_very_eager)
    if initial_chunk:
        data += initial_chunk

    # Wait for additional data
    await asyncio.sleep(response_wait)

    # Read remaining data
    more_data = await asyncio.to_thread(tn.read_very_eager)
    if more_data:
        data += more_data

    # If no data yet, try a timed read with timeout
    # Use read_until with a short timeout instead of blocking read_some
    if not data:
        try:
            # Try to read with a 1 second timeout instead of blocking indefinitely
            data = await asyncio.wait_for(
                asyncio.to_thread(tn.read_very_eager), timeout=1.0
            )
        except asyncio.TimeoutError:
            # No data available, that's okay for interactive sessions
            pass

    # Decode response
    response_text = data.decode("utf-8", errors="ignore")

    # Strip command echo if requested
    if strip_echo:
        response_text = _strip_command_echo(response_text, command)

    return CommandResponse(command=command, response=response_text)


# ============================================================================
# MCP Tools
# ============================================================================


@tool(
    name="telnet_client",
    description="Connect to a Telnet server, run commands, and return output. Best for line-based command shells. For interactive full-screen apps (games, editors), use raw_input=True and send single-key commands (e.g., 'q' to quit, not 'quit').",
)
async def telnet_client_tool(
    host: str,
    port: int,
    commands: list[str],
    telnet_session_id: Optional[str] = None,
    close_session: bool = False,
    read_timeout: int = TelnetDefaults.READ_TIMEOUT,
    command_delay: float = TelnetDefaults.COMMAND_DELAY,
    response_wait: float = TelnetDefaults.RESPONSE_WAIT,
    strip_command_echo: bool = True,
    raw_input: bool = False,
) -> TelnetClientOutput:
    """
    Universal Telnet client tool that works with various server types.

    Supports session persistence when running via HTTP/SSE transport, allowing
    you to maintain an open telnet connection across multiple tool calls.

    IMPORTANT - Interactive Applications:
    - Line-based shells (default): Send commands like ['ls', 'pwd'] with raw_input=False
    - Full-screen interactive apps (games, vim, sudoku):
      * To just VIEW the state: Send ['sudoku'] with close_session=True (force-close after)
      * To interact: Must use TWO separate calls:
        1. Start: telnet_client(['sudoku'], close_session=False) -> get session_id
        2. Quit: telnet_client(['q'], session_id=..., raw_input=True, close_session=True)
      * Single-key commands only with raw_input=True: 'q' to quit (not 'quit')
      * These apps use cursor positioning and expect raw keystrokes
    - Programmatic interaction with interactive apps is VERY LIMITED
      * You can start them, view initial state, and quit them
      * You CANNOT easily solve puzzles or edit files through this interface
      * RECOMMENDED: Parse initial state, then solve locally with solver tools
      * Do NOT try to send move-by-move commands to interactive games

    Args:
        host: Host or IP to connect to
        port: Port number
        commands: List of commands to send (use single chars like 'q' for interactive apps)
        telnet_session_id: Telnet session ID for reusing existing connections (HTTP/SSE only)
        close_session: Whether to close the telnet session after commands
        read_timeout: Timeout in seconds when waiting for initial responses
        command_delay: Delay after sending each command (default: 1.0s)
        response_wait: Additional time to wait for complete response (default: 1.5s)
        strip_command_echo: Try to remove command echo from responses (default: True)
        raw_input: Send input as raw bytes without CRLF line endings (use True for
                  interactive games/editors that expect single keystrokes)

    Returns:
        TelnetClientOutput with server responses and session information

    Raises:
        ValueError: If input validation fails
        RuntimeError: If connection fails
    """
    # Validate input
    try:
        validated_input = TelnetClientInput(host=host, port=port, commands=commands)
    except ValidationError as e:
        raise ValueError(f"Invalid input for telnet_client_tool: {e}")

    # Generate session ID if not provided
    if not telnet_session_id:
        telnet_session_id = f"telnet_{host}_{port}_{int(time.time())}"

    # Try to retrieve existing session
    existing_session = await _session_store.get(telnet_session_id)

    if existing_session:
        # Reuse existing connection
        tn = existing_session.telnet
        initial_banner = ""  # No banner for existing sessions

        # Verify the connection is still alive
        try:
            # Quick check - try to read any pending data with very short timeout
            await asyncio.wait_for(asyncio.to_thread(tn.read_very_eager), timeout=0.1)
        except asyncio.TimeoutError:
            # No data available - connection is idle, which is fine
            pass
        except (OSError, EOFError):
            # Connection is dead - remove it and create a new one
            logger.warning(
                f"Session {telnet_session_id} connection is dead, creating new connection"
            )
            await _session_store.delete(telnet_session_id)
            existing_session = None  # Fall through to create new connection

    if not existing_session:
        # Create new connection
        tn, initial_banner = await _connect_telnet(
            validated_input.host, validated_input.port
        )

        # Store the new session
        new_session = TelnetSession(
            telnet=tn,
            host=validated_input.host,
            port=validated_input.port,
            created_at=time.time(),
            session_id=telnet_session_id,
        )
        await _session_store.store(new_session)

    # Execute commands
    responses: list[CommandResponse] = []
    for cmd in validated_input.commands:
        try:
            response = await _execute_command(
                tn=tn,
                command=cmd,
                command_delay=command_delay,
                response_wait=response_wait,
                strip_echo=strip_command_echo,
                raw_input=raw_input,
            )
            responses.append(response)
        except (OSError, EOFError) as e:
            # Connection was closed (likely by exit/quit command or server disconnect)
            # This is expected behavior, not an error - just stop processing commands
            logger.info(f"Connection closed while executing '{cmd}': {e}")
            # Add a response indicating connection was closed
            responses.append(
                CommandResponse(command=cmd, response="(connection closed by server)")
            )
            break  # Stop processing remaining commands
        except Exception as e:
            # Unexpected error - log and re-raise with context
            logger.error(f"Failed to execute command '{cmd}': {e}")
            raise RuntimeError(f"Failed to execute command '{cmd}': {e}") from e

    # Close connection if requested
    if close_session:
        await _session_store.delete(telnet_session_id)

    # Check if session is still active
    session_active = await _session_store.get(telnet_session_id) is not None

    # Debug logging
    logger.info(
        f"Session check: telnet_session_id={telnet_session_id}, active={session_active}"
    )

    return TelnetClientOutput(
        host=validated_input.host,
        port=validated_input.port,
        initial_banner=initial_banner,
        responses=responses,
        session_id=telnet_session_id,
        session_active=session_active,
    )


@tool(name="telnet_close_session", description="Close a specific Telnet session.")
async def telnet_close_session(session_id: str) -> SessionCloseResponse:
    """
    Close a specific Telnet session.

    NOTE: In stdio transport mode, actual telnet connections are always closed
    after each tool call. This just removes the session metadata.

    Args:
        session_id: The session ID to close

    Returns:
        SessionCloseResponse with operation status
    """
    await _session_store.delete(session_id)
    return SessionCloseResponse(
        success=True, message=f"Session {session_id} closed successfully"
    )


@tool(
    name="telnet_list_sessions",
    description="List all active Telnet sessions with connection details.",
)
async def telnet_list_sessions() -> SessionListResponse:
    """
    List all active Telnet sessions.

    In HTTP mode, this shows truly active connections.
    In stdio mode, this will always be empty.

    Returns:
        SessionListResponse with all active sessions
    """
    sessions = await _session_store.list_all()
    current_time = time.time()

    session_info_dict: dict[str, SessionInfo] = {}
    for session in sessions:
        session_info_dict[session.session_id] = SessionInfo(
            session_id=session.session_id,
            host=session.host,
            port=session.port,
            created_at=session.created_at,
            age_seconds=current_time - session.created_at,
        )

    return SessionListResponse(
        active_sessions=len(session_info_dict), sessions=session_info_dict
    )
