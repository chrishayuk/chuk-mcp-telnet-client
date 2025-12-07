# Telnet Client MCP Server - Examples

This directory contains example scripts demonstrating how to use the Telnet Client MCP Server.

## Examples

### 1. Basic Usage (`basic_usage.py`)

Demonstrates programmatic usage of the telnet client tools:
- Simple telnet connection
- Session reuse
- Listing active sessions
- Closing sessions

**Run it:**
```bash
uv run python examples/basic_usage.py
```

### 2. Server Example (`server_example.py`)

Shows how to run the telnet client as an MCP server:
- Starting the server in stdio mode
- Available tools and their descriptions

**Run it:**
```bash
uv run python examples/server_example.py
```

### 3. Star Wars Example (`star_wars_example.py`)

Fun example connecting to the famous Star Wars ASCII art telnet server:
- Demonstrates real-world telnet connection
- Shows banner capture and session management
- Connects to towel.blinkenlights.nl:23

**Run it:**
```bash
uv run python examples/star_wars_example.py
```

## Common Use Cases

### Connecting to a Telnet Server

```python
import asyncio
from chuk_mcp_telnet_client.tools import telnet_client_tool

async def connect_example():
    result = await telnet_client_tool(
        host="towel.blinkenlights.nl",  # Star Wars ASCII art
        port=23,
        commands=[""],  # Just get the banner
        command_delay=0.5,
        response_wait=1.0
    )
    print(f"Banner: {result.initial_banner}")

asyncio.run(connect_example())
```

### Session Management

```python
# Create a session
result1 = await telnet_client_tool(
    host="localhost",
    port=23,
    commands=["ls"],
)
session_id = result1.session_id

# Reuse the session
result2 = await telnet_client_tool(
    host="localhost",
    port=23,
    commands=["pwd"],
    telnet_session_id=session_id
)

# Close when done
await telnet_close_session(session_id)
```

### Customizing Timeouts and Delays

```python
result = await telnet_client_tool(
    host="example.com",
    port=23,
    commands=["command1", "command2"],
    command_delay=1.0,        # Wait 1s after sending each command
    response_wait=2.0,         # Wait 2s for response
    strip_command_echo=True    # Remove command echo from output
)
```

## Testing Locally

To test the examples locally, you can use the included test server or connect to public telnet servers:

**Public telnet servers for testing:**
- `towel.blinkenlights.nl:23` - Star Wars ASCII art
- `telehack.com:23` - Retro computing simulator
- `rainmaker.wunderground.com:23` - Weather information

**Note:** Many of these servers may be slow or unavailable. For production use, ensure you have reliable telnet servers to connect to.

## Running as an MCP Server

To use the telnet client with an MCP client (like Claude Desktop):

1. Install the package:
   ```bash
   pip install chuk-mcp-telnet-client
   ```

2. Configure your MCP client to use the telnet server:
   ```json
   {
     "mcpServers": {
       "telnet": {
         "command": "mcp-telnet-client"
       }
     }
   }
   ```

3. The server will be available with three tools:
   - `telnet_client` - Connect and execute commands
   - `telnet_list_sessions` - List active sessions
   - `telnet_close_session` - Close a session

## Development

For development, you can run the server in debug mode:

```bash
PYTHONPATH=src python -m chuk_mcp_telnet_client.main
```

Or use the Makefile:

```bash
make run
```
