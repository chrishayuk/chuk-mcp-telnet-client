#!/usr/bin/env python3
"""
Star Wars Telnet Example

This example demonstrates connecting to the famous Star Wars ASCII art telnet server
and capturing the initial frames of the animation.
"""

import asyncio

from chuk_mcp_telnet_client.tools import telnet_client_tool


async def main():
    """Connect to Star Wars telnet server and watch the intro."""
    print("=" * 70)
    print("Star Wars ASCII Art - Telnet Demo")
    print("=" * 70)
    print()
    print("Connecting to towel.blinkenlights.nl:23...")
    print("This is the famous Star Wars ASCII art animation!")
    print()

    try:
        # Connect and watch the intro
        result = await telnet_client_tool(
            host="towel.blinkenlights.nl",
            port=23,
            commands=[""],  # Just connect and get initial output
            command_delay=0.5,
            response_wait=2.0,  # Wait longer to capture animation
            close_session=True,  # Close when done
        )

        print("Connection successful!")
        print(f"Session ID: {result.session_id}")
        print()
        print("-" * 70)
        print("Initial Banner (First ~500 characters):")
        print("-" * 70)
        # Show first part of the banner
        banner_preview = result.initial_banner[:500]
        print(banner_preview)

        if len(result.initial_banner) > 500:
            print(
                f"\n... (truncated, total length: {len(result.initial_banner)} chars)"
            )

        print()
        print("-" * 70)
        print(f"Session closed: {not result.session_active}")
        print("-" * 70)

    except Exception as e:
        print(f"Error connecting: {e}")
        print()
        print("Note: The Star Wars telnet server may occasionally be unavailable.")

    print()
    print("=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
