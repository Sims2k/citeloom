"""MCP server setup with stdio/SSE transport."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from ...infrastructure.config.settings import Settings
from .tools import (
    create_tools,
    handle_tool_call,
)

logger = logging.getLogger(__name__)


def create_mcp_server(config_path: str | Path | None = None) -> Server:
    """
    Create and configure MCP server instance.
    
    Args:
        config_path: Path to citeloom.toml configuration file (defaults to CITELOOM_CONFIG env or citeloom.toml)
    
    Returns:
        Configured MCP server instance
    """
    # Load configuration
    if config_path is None:
        config_path = os.getenv("CITELOOM_CONFIG", "citeloom.toml")
    
    config_path = Path(config_path)
    try:
        settings = Settings.from_toml(config_path)
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")
        settings = Settings()  # Use defaults
    
    # Create server instance
    server = Server("citeloom")
    
    # Store settings for tool handlers
    server._settings = settings  # type: ignore[attr-defined]
    
    # Register tools list
    @server.list_tools()
    async def list_tools() -> list:
        """List available MCP tools."""
        return create_tools(settings)
    
    # Register tool handler
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool execution."""
        # handle_tool_call already returns JSON strings (including error responses)
        result = await handle_tool_call(name, arguments, settings)
        return [TextContent(type="text", text=result)]
    
    return server


async def run_stdio_server(config_path: str | Path | None = None) -> None:
    """
    Run MCP server with stdio transport.
    
    Args:
        config_path: Path to citeloom.toml configuration file
    """
    server = create_mcp_server(config_path)
    
    # Configure logging (MCP servers typically use stderr)
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise for MCP protocol
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    
    # Run stdio server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """CLI entrypoint for MCP server."""
    config_path = os.getenv("CITELOOM_CONFIG", "citeloom.toml")
    asyncio.run(run_stdio_server(config_path))


if __name__ == "__main__":
    main()

