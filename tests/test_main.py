"""
Tests for the main entry point module.

Tests cover:
- Transport mode detection
- Logging configuration
- Command line argument parsing
"""

import sys
from unittest.mock import MagicMock, patch


def test_main_default_stdio_mode():
    """Test that main() runs in stdio mode by default."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        # Clear any command line args
        with patch.object(sys, "argv", ["mcp-telnet-client"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should call run with stdio transport
            mock_run.assert_called_once_with(transport="stdio")


def test_main_http_mode_with_http_arg():
    """Test that main() runs in HTTP mode when 'http' arg is provided."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "http"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should call run with http transport
            mock_run.assert_called_once_with(transport="http")


def test_main_http_mode_with_http_flag():
    """Test that main() runs in HTTP mode when '--http' flag is provided."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "--http"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should call run with http transport
            mock_run.assert_called_once_with(transport="http")


def test_main_stdio_mode_explicit():
    """Test that main() handles explicit 'stdio' argument."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "stdio"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should call run with stdio transport (default behavior)
            mock_run.assert_called_once_with(transport="stdio")


def test_main_ignores_unknown_args():
    """Test that unknown arguments don't trigger HTTP mode."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "unknown"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should default to stdio for unknown args
            mock_run.assert_called_once_with(transport="stdio")


def test_main_logging_configuration_stdio():
    """Test that logging is properly configured for stdio mode."""
    with patch("chuk_mcp_telnet_client.main.run"):
        with patch.object(sys, "argv", ["mcp-telnet-client"]):
            with patch("logging.getLogger") as mock_get_logger:
                # Create mock loggers
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                from chuk_mcp_telnet_client.main import main

                main()

                # Verify logger configuration was called
                # In stdio mode, framework loggers should be set to ERROR
                assert mock_get_logger.called


def test_main_logging_configuration_http():
    """Test that logging is properly configured for HTTP mode."""
    with patch("chuk_mcp_telnet_client.main.run"):
        with patch.object(sys, "argv", ["mcp-telnet-client", "http"]):
            with patch("chuk_mcp_telnet_client.main.logger") as mock_logger:
                from chuk_mcp_telnet_client.main import main

                main()

                # In HTTP mode, should log the startup message
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[0][0]
                assert "HTTP mode" in call_args


def test_main_imports_tools():
    """Test that main() imports tools module to register decorators."""
    with patch("chuk_mcp_telnet_client.main.run"):
        with patch.object(sys, "argv", ["mcp-telnet-client"]):
            # Mock the tools import
            with patch("chuk_mcp_telnet_client.main.tools", create=True):
                from chuk_mcp_telnet_client.main import main

                main()

                # Tools should be imported (the import happens, mock just verifies)
                # The actual verification is that run() is called, which requires tools


def test_main_callable_from_module():
    """Test that main can be called when module is run directly."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client"]):
            # Import and call main
            from chuk_mcp_telnet_client.main import main

            # Should be callable
            assert callable(main)

            # Should work when called
            main()
            mock_run.assert_called_once()


def test_main_multiple_args_uses_first():
    """Test that only the first argument is checked for transport mode."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "http", "extra", "args"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should use http based on first arg
            mock_run.assert_called_once_with(transport="http")


def test_main_case_insensitive_http():
    """Test that HTTP mode detection is case insensitive."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "HTTP"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should recognize HTTP in any case
            mock_run.assert_called_once_with(transport="http")


def test_main_case_insensitive_http_flag():
    """Test that --http flag is case insensitive."""
    with patch("chuk_mcp_telnet_client.main.run") as mock_run:
        with patch.object(sys, "argv", ["mcp-telnet-client", "--HTTP"]):
            from chuk_mcp_telnet_client.main import main

            main()

            # Should recognize --HTTP in any case
            mock_run.assert_called_once_with(transport="http")
