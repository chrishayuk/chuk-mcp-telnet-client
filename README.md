# MCP Telnet Client

## Overview

The MCP Telnet Client is a Python-based microservice that provides a robust interface for interacting with Telnet servers. It enables applications to establish Telnet connections, execute commands, and maintain persistent sessions across multiple requests.

## Project Details

- **Version**: 0.1.0
- **Python Compatibility**: Python 3.9+

## Features

- **Telnet Server Connectivity**: Connect to any Telnet server with host and port specification
- **Command Execution**: Send commands and collect responses in a structured format
- **Session Management**: Maintain persistent connections with unique session IDs
- **Minimal Telnet Negotiation**: Handles IAC negotiation with sensible defaults
- **Async Server Architecture**: Built with asyncio for efficient performance
- **Flexible Configuration**: Configurable through environment variables and config files
- **Comprehensive Validation**: Robust input validation using Pydantic models

## Dependencies

Core dependencies:
- mcp (>=1.6.0)
- pydantic
- telnetlib (standard library)
- typing (standard library)

Development dependencies:
- pytest

## Installation

### Prerequisites

- Python 3.9 or higher
- pip
- (Optional) Virtual environment recommended

### Install from PyPI

```bash
pip install chuk-mcp-telnet-client
```

### Install from Source

1. Clone the repository:
```bash
git clone <repository-url>
cd chuk-mcp-telnet-client
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install the package:
```bash
pip install .
```

### Development Installation

To set up for development:
```bash
pip install .[dev]  # Installs package with development dependencies
```

## Running the Server

### Command-Line Interface

```bash
chuk-mcp-telnet-client
```

### Programmatic Usage

```python
from chuk_mcp_telnet_client.main import main

if __name__ == "__main__":
    main()
```

## Environment Variables

- `NO_BOOTSTRAP`: Set to disable component bootstrapping
- Other configuration options can be set in the configuration files

## Available Tools

### 1. Telnet Client

Establishes a connection to a Telnet server and executes commands.

**Input**:
- `host`: Host/IP of the Telnet server
- `port`: Port number (e.g., 8023)
- `commands`: List of commands to send to the server
- `session_id` (optional): ID to maintain connection between calls
- `close_session` (optional): If True, close the session after processing commands

**Example**:
```python
telnet_client_tool(
    host="example.com",
    port=23,
    commands=["show version", "show interfaces"],
    session_id=None,  # Auto-generated if not provided
    close_session=False
)
```

**Returns**:
- Initial banner from the server
- List of command responses
- Session information for maintaining connection

### 2. Close Telnet Session

Closes a specific Telnet session by ID.

**Input**:
- `session_id`: The session ID to close

**Example**:
```python
telnet_close_session("telnet_example.com_23_1649876543")
```

**Returns**:
- Status of the operation (success or failure)
- Descriptive message

### 3. List Telnet Sessions

Lists all active Telnet sessions.

**Input**: None

**Example**:
```python
telnet_list_sessions()
```

**Returns**:
- Count of active sessions
- Details for each session (host, port, creation time, age)

## Technical Details

### Session Management

Sessions are maintained in a global dictionary (`TELNET_SESSIONS`) with the following structure:
- Key: Unique session ID
- Value: Dictionary containing:
  - `telnet`: Telnet connection object
  - `host`: Server hostname/IP
  - `port`: Server port number
  - `created_at`: Session creation timestamp

### Telnet Option Negotiation

The client implements minimal Telnet option negotiation that:
- Responds with WONT to DO requests
- Responds with DONT to WILL requests

This approach ensures compatibility with most Telnet servers while avoiding complex negotiation.

## Development

### Code Structure

- `main.py`: Application entry point
- `models.py`: Pydantic models for input/output validation
- `server/`: Server implementation components

### Running Tests

```bash
pytest
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

[MIT License](LICENSE)