# chuk_mcp_telnet_client/main.py
"""
MCP Server Application Entry Point

This module provides the main application initialization 
and runtime for the MCP server.
"""
import os
import sys
import asyncio

# Add the parent directory to Python path to allow imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
sys.path.insert(0, parent_dir)

# Runtime imports
from chuk_mcp_telnet_client.server.server_registry import ServerRegistry
from chuk_mcp_telnet_client.server.logging_config import logger
from chuk_mcp_telnet_client.server.config_loader import load_config, get_project_root
from chuk_mcp_telnet_client.server.server import MCPServer

def main() -> None:
    """
    Main entry point for the MCP server application.
    
    Handles configuration loading, component registration, 
    and server initialization.
    """
    # Log that the server is starting
    logger.info("Starting MCP Telnet Client")

    # Load configuration
    project_root = get_project_root()
    config = load_config(project_root)

    # Only bootstrap if NO_BOOTSTRAP is not set
    if os.getenv("NO_BOOTSTRAP"):
        logger.info("Bootstrapping disabled by NO_BOOTSTRAP environment variable")
    else:
        # Set up server registry and load components
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