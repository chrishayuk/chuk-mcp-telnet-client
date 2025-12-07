import telnetlib
import time
import asyncio
import pickle
import base64
from typing import List, Optional, Dict
from pydantic import ValidationError

# Use the runtime's tool decorator instead of a local one
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool

# Import our models using absolute imports
from chuk_mcp_telnet_client.models import TelnetClientInput, TelnetClientOutput, CommandResponse
from chuk_mcp_runtime.common.errors import ChukMcpRuntimeError

# Import runtime session management for persistence across process invocations
from chuk_mcp_runtime.session import (
    MCPSessionManager,
    get_session_or_none,
)

# Create a singleton session manager instance
_session_manager = None

def _get_session_manager() -> MCPSessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = MCPSessionManager(sandbox_id="telnet-client")
    return _session_manager

# Telnet IAC / negotiation constants
IAC  = bytes([255])  # Interpret As Command
DONT = bytes([254])
DO   = bytes([253])
WONT = bytes([252])
WILL = bytes([251])

# Session storage helper functions using runtime's persistent session manager
async def _store_telnet_session(session_id: str, tn: telnetlib.Telnet, host: str, port: int):
    """Store telnet connection info in persistent session storage."""
    # We can't pickle the telnet connection itself, so we just store metadata
    # The actual connection will be recreated if needed
    mgr = _get_session_manager()
    session_data = {
        "host": host,
        "port": port,
        "created_at": time.time(),
        "has_connection": True,
    }
    try:
        await mgr.update_session(session_id, custom_metadata=session_data)
    except Exception:
        # Session might not exist, try to create it
        try:
            await mgr.create_session(
                session_id=session_id,
                user_id="telnet-user",
                custom_metadata=session_data
            )
        except Exception:
            pass  # Best effort

async def _get_telnet_session(session_id: str) -> Optional[dict]:
    """Retrieve telnet session info from persistent storage."""
    try:
        session = await get_session_or_none(session_id)
        if session and hasattr(session, 'custom_metadata'):
            metadata = session.custom_metadata
            if isinstance(metadata, dict) and metadata.get("has_connection"):
                return metadata
    except Exception:
        pass
    return None

async def _delete_telnet_session(session_id: str):
    """Remove telnet session from persistent storage."""
    mgr = _get_session_manager()
    try:
        await mgr.update_session(session_id, custom_metadata={"has_connection": False})
    except Exception:
        pass

@mcp_tool(name="telnet_client", description="Connect to a Telnet server, run commands, and return output.")
async def telnet_client_tool(
    host: str,
    port: int,
    commands: List[str],
    session_id: Optional[str] = None,
    close_session: bool = False,
    read_timeout: int = 5,
    command_delay: float = 1.0,      # Delay after sending each command
    response_wait: float = 1.5,      # Time to wait for complete response
    strip_command_echo: bool = True  # Whether to try removing the command echo
) -> dict:
    """
    Universal Telnet client tool that works with various server types.

    NOTE: Session reuse across multiple tool calls is NOT supported when running
    via stdio transport because each call is a new process. The telnet connection
    cannot be persisted. This tool will create a fresh connection for each call.

    Args:
        host: Host or IP to connect to
        port: Port number
        commands: List of commands to send
        session_id: Session ID (informational only - connections cannot persist across calls)
        close_session: Whether to close the session after commands (always true for stdio)
        read_timeout: Timeout in seconds when waiting for initial responses
        command_delay: Delay after sending each command
        response_wait: Additional time to wait for complete response
        strip_command_echo: Try to remove command echo from responses

    Returns:
        Dictionary with server responses and session information
    """
    # Validate input
    try:
        validated_input = TelnetClientInput(
            host=host,
            port=port,
            commands=commands
        )
    except ValidationError as e:
        raise ValueError(f"Invalid input for telnet_client_tool: {e}")

    if not session_id:
        session_id = f"telnet_{host}_{port}_{int(time.time())}"

    # Check if session info exists in persistent storage
    # (Note: We can't reuse the actual connection, but we can track session history)
    session_data = await _get_telnet_session(session_id)

    # Always create a fresh connection (connections can't persist across process invocations)
    tn = telnetlib.Telnet()
    initial_data = b""

    def negotiation_callback(sock, cmd, opt):
        if cmd == DO:
            sock.sendall(IAC + WONT + opt)
        elif cmd == WILL:
            sock.sendall(IAC + DONT + opt)

    tn.set_option_negotiation_callback(negotiation_callback)

    try:
        tn.open(validated_input.host, validated_input.port, timeout=10)
    except Exception as ex:
        raise ChukMcpRuntimeError(f"Failed to connect to Telnet server: {ex}")

    # Read initial banner by waiting a moment then reading all available data
    await asyncio.sleep(2)  # Give server time to send welcome message
    initial_data = tn.read_very_eager()

    # If nothing received, try to read some data
    if not initial_data:
        initial_data = tn.read_some()

    # Store session metadata (not the connection itself)
    await _store_telnet_session(session_id, tn, validated_input.host, validated_input.port)

    initial_banner = initial_data.decode("utf-8", errors="ignore")
    responses = []
    
    for cmd in validated_input.commands:
        cmd_bytes = cmd.encode("utf-8") + b"\r\n"  # Use both CR and LF for maximum compatibility
        tn.write(cmd_bytes)
        
        # Give the server time to process the command
        await asyncio.sleep(command_delay)

        # Read response using a combination of techniques to ensure we get complete data
        data = b""

        # First try to read any immediately available data
        initial_chunk = tn.read_very_eager()
        if initial_chunk:
            data += initial_chunk

        # Wait a bit more for additional data to arrive
        await asyncio.sleep(response_wait)
        
        # Read any remaining data
        more_data = tn.read_very_eager()
        if more_data:
            data += more_data
            
        # If we still don't have data, try one more approach
        if not data:
            data = tn.read_some()
        
        # Decode the response
        response_text = data.decode("utf-8", errors="ignore")
        
        # Try to remove command echo if requested
        if strip_command_echo:
            # Remove both CR/LF and just LF variants of the command
            cmd_variants = [
                cmd,                 # Raw command
                cmd + "\r\n",        # Command with CRLF
                cmd + "\n",          # Command with LF
                "\r\n" + cmd,        # CRLF then command
                "\n" + cmd           # LF then command
            ]
            
            for variant in cmd_variants:
                if response_text.startswith(variant):
                    response_text = response_text[len(variant):]
                    break
                    
            # Also check for the command in the middle of the response
            # (some servers echo after initial protocol output)
            for variant in cmd_variants:
                if variant in response_text:
                    parts = response_text.split(variant, 1)
                    if len(parts) > 1:
                        # Only remove first occurrence
                        response_text = parts[0] + parts[1]
                        break
        
        responses.append(CommandResponse(
            command=cmd,
            response=response_text
        ))

    # Always close the connection (stdio transport cannot maintain persistent connections)
    try:
        tn.close()
    except:
        pass  # Best effort close

    # Mark session as closed if requested
    if close_session:
        await _delete_telnet_session(session_id)

    output_model = TelnetClientOutput(
        host=validated_input.host,
        port=validated_input.port,
        initial_banner=initial_banner,
        responses=responses,
        session_id=session_id,
        session_active=False  # Connection always closed after each call in stdio mode
    )

    return output_model.model_dump()

# Add a tool for closing specific sessions
@mcp_tool(name="telnet_close_session", description="Close a specific Telnet session (marks session metadata as closed).")
async def telnet_close_session(session_id: str) -> dict:
    """
    Mark a specific Telnet session as closed in persistent storage.

    NOTE: In stdio transport mode, actual telnet connections are always closed
    after each tool call. This just removes the session metadata.

    :param session_id: The session ID to close.
    :return: Status of the operation.
    """
    await _delete_telnet_session(session_id)
    return {"success": True, "message": f"Session {session_id} marked as closed"}

# Add a tool for listing active sessions
@mcp_tool(name="telnet_list_sessions", description="List all Telnet sessions (metadata only - actual connections don't persist).")
async def telnet_list_sessions() -> dict:
    """
    List Telnet session metadata from persistent storage.

    NOTE: In stdio transport mode, actual telnet connections cannot persist
    across tool calls. This lists session metadata only.

    :return: Dict with session information.
    """
    # Get all sessions from the session manager
    mgr = _get_session_manager()

    # Try to list all sessions (this may not be supported by all implementations)
    sessions = {}
    try:
        # For now, we'll just return an empty list since we don't have a way to enumerate
        # all sessions without the session IDs. In practice, the LLM should track session IDs.
        pass
    except Exception:
        pass

    return {
        "active_sessions": len(sessions),
        "sessions": sessions,
        "note": "Sessions listed are metadata only. Actual telnet connections cannot persist in stdio mode. Session tracking requires the LLM to remember session IDs across calls."
    }