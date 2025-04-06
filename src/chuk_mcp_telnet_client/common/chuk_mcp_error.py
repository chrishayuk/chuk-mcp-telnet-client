# src/chuk_mcp_telnet_client/common/errors.py

class ChukMcpError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
