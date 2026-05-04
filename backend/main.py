"""
MediConnect FastAPI Application — Main Entry Point.

A smart doctor appointment and reporting assistant using the
Model Context Protocol (MCP) for agentic AI behaviour.

MCP architecture
────────────────
  mcp_server/server.py  — real MCP server process (stdio transport)
  agent/mcp_client.py   — MCP client that spawns the server
  agent/orchestrator.py — uses the client for tool discovery + invocation

New MCP-info endpoints demonstrate the live MCP protocol:
  GET /api/mcp/info       — static overview
  GET /api/mcp/tools      — live tools/list via MCP
  GET /api/mcp/resources  — live resources/list via MCP
  GET /api/mcp/prompts    — live prompts/list via MCP
  GET /api/mcp/resource?uri=… — live resources/read via MCP
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database.connection import init_db, SessionLocal
from database.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting MediConnect API...")
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    print("✅ MediConnect API ready — MCP server will be spawned on first chat request.")
    yield
    print("👋 Shutting down MediConnect API...")


app = FastAPI(
    title="MediConnect API",
    description="Smart Doctor Appointment & Reporting Assistant — MCP + Agentic AI",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Domain routers ──────────────────────────────────────────────────────
from routers.auth import router as auth_router
from routers.chat import router as chat_router
from routers.appointments import router as appointments_router
from routers.doctors import router as doctors_router
from routers.notifications import router as notifications_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(appointments_router)
app.include_router(doctors_router)
app.include_router(notifications_router)


# ── Root ────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name": "MediConnect API",
        "version": "2.0.0",
        "mcp": "Real MCP server — see /api/mcp/info",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


# ── MCP info endpoints (use live MCP protocol) ──────────────────────────
@app.get("/api/mcp/info")
def mcp_info():
    """
    Static overview of the MCP implementation.
    Use /api/mcp/tools, /api/mcp/resources, /api/mcp/prompts for live data.
    """
    return {
        "protocol": "Model Context Protocol (MCP)",
        "transport": "stdio (subprocess)",
        "server": "mcp_server/server.py  — run with `python mcp_server/server.py`",
        "client": "agent/mcp_client.py",
        "live_endpoints": {
            "tools":     "/api/mcp/tools     — tools/list via real MCP",
            "resources": "/api/mcp/resources — resources/list via real MCP",
            "prompts":   "/api/mcp/prompts   — prompts/list via real MCP",
            "resource":  "/api/mcp/resource?uri=<uri> — resources/read via real MCP",
        },
        "how_it_works": (
            "The AgentOrchestrator opens a ClientSession to the MCP server "
            "subprocess for each user message. It calls tools/list to discover "
            "available tools (converted to Gemini function declarations), then "
            "calls tools/call for every tool the LLM wants to invoke, and "
            "prompts/get to load the role-specific system prompt — all over the "
            "MCP stdio protocol."
        ),
    }


@app.get("/api/mcp/tools")
async def mcp_tools_live():
    """List all tools exposed by the MCP server (live tools/list call)."""
    from agent.mcp_client import list_tools_for_gemini
    tools = await list_tools_for_gemini()
    return {"source": "MCP tools/list", "count": len(tools), "tools": tools}


@app.get("/api/mcp/resources")
async def mcp_resources_live():
    """List all resources exposed by the MCP server (live resources/list call)."""
    from agent.mcp_client import list_resources
    resources = await list_resources()
    return {"source": "MCP resources/list", "count": len(resources), "resources": resources}


@app.get("/api/mcp/prompts")
async def mcp_prompts_live():
    """List all prompts exposed by the MCP server (live prompts/list call)."""
    from agent.mcp_client import list_prompts
    prompts = await list_prompts()
    return {"source": "MCP prompts/list", "count": len(prompts), "prompts": prompts}


@app.get("/api/mcp/resource")
async def mcp_read_resource(uri: str = Query(..., description="Resource URI e.g. mediconnect://doctors")):
    """Read the contents of an MCP resource by URI (live resources/read call)."""
    from agent.mcp_client import read_resource
    data = await read_resource(uri)
    return {"source": "MCP resources/read", "uri": uri, "data": data}
