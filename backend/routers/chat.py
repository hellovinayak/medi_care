"""Chat routes - AI agent interaction endpoint with multi-turn support."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database.connection import get_db
from database.models import Patient
from routers.auth import get_current_user
from agent.orchestrator import agent
import uuid

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list = []


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Patient = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to the AI agent.

    The agent will:
    1. Parse the natural language message
    2. Decide which MCP tools to call
    3. Execute tools (check availability, book appointments, etc.)
    4. Return a natural language response

    Supports multi-turn conversations via session_id.
    """
    # Create or reuse session
    session_id = request.session_id or str(uuid.uuid4())

    # Build user context
    user_context = {
        "user_id": current_user.id,
        "patient_id": current_user.id,
        "user_name": current_user.name,
        "user_email": current_user.email,
        "role": current_user.role
    }

    # Process through agent
    result = await agent.process_message(
        user_message=request.message,
        session_id=session_id,
        user_context=user_context,
        db=db
    )

    return ChatResponse(
        response=result["response"],
        session_id=session_id,
        tool_calls=result.get("tool_calls", [])
    )


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: Patient = Depends(get_current_user)
):
    """Get conversation history for a session."""
    history = agent.session_manager.get_session_history(session_id)
    return {"session_id": session_id, "messages": history}


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    current_user: Patient = Depends(get_current_user)
):
    """Clear conversation history for a session."""
    agent.session_manager.clear_session(session_id)
    return {"message": "Session cleared"}
