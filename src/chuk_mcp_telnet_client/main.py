# chuk_mcp_telnet_client/main.py
"""
Main entry point for the Telnet Client MCP Server.

Supports both stdio (default) and HTTP transport modes:
- stdio: Default mode, works with uvx and MCP clients (no session sharing)
- HTTP: Optional mode for persistent sessions across requests

Usage:
    mcp-telnet-client              # stdio mode (default)
    mcp-telnet-client http         # HTTP mode with session persistence
    mcp-telnet-client --http       # HTTP mode (alternate syntax)
"""

import logging
import sys

from chuk_mcp_server import run

# Configure logging
# In STDIO mode, we need to be quiet to avoid polluting the JSON-RPC stream
# Only log to stderr, and only warnings/errors
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    """Run the Telnet Client MCP server."""
    # Import tools to register them with the global decorator
    from . import tools  # noqa: F401

    # Check if transport is specified in command line args
    # Default to stdio for MCP compatibility (Claude Desktop, uvx, mcp-cli)
    transport = "stdio"

    # Allow HTTP mode via command line (case insensitive)
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["http", "--http"]:
        transport = "http"
        # Only log in HTTP mode
        logger.warning("Starting Telnet Client MCP Server in HTTP mode")

    # Suppress chuk_mcp_server logging in STDIO mode
    if transport == "stdio":
        # Set chuk_mcp_server loggers to ERROR only
        logging.getLogger("chuk_mcp_server").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.core").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.stdio_transport").setLevel(logging.ERROR)

    # Run the server
    # stdio: Works with uvx, one-shot commands (no session persistence)
    # http: Allows session reuse across multiple requests
    run(transport=transport)


if __name__ == "__main__":
    main()
