"""Entry point for the mcp-server-odoo package."""

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

from .config import load_config
from .server import SERVER_VERSION, OdooMCPServer


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Odoo MCP Server - Model Context Protocol server for Odoo ERP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Environment variables:
  ODOO_URL              Odoo server URL (required)
  ODOO_API_KEY          Odoo API key
  ODOO_USER             Odoo username
  ODOO_PASSWORD         Odoo password
  ODOO_DB               Odoo database name (auto-detected if not set)
  ODOO_API_PROTOCOL     API protocol: xmlrpc (default) or json2 (Odoo 19+)
  ODOO_EXECUTE_LEVEL    Method execution level: safe, business (default), admin
  ODOO_YOLO             YOLO mode (xmlrpc only): off, read, or true

Optional:
  ODOO_MCP_LOG_LEVEL    Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  ODOO_MCP_DEFAULT_LIMIT   Default record limit (default: 10)
  ODOO_MCP_MAX_LIMIT       Maximum record limit (default: 100)
  ODOO_MCP_TRANSPORT    Transport type: stdio or streamable-http (default: stdio)
  ODOO_MCP_HOST         Server host for HTTP transports (default: localhost)
  ODOO_MCP_PORT         Server port for HTTP transports (default: 8000)
  ODOO_LOCALE           Locale for formatting (e.g. en_US, de_DE)

JSON-2 quick start (.env):
  ODOO_URL=https://myodoo.example.com
  ODOO_API_KEY=your-api-key-here
  ODOO_API_PROTOCOL=json2
  ODOO_DB=mydb
  ODOO_EXECUTE_LEVEL=business

For more information, visit: https://github.com/ivnvxd/mcp-server-odoo""",
    )

    parser.add_argument("--version", action="version", version=f"odoo-mcp-server v{SERVER_VERSION}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("ODOO_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("ODOO_MCP_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ODOO_MCP_PORT", "8000")))

    args = parser.parse_args(argv)

    try:
        if args.transport:
            os.environ["ODOO_MCP_TRANSPORT"] = args.transport
        if args.host:
            os.environ["ODOO_MCP_HOST"] = args.host
        if args.port:
            os.environ["ODOO_MCP_PORT"] = str(args.port)

        config = load_config()
        server = OdooMCPServer(config)

        if config.transport == "stdio":
            asyncio.run(server.run_stdio())
        elif config.transport == "streamable-http":
            asyncio.run(server.run_http(host=config.host, port=config.port))
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

        return 0

    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        return 0
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
