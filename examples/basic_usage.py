#!/usr/bin/env python3
"""
Basic usage example for the Telnet Client MCP Server.

This example demonstrates how to use the telnet client tools programmatically.
"""

import asyncio
from chuk_mcp_telnet_client.tools import (
    telnet_client_tool,
    telnet_list_sessions,
    telnet_close_session,
)


async def main():
    """Run basic telnet client examples."""
    print("=" * 70)
    print("Telnet Client MCP Server - Basic Usage Examples")
    print("=" * 70)
    print()

    # Example 1: Simple telnet session
    print("Example 1: Simple telnet connection")
    print("-" * 70)

    try:
        result = await telnet_client_tool(
            host="towel.blinkenlights.nl",  # Star Wars telnet server
            port=23,
            commands=[""],  # Just connect and get banner
            command_delay=0.5,
            response_wait=1.0,
        )

        print(f"Connected to: {result.host}:{result.port}")
        print(f"Session ID: {result.session_id}")
        print(f"Banner: {result.initial_banner[:100]}...")  # First 100 chars
        print()

    except Exception as e:
        print(f"Error: {e}")
        print()

    # Example 2: Session reuse
    print("Example 2: Reusing a telnet session")
    print("-" * 70)

    try:
        # First connection
        result1 = await telnet_client_tool(
            host="localhost",
            port=23,
            commands=["echo 'First command'"],
            command_delay=0.1,
            response_wait=0.2,
        )

        session_id = result1.session_id
        print(f"Created session: {session_id}")
        print(f"Response: {result1.responses[0].response[:50]}...")

        # Reuse the session
        result2 = await telnet_client_tool(
            host="localhost",
            port=23,
            commands=["echo 'Second command'"],
            telnet_session_id=session_id,
            command_delay=0.1,
            response_wait=0.2,
        )

        print(f"Reused session: {result2.session_id}")
        print(f"Session active: {result2.session_active}")
        print()

    except Exception as e:
        print(f"Error (this is expected if no local telnet server): {e}")
        print()

    # Example 3: List active sessions
    print("Example 3: Listing active sessions")
    print("-" * 70)

    sessions = await telnet_list_sessions()
    print(f"Active sessions: {sessions.active_sessions}")

    for session_id, info in sessions.sessions.items():
        print(f"\nSession: {session_id}")
        print(f"  Host: {info.host}:{info.port}")
        print(f"  Age: {info.age_seconds:.2f} seconds")

    print()

    # Example 4: Close a session
    print("Example 4: Closing a session")
    print("-" * 70)

    if sessions.active_sessions > 0:
        session_id = list(sessions.sessions.keys())[0]
        result = await telnet_close_session(session_id)
        print(f"Close result: {result.message}")
    else:
        print("No sessions to close")

    print()

    print("=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
