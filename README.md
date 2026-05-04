# MediConnect — Smart Doctor Appointment & Reporting Assistant

> **Full-Stack Agentic AI with a real Model Context Protocol (MCP) implementation**

Patients book appointments through natural language; doctors get AI-generated reports — all powered by a Gemini LLM agent that discovers and invokes backend capabilities through a genuine MCP client-server setup.

---

## What Makes This a Real MCP Implementation

The previous version had a Python class *named* `MCPServer` — but that was just a wrapper around a dictionary of functions with no protocol involved.

This version implements the full **Model Context Protocol**:

| Layer | File | Role |
|---|---|---|
| **MCP Server** | `backend/mcp_server/server.py` | Standalone process; exposes tools, resources, and prompts over the MCP stdio protocol using the official `mcp` Python SDK (`FastMCP`) |
| **MCP Client** | `backend/agent/mcp_client.py` | Spawns the server as a subprocess; communicates via `ClientSession` over stdin/stdout using the MCP wire protocol |
| **Orchestrator** | `backend/agent/orchestrator.py` | Calls `tools/list`, `prompts/get`, and `tools/call` via the MCP client; never hard-codes tool definitions |

### What the MCP protocol provides here

```
Orchestrator                MCP Client              MCP Server subprocess
     │                          │                          │
     │  process_message()       │                          │
     │──────────────────────────▶  stdio_client spawn      │
     │                          │─────────────────────────▶│
     │                          │  initialize (handshake)  │
     │                          │◀─────────────────────────│
     │                          │  tools/list              │
     │                          │─────────────────────────▶│
     │                          │◀── [Tool, Tool, ...]  ───│
     │  tools (Gemini format)   │                          │
     │◀─────────────────────────│                          │
     │                          │  prompts/get             │
     │                          │─────────────────────────▶│
     │                          │◀── system prompt text ───│
     │                          │                          │
     │  [Gemini responds with functionCall]                 │
     │                          │  tools/call              │
     │                          │─────────────────────────▶│
     │                          │◀── JSON result ──────────│
     │                          │                          │
     │  [repeat until text response]                        │
     │                          │                          │
     │  final text response     │                          │
     │◀─────────────────────────│                          │
```

One MCP subprocess is spawned per user message and kept alive for the entire agent loop (all tool calls in that turn share the same connection).

---

## Architecture

```
┌───────────────────┐    HTTP     ┌──────────────────────────────────────┐
│  React Frontend   │◄──────────▶│  FastAPI Backend (port 8000)          │
│  Vite + React     │            │                                        │
│  • Chat UI        │            │  AgentOrchestrator                     │
│  • Dashboards     │            │    │  1. open MCP session              │
│  • Auth           │            │    │  2. tools/list (discover)         │
└───────────────────┘            │    │  3. prompts/get (system prompt)   │
                                 │    │  4. call Gemini                   │
                                 │    │  5. tools/call (per LLM request)  │
                                 │    │  6. repeat until text response    │
                                 │    ▼                                   │
                                 │  MCP Client (stdio)                    │
                                 │    │                                   │
                                 │    ▼  (subprocess)                     │
                                 │  MCP Server — mcp_server/server.py     │
                                 │    • 9 tools                           │
                                 │    • 3 resources                       │
                                 │    • 2 prompts                         │
                                 │    │                                   │
                                 │    ▼                                   │
                                 │  SQLite Database                       │
                                 └──────────────────────────────────────┘
```

---

## Setup & Running

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend will auto-create the SQLite database and seed demo accounts:
- **Patient** — `vinayak@gmail.com` / `123`
- **Doctor** — `doctor@mediconnect.com` / `doctor123`

Add your Gemini API key to `backend/.env`:
```
GEMINI_API_KEY=your_key_here
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Testing the MCP Implementation

### Option A — Standalone MCP test (no API key needed)

```bash
cd backend
python test_mcp.py
```

This opens a real MCP ClientSession, runs the full MCP handshake, then exercises `tools/list`, `prompts/list`, `prompts/get`, `resources/list`, `resources/read`, and two `tools/call` invocations — all over the stdio transport.

Expected output:
```
============================================================
  MediConnect — Real MCP Client-Server Communication Test
============================================================

✅  MCP handshake complete (initialize)

─── tools/list ─────────────────────────────────────────────
Discovered 9 tools:
  • get_doctors_list                 Get a list of all available doctors ...
  • check_doctor_availability        Check a doctor's available appointment...
  ...

─── prompts/list ──────────────────────────────────────────
Discovered 2 prompts:
  • patient_appointment              System prompt for the patient-facing ...
  • doctor_summary                   System prompt for the doctor-facing ...

─── tools/call: get_doctors_list ───────────────────────────
✅  Tool returned 4 doctors:
  • Dr. Ahuja (General Physician)
  ...
```

### Option B — Live via the API (server must be running)

```bash
# List all MCP tools (live tools/list call)
curl http://localhost:8000/api/mcp/tools

# List all MCP resources
curl http://localhost:8000/api/mcp/resources

# List all MCP prompts
curl http://localhost:8000/api/mcp/prompts

# Read a resource (live resources/read call)
curl "http://localhost:8000/api/mcp/resource?uri=mediconnect://doctors"
curl "http://localhost:8000/api/mcp/resource?uri=mediconnect://stats/today"
```

### Option C — Run the MCP server directly (inspect raw protocol)

```bash
cd backend
python mcp_server/server.py
# Now type MCP JSON-RPC messages on stdin, e.g.:
# {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}
```

### Option D — Use MCP Inspector (visual tool)

```bash
npx @modelcontextprotocol/inspector python backend/mcp_server/server.py
```

Open http://localhost:5173 in the Inspector to browse tools, resources, and prompts interactively.

---

## MCP Server Details

### Tools (9 total — discovered dynamically via `tools/list`)

| Tool | Description |
|---|---|
| `get_doctors_list` | List all doctors, optional specialty filter |
| `check_doctor_availability` | Available slots for a doctor on a given date |
| `book_appointment` | Book a time slot; returns appointment ID |
| `send_email_confirmation` | Email confirmation after booking |
| `get_appointment_stats` | Stats for a period (today/week/month) |
| `send_notification` | In-app notification to a user |
| `get_patient_appointments` | Patient's upcoming/past appointments |
| `cancel_appointment` | Cancel by appointment ID |
| `complete_appointment` | Mark appointment as completed |

FastMCP auto-generates JSON schemas from Python type hints, which are then converted to Gemini function declarations by the MCP client.

### Resources (3 total — addressable by URI via `resources/read`)

| URI | Content |
|---|---|
| `mediconnect://doctors` | Live list of all doctors |
| `mediconnect://appointments/upcoming` | All upcoming scheduled appointments |
| `mediconnect://stats/today` | Today's appointment counts by status |

### Prompts (2 total — retrieved via `prompts/get`)

| Name | Purpose |
|---|---|
| `patient_appointment` | Patient-facing booking assistant system prompt |
| `doctor_summary` | Doctor-facing reporting assistant system prompt |

The orchestrator fetches these at runtime — the prompts are never embedded in the orchestrator code itself.

---

## Multi-Turn Conversation

Sessions are maintained in `agent/session.py`. The full Gemini conversation history (including all function call/result turns) is stored per session ID and replayed on every request. This gives the LLM continuity across multiple messages:

```
User:  "I want to see Dr. Ahuja tomorrow"
  → MCP tools/call: check_doctor_availability(doctor_name="Dr. Ahuja", date="tomorrow")
  → Available slots: [10:00, 11:00, 14:00, 15:00]
AI:   "Dr. Ahuja is available tomorrow. Which time works for you?"

User:  "3 PM please"   ← context retained from previous turn
  → MCP tools/call: book_appointment(doctor_name="Dr. Ahuja", date="tomorrow", time_slot="15:00")
  → MCP tools/call: send_email_confirmation(appointment_id=42)
AI:   "Booked! You'll receive an email confirmation."
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | FastAPI (Python) |
| MCP SDK | `mcp` (official Python SDK — `FastMCP`) |
| MCP Transport | stdio (subprocess) |
| LLM | Gemini 2.5 Flash (function-calling) |
| Database | SQLite + SQLAlchemy ORM |
| Auth | JWT (python-jose + passlib) |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat` | Send message to AI agent |
| GET | `/api/chat/history/{session_id}` | Conversation history |
| GET | `/api/appointments` | List appointments |
| GET | `/api/doctors` | List doctors |
| GET | `/api/notifications` | Get notifications |
| GET | `/api/mcp/info` | MCP implementation overview |
| GET | `/api/mcp/tools` | **Live** `tools/list` via MCP |
| GET | `/api/mcp/resources` | **Live** `resources/list` via MCP |
| GET | `/api/mcp/prompts` | **Live** `prompts/list` via MCP |
| GET | `/api/mcp/resource?uri=…` | **Live** `resources/read` via MCP |
