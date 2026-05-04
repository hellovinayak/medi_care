"""
MCP Client — connects to the MediConnect MCP server via stdio transport.

This module:
  1. Spawns `mcp_server/server.py` as a subprocess.
  2. Speaks the Model Context Protocol over stdin/stdout.
  3. Exposes high-level async helpers used by the AgentOrchestrator:
       - list_tools_for_gemini()   → Gemini-compatible tool declarations
       - call_tool(name, args)     → invoke a tool, return parsed dict
       - list_resources()          → enumerate MCP resources
       - read_resource(uri)        → read resource content
       - list_prompts()            → enumerate MCP prompts
       - get_prompt(name)          → fetch rendered prompt text

The `mcp_session()` async context manager opens ONE subprocess per call
and keeps the connection alive for the full duration, making it cheap to
call multiple tools inside a single agent loop iteration.
"""

import sys
import json
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Absolute path to the MCP server script
_SERVER_SCRIPT = str(Path(__file__).parent.parent / "mcp_server" / "server.py")


def _server_params() -> StdioServerParameters:
    """Build stdio launch parameters for the MCP server subprocess."""
    return StdioServerParameters(
        command=sys.executable,       # same Python interpreter as this process
        args=[_SERVER_SCRIPT],
        env=None,                     # inherit current environment (DATABASE_URL etc.)
    )


@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """
    Async context manager — yields an initialised MCP ClientSession.

    One subprocess is spawned per `async with mcp_session()` block.
    Keep the block open for all tool calls in a single agent turn so
    that only one subprocess is spawned per user message.

    Usage::

        async with mcp_session() as session:
            tools = await _list_tools(session)
            result = await _call_tool(session, "book_appointment", {...})
    """
    async with stdio_client(_server_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # MCP handshake: client sends initialize, server responds
            await session.initialize()
            yield session


# ── Low-level helpers (accept an open session) ───────────────────────────────

async def _list_tools(session: ClientSession) -> list[dict]:
    """Fetch tool list and convert to Gemini function-declaration format."""
    result = await session.list_tools()
    gemini_tools = []
    for tool in result.tools:
        schema = tool.inputSchema or {"type": "object", "properties": {}, "required": []}
        gemini_tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        })
    return gemini_tools


async def _call_tool(session: ClientSession, name: str, arguments: dict) -> dict:
    """Invoke a tool and return the parsed JSON result."""
    result = await session.call_tool(name, arguments)
    if result.isError:
        return {"success": False, "error": f"MCP tool error: {result.content}"}
    if result.content:
        text = result.content[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            return {"success": True, "result": text}
    return {"success": False, "error": "No content returned from MCP server"}


async def _list_resources(session: ClientSession) -> list[dict]:
    """Return the list of available MCP resources."""
    result = await session.list_resources()
    return [
        {
            "uri":         str(r.uri),
            "name":        r.name,
            "description": r.description or "",
            "mimeType":    r.mimeType or "application/json",
        }
        for r in result.resources
    ]


async def _read_resource(session: ClientSession, uri: str) -> dict:
    """Read a single MCP resource by URI."""
    result = await session.read_resource(uri)
    if result.contents:
        text = result.contents[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            return {"content": text}
    return {}


async def _list_prompts(session: ClientSession) -> list[dict]:
    """Return the list of available MCP prompts."""
    result = await session.list_prompts()
    return [{"name": p.name, "description": p.description or ""} for p in result.prompts]


async def _get_prompt(session: ClientSession, name: str, arguments: dict | None = None) -> str:
    """Fetch and render a named MCP prompt, return its text content."""
    result = await session.get_prompt(name, arguments or {})
    parts = []
    for msg in result.messages:
        content = msg.content
        if hasattr(content, "text"):
            parts.append(content.text)
        elif isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


# ── High-level convenience functions (spawn session internally) ───────────────
# These are fine for one-off calls (e.g. the /api/mcp/info endpoint).
# The orchestrator uses the low-level helpers inside a single shared session.

async def list_tools_for_gemini() -> list[dict]:
    """Open an MCP session, discover all tools, return Gemini-compatible list."""
    async with mcp_session() as session:
        return await _list_tools(session)


async def call_tool(name: str, arguments: dict) -> dict:
    """Open an MCP session, invoke one tool, return result dict."""
    async with mcp_session() as session:
        return await _call_tool(session, name, arguments)


async def list_resources() -> list[dict]:
    """Discover all MCP resources."""
    async with mcp_session() as session:
        return await _list_resources(session)


async def read_resource(uri: str) -> dict:
    """Read one MCP resource by URI."""
    async with mcp_session() as session:
        return await _read_resource(session, uri)


async def list_prompts() -> list[dict]:
    """Discover all MCP prompts."""
    async with mcp_session() as session:
        return await _list_prompts(session)


async def get_prompt(name: str, arguments: dict | None = None) -> str:
    """Fetch a rendered MCP prompt by name."""
    async with mcp_session() as session:
        return await _get_prompt(session, name, arguments)
