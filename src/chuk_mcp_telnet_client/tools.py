import telnetlib
import time
from typing import List, Optional, Dict
from pydantic import ValidationError

# Use the runtime's tool decorator instead of a local one
from chuk_mcp_runtime.common.mcp_tool_decorator import mcp_tool

# Import our models using absolute imports
from chuk_mcp_telnet_client.models import TelnetClientInput, TelnetClientOutput, CommandResponse
from chuk_mcp_runtime.common.errors import ChukMcpRuntimeError

# Telnet IAC / negotiation constants
IAC  = bytes([255])  # Interpret As Command
DONT = bytes([254])
DO   = bytes([253])
WONT = bytes([252])
WILL = bytes([251])

# Global session store
TELNET_SESSIONS: Dict[str, dict] = {}

@mcp_tool(name="telnet_client", description="Connect to a Telnet server, run commands, and return output.")
def telnet_client_tool(
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
    
    Args:
        host: Host or IP to connect to
        port: Port number
        commands: List of commands to send
        session_id: Optional session ID for persistent connections
        close_session: Whether to close the session after commands
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
    
    session = TELNET_SESSIONS.get(session_id)
    tn = None
    initial_data = b""

    if session:
        tn = session.get("telnet")
        if not tn:
            raise ChukMcpRuntimeError(f"Session {session_id} exists but telnet connection is invalid")
    else:
        tn = telnetlib.Telnet()

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
        time.sleep(2)  # Give server time to send welcome message
        initial_data = tn.read_very_eager()
        
        # If nothing received, try to read some data
        if not initial_data:
            initial_data = tn.read_some()
        
        TELNET_SESSIONS[session_id] = {
            "telnet": tn,
            "host": validated_input.host,
            "port": validated_input.port,
            "created_at": time.time()
        }

    initial_banner = initial_data.decode("utf-8", errors="ignore")
    responses = []
    
    for cmd in validated_input.commands:
        cmd_bytes = cmd.encode("utf-8") + b"\r\n"  # Use both CR and LF for maximum compatibility
        tn.write(cmd_bytes)
        
        # Give the server time to process the command
        time.sleep(command_delay)
        
        # Read response using a combination of techniques to ensure we get complete data
        data = b""
        
        # First try to read any immediately available data
        initial_chunk = tn.read_very_eager()
        if initial_chunk:
            data += initial_chunk
        
        # Wait a bit more for additional data to arrive
        time.sleep(response_wait)
        
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

    if close_session and session_id in TELNET_SESSIONS:
        tn.close()
        del TELNET_SESSIONS[session_id]

    output_model = TelnetClientOutput(
        host=validated_input.host,
        port=validated_input.port,
        initial_banner=initial_banner,
        responses=responses,
        session_id=session_id,
        session_active=session_id in TELNET_SESSIONS
    )

    return output_model.model_dump()

# Add a tool for closing specific sessions
@mcp_tool(name="telnet_close_session", description="Close a specific Telnet session.")
def telnet_close_session(session_id: str) -> dict:
    """
    Close a specific Telnet session by ID.

    :param session_id: The session ID to close.
    :return: Status of the operation.
    """
    if session_id in TELNET_SESSIONS:
        try:
            TELNET_SESSIONS[session_id]["telnet"].close()
        except:
            pass  # Best effort to close
        del TELNET_SESSIONS[session_id]
        return {"success": True, "message": f"Session {session_id} closed"}
    else:
        return {"success": False, "message": f"Session {session_id} not found"}

# Add a tool for listing active sessions
@mcp_tool(name="telnet_list_sessions", description="List all active Telnet sessions.")
def telnet_list_sessions() -> dict:
    """
    List all active Telnet sessions.

    :return: Dict with session information.
    """
    sessions = {}
    for session_id, session_data in TELNET_SESSIONS.items():
        sessions[session_id] = {
            "host": session_data["host"],
            "port": session_data["port"],
            "created_at": session_data["created_at"],
            "age_seconds": time.time() - session_data["created_at"]
        }
    
    return {
        "active_sessions": len(sessions),
        "sessions": sessions
    }