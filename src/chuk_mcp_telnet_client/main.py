"""
MCP Server Application Entry Point

This module provides the main application initialization 
and runtime for the MCP Telnet Client.
"""
import os
import sys
import asyncio

# Add the parent directory to Python path to allow imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the tools to ensure their decorators register the tools
import chuk_mcp_telnet_client.tools

# Runtime imports from chuk_mcp_runtime
from chuk_mcp_runtime.server.server_registry import ServerRegistry
from chuk_mcp_runtime.server.logging_config import get_logger, configure_logging
from chuk_mcp_runtime.server.config_loader import load_config, find_project_root
from chuk_mcp_runtime.server.server import MCPServer

logger = get_logger("chuk_mcp_telnet_client")

def main() -> None:
    """
    Main entry point for the MCP Telnet Client application.
    
    Handles configuration loading, component registration, 
    and server initialization.
    """
    logger.info("Starting MCP Telnet Client")

    # Determine the project root and load configuration
    project_root = find_project_root()
    config = load_config()

    # Optionally bootstrap server components if enabled
    if os.getenv("NO_BOOTSTRAP"):
        logger.info("Bootstrapping disabled by NO_BOOTSTRAP environment variable")
    else:
        registry = ServerRegistry(project_root, config)
        registry.load_server_components()

    try:
        # Create and run the MCP server
        mcp_server = MCPServer(config)
        asyncio.run(mcp_server.serve())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)

if __name__ == "__main__":
    main()