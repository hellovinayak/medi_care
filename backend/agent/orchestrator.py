"""
LLM Agent Orchestrator — Agentic AI loop using real MCP client-server communication.

Flow per user message
─────────────────────
 1. Open a SINGLE MCP client session (one subprocess for the whole turn).
 2. tools/list  → discover available tools from the MCP server.
 3. prompts/get → fetch the role-appropriate system prompt from the MCP server.
 4. Send user message + history to Gemini with the discovered tool declarations.
 5. Gemini may respond with functionCall blocks:
      a. Inject user context (patient_id, user_id) into arguments.
      b. tools/call → invoke each tool via MCP.
      c. Append tool results and loop back to Gemini.
 6. When Gemini returns a plain text response, return it to the caller.
"""

import httpx
from typing import Optional
from sqlalchemy.orm import Session

from agent.session import SessionManager
from agent.mcp_client import mcp_session, _list_tools, _call_tool, _get_prompt
from config import get_settings

settings = get_settings()

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash:generateContent"
)


class AgentOrchestrator:
    """
    Orchestrates the multi-turn agentic AI loop.

    Key design points
    -----------------
    * ONE MCP session is opened per process_message call so all tool
      invocations within a single agent turn share the same subprocess
      connection — efficient and correct.
    * Tool definitions are discovered at runtime via MCP (tools/list),
      not hard-coded, so new tools added to the MCP server are
      automatically reflected in the LLM's function-calling schema.
    * System prompts are fetched from the MCP server (prompts/get) so
      prompt logic lives in one place and can evolve independently.
    """

    def __init__(self):
        self.session_manager = SessionManager()
        self.max_tool_calls = 5  # safety guard against infinite loops

    async def process_message(
        self,
        user_message: str,
        session_id: str,
        user_context: dict,
        db: Session,          # kept for interface compatibility
    ) -> dict:
        session = self.session_manager.get_session(session_id)
        role = user_context.get("role", "patient")
        prompt_name = "doctor_summary" if role == "doctor" else "patient_appointment"

        # ── Open ONE MCP session for the entire agent turn ──────────────
        async with mcp_session() as mcp:

            # Step 1 — Discover tools (tools/list via MCP protocol)
            tools = await _list_tools(mcp)

            # Step 2 — Fetch system prompt (prompts/get via MCP protocol)
            system_prompt = await _get_prompt(mcp, prompt_name)

            session["messages"].append({
                "role": "user",
                "parts": [{"text": user_message}],
            })

            tool_calls_made = []

            # ── Agent loop ─────────────────────────────────────────────
            for _ in range(self.max_tool_calls):

                # Step 3 — Call Gemini with MCP-discovered tool schemas
                response = await self._call_gemini(system_prompt, session["messages"], tools)

                if not response:
                    msg = "I'm sorry, I couldn't process your request. Please try again."
                    session["messages"].append({"role": "model", "parts": [{"text": msg}]})
                    return {"response": msg, "tool_calls": tool_calls_made}

                candidates = response.get("candidates", [])
                if not candidates:
                    msg = "No response generated. Please try again."
                    session["messages"].append({"role": "model", "parts": [{"text": msg}]})
                    return {"response": msg, "tool_calls": tool_calls_made}

                parts = candidates[0].get("content", {}).get("parts", [])
                function_calls = [p for p in parts if "functionCall" in p]

                if function_calls:
                    session["messages"].append({"role": "model", "parts": parts})

                    function_responses = []
                    for fc_part in function_calls:
                        fc = fc_part["functionCall"]
                        tool_name = fc["name"]
                        tool_args = dict(fc.get("args", {}))

                        # Inject caller context so MCP server knows who's asking
                        if "patient_id" not in tool_args and "patient_id" in user_context:
                            tool_args["patient_id"] = user_context["patient_id"]
                        if "user_id" not in tool_args and "user_id" in user_context:
                            tool_args["user_id"] = user_context["user_id"]

                        # Step 4 — Invoke tool via MCP (tools/call)
                        result = await _call_tool(mcp, tool_name, tool_args)

                        tool_calls_made.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": result,
                        })
                        function_responses.append({
                            "functionResponse": {"name": tool_name, "response": result}
                        })

                    session["messages"].append({"role": "user", "parts": function_responses})
                    continue

                else:
                    # Plain text — agent turn complete
                    text_parts = [p.get("text", "") for p in parts if "text" in p]
                    final_response = " ".join(text_parts).strip()
                    if not final_response:
                        final_response = "Done! Is there anything else I can help with?"

                    session["messages"].append({
                        "role": "model",
                        "parts": [{"text": final_response}],
                    })
                    return {"response": final_response, "tool_calls": tool_calls_made}

        fallback = "I've completed your request. Is there anything else you need?"
        session["messages"].append({"role": "model", "parts": [{"text": fallback}]})
        return {"response": fallback, "tool_calls": tool_calls_made}

    async def _call_gemini(self, system_prompt, messages, tools) -> Optional[dict]:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return None
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": messages,
            "tools": [{"function_declarations": tools}],
            "tool_config": {"function_calling_config": {"mode": "AUTO"}},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{GEMINI_URL}?key={api_key}",
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 429:
                    return {"candidates": [{"content": {"parts": [{"text": "⚠️ Rate limit reached. Please wait 60 seconds and try again."}]}}]}
                if resp.status_code != 200:
                    print(f"Gemini error {resp.status_code}: {resp.text}")
                    return None
                return resp.json()
        except Exception as exc:
            print(f"Error calling Gemini: {exc}")
            return None


# Singleton used by the chat router
agent = AgentOrchestrator()
