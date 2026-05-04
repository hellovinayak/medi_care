## MediConnect — Complete MCP Architecture & Requirement Mapping

### ✅ MCP Client–Server Architecture

**Server Process**
```
mcp_server/server.py
├─ Runs as independent subprocess
├─ Uses FastMCP (official mcp Python SDK)
├─ Listens on stdin, writes to stdout
└─ Never runs in the FastAPI process
```

**Client Process**
```
agent/mcp_client.py
├─ Spawns mcp_server.py as subprocess via stdio_client
├─ Maintains ClientSession connection
├─ Sends/receives MCP JSON-RPC messages
└─ Provides async helpers (_list_tools, _call_tool, etc.)
```

**Wire Protocol: JSON-RPC over stdio**
```
Client                                    Server (subprocess)
  │                                         │
  ├─ {"jsonrpc":"2.0","method":"initialize",...}
  ├──────────────────────────────────────▶ │
  │                                         │
  │ {"jsonrpc":"2.0","result":{"capabilities":{...}}}
  │◀────────────────────────────────────── ├
  │                                         │
  ├─ {"jsonrpc":"2.0","method":"tools/list",...}
  ├──────────────────────────────────────▶ │
  │                                         │
  │ {"jsonrpc":"2.0","result":{"tools":[...]}}
  │◀────────────────────────────────────── ├
  │                                         │
  ├─ {"jsonrpc":"2.0","method":"tools/call","params":{"name":"book_appointment",...}}
  ├──────────────────────────────────────▶ │
  │                                         │
  │ {"jsonrpc":"2.0","result":{"success":true,...}}
  │◀────────────────────────────────────── ├
```

---

### ✅ Tool Discovery and Invocation Through MCP

**Where Tools Are Defined**
```python
# mcp_server/server.py

@mcp.tool()
def get_doctors_list(specialty: str = "") -> str:
    """FastMCP auto-generates JSON schema from type hints"""
    # ... implementation ...
    return json.dumps({"success": True, "doctors": [...]})

@mcp.tool()
def book_appointment(doctor_name: str, date: str, time_slot: str, ...) -> str:
    """Another tool with auto-schema generation"""
    # ... implementation ...
    return json.dumps({"success": True, "appointment_id": 42})

# Total: 9 tools registered via @mcp.tool() decorator
```

**Tool Discovery (tools/list) Flow**
```
User sends: /api/chat {"message": "Book Dr. Ahuja tomorrow"}
            ↓
        orchestrator.process_message()
            ↓
        async with mcp_session() as mcp:
            ↓
            tools = await _list_tools(mcp)  ← MCP RPC: tools/list
            ↓
            [Real MCP communication over stdio]
            ↓
            Server runs: mcp.list_tools() → discovers 9 @mcp.tool() registrations
            ↓
            Returns JSON with full JSON schemas:
            {
              "tools": [
                {
                  "name": "get_doctors_list",
                  "description": "...",
                  "inputSchema": {
                    "type": "object",
                    "properties": {
                      "specialty": {"type": "string", "description": "..."}
                    },
                    "required": []
                  }
                },
                ... 8 more tools ...
              ]
            }
            ↓
            Converted to Gemini format for function calling
            ↓
            Sent to Gemini in the system prompt
```

**Tool Invocation (tools/call) Flow**
```
Gemini response includes: {"functionCall": {"name": "book_appointment", "args": {...}}}
            ↓
        orchestrator receives it
            ↓
        result = await _call_tool(mcp, "book_appointment", args)
            ↓
            [Real MCP communication over stdio]
            ↓
            Client sends: {"jsonrpc":"2.0","method":"tools/call","params":{"name":"book_appointment","arguments":{...}}}
            ↓
            Server executes: TOOL_REGISTRY["book_appointment"](db, **args)
            ↓
            Server returns: {"success": true, "appointment_id": 42, ...}
            ↓
            result = {"success": true, "appointment_id": 42, ...}
            ↓
        Append to Gemini conversation: {"functionResponse": {"name": "book_appointment", "response": result}}
            ↓
        Continue agent loop until Gemini returns text response
```

**Code Location: Tool Invocation**
```python
# agent/mcp_client.py
async def _call_tool(session: ClientSession, name: str, arguments: dict) -> dict:
    """Invoke a tool and return the parsed JSON result."""
    result = await session.call_tool(name, arguments)  # ← MCP protocol call
    # ... parse and return ...
    return parsed_json

# agent/orchestrator.py
for fc_part in function_calls:
    fc = fc_part["functionCall"]
    tool_name = fc["name"]
    tool_args = dict(fc.get("args", {}))
    
    # Inject user context
    if "patient_id" not in tool_args and "patient_id" in user_context:
        tool_args["patient_id"] = user_context["patient_id"]
    
    # Invoke via MCP
    result = await _call_tool(mcp, tool_name, tool_args)  # ← HERE
    
    tool_calls_made.append({
        "tool": tool_name,
        "args": tool_args,
        "result": result,
    })
```

---

### ✅ MCP Tools, Prompts, and Resources

#### Tools (9 total, discovered via tools/list)
```python
# mcp_server/server.py — all registered via @mcp.tool()

1. get_doctors_list(specialty)
   → Returns: {"success": true, "doctors": [...], "count": N}

2. check_doctor_availability(doctor_name, date)
   → Returns: {"success": true, "available_slots": [...], "booked_slots": [...]}

3. book_appointment(doctor_name, date, time_slot, patient_id, reason, symptoms)
   → Returns: {"success": true, "appointment_id": N, ...}

4. send_email_confirmation(appointment_id)
   → Returns: {"success": true, "email_status": "mock_sent"}

5. get_appointment_stats(period, doctor_name, symptom_filter)
   → Returns: {"success": true, "total_appointments": N, "scheduled": M, ...}

6. send_notification(user_email, title, message, notification_type)
   → Returns: {"success": true, "notification_id": N}

7. get_patient_appointments(patient_id, status, period)
   → Returns: {"success": true, "appointments": [...], "count": N}

8. cancel_appointment(appointment_id)
   → Returns: {"success": true, "message": "..."}

9. complete_appointment(appointment_id, notes)
   → Returns: {"success": true, "message": "..."}
```

#### Prompts (2 total, discovered via prompts/list, fetched via prompts/get)
```python
# mcp_server/server.py — all registered via @mcp.prompt()

@mcp.prompt()
def patient_appointment() -> str:
    """System prompt for patient appointment booking"""
    return f"""You are MediConnect AI Assistant...
Available doctors:
  • Dr. Ahuja      — General Physician
  • Dr. Pyari      — Cardiologist
  ...
"""

@mcp.prompt()
def doctor_summary() -> str:
    """System prompt for doctor reporting"""
    return f"""You are MediConnect AI Assistant, helping doctors...
Your capabilities:
  1. Query appointment statistics
  2. Filter appointments by symptoms
  3. Generate and format summary reports
  ...
"""

# Retrieved at runtime in orchestrator.py:
system_prompt = await _get_prompt(mcp, prompt_name)  ← MCP RPC: prompts/get
```

#### Resources (3 total, discovered via resources/list, read via resources/read)
```python
# mcp_server/server.py — all registered via @mcp.resource("uri")

@mcp.resource("mediconnect://doctors")
def resource_doctors() -> str:
    """Live list of all doctors with their specialties and contact details."""
    # Queries database, returns JSON
    return json.dumps({
        "doctors": [
            {"id": 1, "name": "Dr. Ahuja", "specialty": "General Physician", ...},
            ...
        ],
        "count": 4,
    })

@mcp.resource("mediconnect://appointments/upcoming")
def resource_upcoming_appointments() -> str:
    """All upcoming (scheduled) appointments across the system."""
    # Live DB snapshot
    return json.dumps({"upcoming_appointments": [...], "count": N})

@mcp.resource("mediconnect://stats/today")
def resource_today_stats() -> str:
    """Today's appointment summary statistics."""
    return json.dumps({"date": "...", "total": N, "scheduled": M, ...})

# Accessible via HTTP:
GET /api/mcp/resource?uri=mediconnect://doctors
GET /api/mcp/resource?uri=mediconnect://appointments/upcoming
GET /api/mcp/resource?uri=mediconnect://stats/today
```

---

### ✅ Protocol-Based Communication Between MCP Client and Server

**Transport Layer: stdio**
```
mcp_client.py (FastAPI process)
    ↓ (subprocess.Popen)
    └─ mcp_server/server.py (child process)
       stdin  ← receives JSON-RPC messages
       stdout → sends JSON-RPC responses
```

**Implementation: agent/mcp_client.py**
```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

def _server_params() -> StdioServerParameters:
    """Build stdio launch parameters"""
    return StdioServerParameters(
        command=sys.executable,
        args=[_SERVER_SCRIPT],  # mcp_server/server.py
        env=None,  # inherit environment
    )

@asynccontextmanager
async def mcp_session() -> AsyncIterator[ClientSession]:
    """
    Open ONE MCP session (spawns subprocess if needed).
    Stays open for the entire agent turn.
    """
    async with stdio_client(_server_params()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()  ← JSON-RPC handshake
            yield session
            # Subprocess automatically cleaned up on exit
```

**Server-Side: mcp_server/server.py**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mediconnect-mcp-server", instructions="...")

# FastMCP handles the protocol automatically:
# - Listens on stdin for JSON-RPC messages
# - Routes to @mcp.tool(), @mcp.prompt(), @mcp.resource() handlers
# - Writes JSON-RPC responses to stdout

if __name__ == "__main__":
    mcp.run()  # Starts the MCP server over stdio
```

**Protocol Messages Exchanged**
```
1. Initialize handshake:
   Client → {"jsonrpc":"2.0","id":1,"method":"initialize",...}
   Server ← {"jsonrpc":"2.0","id":1,"result":{...}}

2. Tool discovery:
   Client → {"jsonrpc":"2.0","id":2,"method":"tools/list"}
   Server ← {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}

3. Prompt retrieval:
   Client → {"jsonrpc":"2.0","id":3,"method":"prompts/get","params":{"name":"patient_appointment",...}}
   Server ← {"jsonrpc":"2.0","id":3,"result":{"messages":[...]}}

4. Tool invocation:
   Client → {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"book_appointment","arguments":{...}}}
   Server ← {"jsonrpc":"2.0","id":4,"result":{"success":true,...}}

5. Resource read:
   Client → {"jsonrpc":"2.0","id":5,"method":"resources/read","params":{"uri":"mediconnect://doctors"}}
   Server ← {"jsonrpc":"2.0","id":5,"result":{"contents":[{"text":"..."}]}}
```

---

### ✅ Multi-Turn LLM Workflow Orchestration

**Session Management: agent/session.py**
```python
class SessionManager:
    """Manages conversation sessions for multi-turn AI interactions."""
    
    def __init__(self, max_session_age_hours: int = 24):
        self._sessions: dict = {}  # session_id → session_data
        self._max_age = timedelta(hours=max_session_age_hours)
    
    def get_session(self, session_id: str) -> dict:
        """Get or create a session with full message history."""
        session = self._sessions[session_id]
        session["messages"] = [
            {
                "role": "user",
                "parts": [{"text": "I want to book Dr. Ahuja tomorrow"}],
            },
            {
                "role": "model",
                "parts": [
                    {"text": "Let me check availability..."},
                    {"functionCall": {"name": "check_doctor_availability", ...}},
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "check_doctor_availability",
                            "response": {"available_slots": ["10:00", "11:00", "14:00"], ...},
                        }
                    }
                ],
            },
            {
                "role": "model",
                "parts": [{"text": "Dr. Ahuja is available at 10:00, 11:00, or 14:00. Which works for you?"}],
            },
            # ... next user turn ...
        ]
        return session
```

**Orchestrator Loop: agent/orchestrator.py**
```python
async def process_message(self, user_message: str, session_id: str, user_context: dict, db: Session) -> dict:
    """Process one user message through multi-turn agent loop."""
    
    # Step 1: Get session with full conversation history
    session = self.session_manager.get_session(session_id)
    
    # Step 2: Open ONE MCP session for entire agent turn
    async with mcp_session() as mcp:
        
        # Step 3: Discover tools (tools/list via MCP)
        tools = await _list_tools(mcp)
        
        # Step 4: Fetch system prompt (prompts/get via MCP)
        system_prompt = await _get_prompt(mcp, prompt_name)
        
        # Step 5: Add new user turn to history
        session["messages"].append({
            "role": "user",
            "parts": [{"text": user_message}],
        })
        
        # Step 6: Agent loop — keep calling Gemini until text response
        for iteration in range(self.max_tool_calls):
            
            # Call Gemini with full history + discovered tools
            response = await self._call_gemini(
                system_prompt=system_prompt,
                messages=session["messages"],  # Full history!
                tools=tools,
            )
            
            # Check if Gemini wants to call tools
            if function_calls := extract_function_calls(response):
                
                # Append Gemini's "thinking" (with function calls) to history
                session["messages"].append({"role": "model", "parts": parts})
                
                # Execute each tool call
                function_responses = []
                for fc in function_calls:
                    tool_name = fc["name"]
                    tool_args = fc["args"]
                    
                    # Inject user context
                    if "patient_id" not in tool_args:
                        tool_args["patient_id"] = user_context["patient_id"]
                    
                    # Invoke tool via MCP (tools/call)
                    result = await _call_tool(mcp, tool_name, tool_args)
                    
                    function_responses.append({
                        "functionResponse": {
                            "name": tool_name,
                            "response": result,
                        }
                    })
                
                # Append tool results to history
                session["messages"].append({
                    "role": "user",
                    "parts": function_responses,
                })
                
                # Continue loop — Gemini needs to process tool results
                continue
            
            else:
                # Plain text response — we're done!
                final_response = extract_text(response)
                
                # Append to history
                session["messages"].append({
                    "role": "model",
                    "parts": [{"text": final_response}],
                })
                
                return {
                    "response": final_response,
                    "tool_calls": tool_calls_made,
                }
```

**Multi-Turn Example: Patient Booking**

*Turn 1: User asks about availability*
```
Input:  "I want to book an appointment with Dr. Ahuja tomorrow"
Session history: []

Process:
  1. Add user message to history
  2. Call Gemini (no prior context)
  3. Gemini: "Let me check availability..." + functionCall(check_doctor_availability, ...)
  4. Execute tool via MCP → get available slots
  5. Append results to history
  6. Call Gemini again (with tool results in history)
  7. Gemini: "Dr. Ahuja is available at 10:00, 11:00, 14:00. Which works for you?"

Session history now:
  [user: "I want to book...", model: "...", functionCall, user: functionResponse, model: "Which time..."]
```

*Turn 2: User picks a time*
```
Input:  "3 PM please"
Session history: [entire turn 1 conversation]

Process:
  1. Add user message to history
  2. Call Gemini WITH FULL HISTORY → Gemini remembers Dr. Ahuja and understands "3 PM"
  3. Gemini: "Booking now..." + functionCall(book_appointment, doctor_name="Dr. Ahuja", time_slot="15:00", ...)
  4. Execute tool via MCP → appointment created (ID: 42)
  5. Append results to history
  6. Call Gemini again
  7. Gemini: "functionCall(send_email_confirmation, appointment_id=42)"
  8. Execute tool via MCP → email queued
  9. Append results to history
  10. Call Gemini again
  11. Gemini: "Booked! You'll receive an email confirmation to your registered email."

Session history now:
  [full turn 1 + user: "3 PM please", model: "Booking now...", functionCall(book_appointment),
   user: functionResponse, model: "functionCall(send_email_confirmation)", 
   user: functionResponse, model: "Booked!..."]
```

*Turn 3: User asks about the booking*
```
Input:  "What time is my appointment?"
Session history: [full turns 1 & 2]

Process:
  1. Gemini reads FULL HISTORY → knows appointment was just booked at 15:00 with Dr. Ahuja
  2. Responds directly: "Your appointment with Dr. Ahuja is tomorrow at 3:00 PM"
  3. No tool calls needed — Gemini used context from history

Session history now: [full turns 1, 2, & 3]
```

---

### Testing & Verification

**Test File: backend/test_mcp.py**
```
Runs:
  1. ✅ MCP handshake (initialize)
  2. ✅ tools/list       — discovers 9 tools
  3. ✅ prompts/list     — discovers 2 prompts
  4. ✅ prompts/get      — fetches system prompt text
  5. ✅ resources/list   — discovers 3 resources
  6. ✅ resources/read   — reads resource contents
  7. ✅ tools/call       — invokes get_doctors_list
  8. ✅ tools/call       — invokes check_doctor_availability

Run with: python test_mcp.py
```

**Live HTTP Endpoints**
```
GET /api/mcp/tools        → tools/list
GET /api/mcp/resources    → resources/list
GET /api/mcp/prompts      → prompts/list
GET /api/mcp/resource?uri=mediconnect://doctors  → resources/read
POST /api/chat            → full agent orchestration with MCP
```

---

### Summary: All Requirements Met ✅

| Requirement | Implementation | Evidence |
|---|---|---|
| **MCP client–server architecture** | subprocess with stdio transport | `agent/mcp_client.py` lines 31–37, `mcp_server/server.py` line 650 |
| **Tool discovery (tools/list)** | @mcp.tool() decorators + FastMCP | `mcp_server/server.py` lines 72–370, `agent/mcp_client.py` lines 98–108 |
| **Tool invocation (tools/call)** | async _call_tool() via session | `agent/mcp_client.py` lines 131–141, `agent/orchestrator.py` lines 88–100 |
| **Prompts (prompts/get)** | @mcp.prompt() decorators | `mcp_server/server.py` lines 535–582, `agent/mcp_client.py` lines 155–160 |
| **Resources (resources/read)** | @mcp.resource() decorators | `mcp_server/server.py` lines 414–478, `agent/mcp_client.py` lines 148–153 |
| **Protocol-based communication** | JSON-RPC over stdio | `agent/mcp_client.py` lines 31–37, `mcp_server/server.py` line 650 |
| **Multi-turn orchestration** | SessionManager + agent loop | `agent/session.py`, `agent/orchestrator.py` lines 49–137 |
| **Context continuity** | Full message history in session | `agent/session.py` lines 21–36, `agent/orchestrator.py` line 66 |
| **Live HTTP endpoints** | /api/mcp/* routes | `main.py` lines 102–131 |
| **Standalone test** | test_mcp.py exercises all protocols | `test_mcp.py` |
