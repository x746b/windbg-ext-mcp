#!/usr/bin/env python
"""
WinDbg MCP Server

Main entry point for the MCP server that brokers between MCP clients and the
WinDbg extension over a named pipe.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from zeromcp import McpServer

from mcp_server.config import LOG_FORMAT, load_environment_config, LOG_LEVEL, DEBUG_ENABLED
from mcp_server.tools import register_all_tools, get_tool_info
from mcp_server.core.server_initialization import ServerInitializer, InitializationConfig


def _configure_logging() -> logging.Logger:
    load_environment_config()
    logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
    logger = logging.getLogger(__name__)
    if DEBUG_ENABLED:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("zeromcp").setLevel(logging.DEBUG)
    return logger


class WinDbgMCPServer:
    """Main WinDbg MCP Server class."""

    def __init__(self, transport: str | None = None) -> None:
        self.mcp = McpServer("windbg-mcp")
        self.initializer = ServerInitializer(InitializationConfig())
        self._initialized = False
        self.logger = logging.getLogger(__name__)
        self.transport = transport

    def start(self) -> None:
        """Start the WinDbg MCP Server."""
        try:
            self._log_startup_banner()
            self.initializer.initialize()
            self._initialized = True
            self._register_tools()
            self._log_transport_info()
            self._run_server()
        except Exception as e:  # pragma: no cover - startup path
            self.logger.error(f"Failed to start server: {e}")
            raise

    def _log_startup_banner(self) -> None:
        tool_info: Dict = get_tool_info()
        self.logger.info("WinDbg MCP Server")
        self.logger.info("=" * 40)
        self.logger.info(f"Total tools: {tool_info['total_tools']}")
        self.logger.info("Tool categories:")
        for category, details in tool_info["categories"].items():
            self.logger.info(f"  {category}: {len(details['tools'])} tools")

    def _register_tools(self) -> None:
        self.logger.debug("Registering tools…")
        register_all_tools(self.mcp)

    def _log_transport_info(self) -> None:
        """Log transport configuration."""
        if self.transport:
            self.logger.info(f"MCP server ready. Listening on HTTP/SSE at {self.transport}")
        else:
            self.logger.info("MCP server ready. Listening on stdio.")

    def _run_server(self) -> None:
        """Run the server with configured transport."""
        try:
            if self.transport:
                # Parse the URL to extract host and port
                parsed = urlparse(self.transport)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 5312

                self.logger.info(f"Starting HTTP/SSE server on {host}:{port}")
                self.mcp.serve(host, port, background=False)
            else:
                self.mcp.stdio()
        except KeyboardInterrupt:
            self.logger.info("Server stopped by user")
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="windbg-mcp", description="WinDbg MCP server")
    parser.add_argument(
        "--list-tools", action="store_true", help="Print available tools and exit"
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument(
        "--transport",
        type=str,
        help="Transport URL for HTTP/SSE (e.g., http://127.0.0.1:5312). If not provided, uses stdio.",
    )
    args = parser.parse_args(argv)

    if args.version:
        from mcp_server import __version__

        print(__version__)
        return 0

    if args.list_tools:
        info = get_tool_info()
        print(f"Total tools: {info['total_tools']}")
        for cat, details in info["categories"].items():
            print(f"- {cat}: {', '.join(details['tools'])}")
        return 0

    server = WinDbgMCPServer(transport=args.transport)
    server.start()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
