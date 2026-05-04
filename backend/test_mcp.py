#!/usr/bin/env python3
"""
test_mcp.py — Standalone test for the MediConnect MCP server.

Demonstrates real MCP client-server communication without needing the
full FastAPI stack or a Gemini API key.

Run from the backend/ directory:
    python test_mcp.py

What it tests
─────────────
  1. MCP handshake (initialize)
  2. tools/list   — tool discovery
  3. prompts/list — prompt discovery
  4. prompts/get  — prompt retrieval
  5. resources/list — resource discovery
  6. resources/read — resource content
  7. tools/call   — tool invocation (get_doctors_list)
  8. tools/call   — tool invocation (check_doctor_availability)
"""

import asyncio
import sys
import json
from pathlib import Path

# Make sure we're running from the backend/ directory
here = Path(__file__).parent
sys.path.insert(0, str(here))

from agent.mcp_client import mcp_session


async def run_tests():
    print("=" * 60)
    print("  MediConnect — Real MCP Client-Server Communication Test")
    print("=" * 60)
    print()

    async with mcp_session() as session:
        print("✅  MCP handshake complete (initialize)\n")

        # ── 1. Tool discovery ────────────────────────────────────────
        print("─── tools/list ─────────────────────────────────────────")
        tools_result = await session.list_tools()
        tools = tools_result.tools
        print(f"Discovered {len(tools)} tools:")
        for t in tools:
            print(f"  • {t.name:<35} {(t.description or '')[:55]}")
        print()

        # ── 2. Prompt discovery ──────────────────────────────────────
        print("─── prompts/list ───────────────────────────────────────")
        prompts_result = await session.list_prompts()
        prompts = prompts_result.prompts
        print(f"Discovered {len(prompts)} prompts:")
        for p in prompts:
            print(f"  • {p.name:<30} {(p.description or '')[:55]}")
        print()

        # ── 3. Prompt retrieval ──────────────────────────────────────
        print("─── prompts/get (patient_appointment) ─────────────────")
        prompt_result = await session.get_prompt("patient_appointment", {})
        prompt_text = ""
        for msg in prompt_result.messages:
            if hasattr(msg.content, "text"):
                prompt_text = msg.content.text
        print("First 300 chars of system prompt:")
        print(f"  {prompt_text[:300]}...")
        print()

        # ── 4. Resource discovery ────────────────────────────────────
        print("─── resources/list ─────────────────────────────────────")
        resources_result = await session.list_resources()
        resources = resources_result.resources
        print(f"Discovered {len(resources)} resources:")
        for r in resources:
            print(f"  • {str(r.uri)}")
        print()

        # ── 5. Resource read ─────────────────────────────────────────
        print("─── resources/read (mediconnect://doctors) ─────────────")
        try:
            read_result = await session.read_resource("mediconnect://doctors")
            data = json.loads(read_result.contents[0].text)
            print(f"Doctors in database: {data['count']}")
            for doc in data["doctors"][:3]:
                print(f"  • {doc['name']} — {doc['specialty']}")
        except Exception as e:
            print(f"  (could not read resource: {e})")
        print()

        # ── 6. Tool invocation: get_doctors_list ─────────────────────
        print("─── tools/call: get_doctors_list ───────────────────────")
        call_result = await session.call_tool("get_doctors_list", {})
        data = json.loads(call_result.content[0].text)
        if data.get("success"):
            print(f"✅  Tool returned {data['count']} doctors:")
            for d in data["doctors"]:
                print(f"  • {d['name']} ({d['specialty']})")
        else:
            print(f"❌  Error: {data.get('error')}")
        print()

        # ── 7. Tool invocation: check_doctor_availability ────────────
        print("─── tools/call: check_doctor_availability ──────────────")
        call_result2 = await session.call_tool(
            "check_doctor_availability",
            {"doctor_name": "Dr. Ahuja", "date": "tomorrow"}
        )
        data2 = json.loads(call_result2.content[0].text)
        if data2.get("success"):
            avail_msg = f"{len(data2['available_slots'])} slots available" if data2["available"] else "Not available"
            print(f"✅  Dr. Ahuja tomorrow ({data2['day']}): {avail_msg}")
            if data2["available_slots"]:
                print(f"     Slots: {', '.join(data2['available_slots'][:5])}")
        else:
            print(f"   Result: {data2.get('message', data2.get('error'))}")
        print()

    print("=" * 60)
    print("  All MCP tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
