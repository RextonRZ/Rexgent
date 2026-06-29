"""Real MCP server exposing the 6 Rexgent tools over the Model Context Protocol.

Run this as a standalone process (see backend/mcp_server_entry.py). It is
isolated from the FastAPI app because the `mcp` SDK pins a starlette version
that conflicts with FastAPI's — which is fine, since MCP servers run as their
own process and connect to MCP clients (Claude Desktop, etc.) over stdio.

It serves the EXACT same tool functions (app.mcp_tools.registry) that the
FastAPI HTTP routes call, so there is one implementation, two transports.
"""
import asyncio
import inspect
import json
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from app.mcp_tools.registry import TOOL_DEFINITIONS, get_tool

server = Server("rexgent-tools")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
        for t in TOOL_DEFINITIONS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    fn = get_tool(name)
    result = fn(arguments)
    if inspect.isawaitable(result):
        result = await result
    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
