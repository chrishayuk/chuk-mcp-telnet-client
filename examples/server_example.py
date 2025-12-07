#!/usr/bin/env python3
"""
MCP Server example for the Telnet Client.

This example shows how to run the telnet client as an MCP server.
"""

from chuk_mcp_server import run


def main():
    """Run the Telnet Client MCP Server."""
    # Import tools to register them
    from chuk_mcp_telnet_client import tools  # noqa: F401

    print("=" * 70)
    print("Starting Telnet Client MCP Server")
    print("=" * 70)
    print()
    print("Available tools:")
    print("  - telnet_client: Connect to telnet servers and execute commands")
    print("  - telnet_close_session: Close an active telnet session")
    print("  - telnet_list_sessions: List all active telnet sessions")
    print()
    print("The server is running in stdio mode (default)")
    print("Connect using an MCP client to interact with telnet servers")
    print()
    print("=" * 70)

    # Run in stdio mode (default)
    run(transport="stdio")


if __name__ == "__main__":
    main()
