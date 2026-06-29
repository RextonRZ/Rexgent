"""Entry point for the standalone Rexgent MCP server.

Run in its own virtualenv (see backend/mcp_requirements.txt):
    python mcp_server_entry.py

Registers 6 tools over MCP stdio. Connect from any MCP client.
"""
import asyncio
from app.mcp_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
