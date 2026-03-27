from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.personal_agent.memory.service import PersonalMemoryService
from app.agents.personal_agent.runtime import PersonalAgentRuntime
from app.agents.personal_agent.schemas import (
    PersonalMemoryCreateRequest,
    PersonalMemoryUpdateRequest,
    PersonalAgentCreateSessionRequest,
    PersonalAgentSendMessageRequest,
)
from app.core.auth import get_current_user, get_current_user_id
from app.db.models import OnboardingMessage, PersonalMemory, User
from app.db.session import get_db
from app.security.agent_admin_acl import require_agent_admin

router = APIRouter()


def _serialize_message(message: OnboardingMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "persona_delta": message.persona_delta,
        "completeness_after": float(message.completeness_after or 0.0),
        "created_at": message.created_at,
    }


def _serialize_memory(memory: PersonalMemory) -> dict:
    return {
        "id": str(memory.id),
        "owner_id": str(memory.owner_id),
        "content": memory.content,
        "tags": memory.tags or [],
        "source": memory.source,
        "confidence": float(memory.confidence or 0.0),
        "is_active": bool(memory.is_active),
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


@router.post("/sessions")
def create_session(
    payload: PersonalAgentCreateSessionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = PersonalAgentRuntime(db)
    session, agent_message = runtime.create_session(
        owner=current_user,
        opening_message=payload.opening_message if payload else None,
    )
    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "agent_message": _serialize_message(agent_message),
        "persona": current_user.persona or {},
    }


@router.get("/sessions/{conversation_id}")
def get_session(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = PersonalAgentRuntime(db)
    session = runtime.get_owned_session(current_user.id, conversation_id)
    messages = runtime.get_messages(session.id)

    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "messages": [_serialize_message(m) for m in messages],
        "total": len(messages),
        "persona": current_user.persona or {},
    }


@router.post("/sessions/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    payload: PersonalAgentSendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = PersonalAgentRuntime(db)
    session = runtime.get_owned_session(current_user.id, conversation_id)

    (
        user_msg,
        agent_msg,
        persona,
        persona_delta,
        completeness_score,
        gaps_remaining,
        next_gap,
        is_complete,
    ) = runtime.run_turn(session=session, owner=current_user, content=payload.content)

    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "user_message": _serialize_message(user_msg),
        "agent_message": _serialize_message(agent_msg),
        "persona_delta": persona_delta,
        "persona": persona,
        "completeness_score": completeness_score,
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "elicitation_complete": is_complete,
    }


@router.post("/memories")
def add_memory(
    payload: PersonalMemoryCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    service = PersonalMemoryService(db)
    memory = service.add_memory(
        owner_id=UUID(current_user_id),
        content=payload.content,
        tags=payload.tags,
        source=payload.source,
        confidence=payload.confidence,
    )
    return _serialize_memory(memory)


@router.get("/memories/search")
def search_memories(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    service = PersonalMemoryService(db)
    results = service.search_memories(owner_id=UUID(current_user_id), query=q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "memories": [_serialize_memory(item) for item in results],
    }


@router.get("/memories")
def list_memories(
    include_inactive: bool = Query(default=False),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    service = PersonalMemoryService(db)
    results = service.list_memories(owner_id=UUID(current_user_id), include_inactive=include_inactive)
    return {
        "count": len(results),
        "memories": [_serialize_memory(item) for item in results],
    }


@router.patch("/memories/{memory_id}")
def update_memory(
    memory_id: UUID,
    payload: PersonalMemoryUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    service = PersonalMemoryService(db)
    updated = service.update_memory(
        owner_id=UUID(current_user_id),
        memory_id=memory_id,
        content=payload.content,
        tags=payload.tags,
        is_active=payload.is_active,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Memory not found"})
    return _serialize_memory(updated)


@router.get("/tools")
def list_tools(db: Session = Depends(get_db)):
    runtime = PersonalAgentRuntime(db)
    return {"tools": runtime.list_tools(), "count": len(runtime.list_tools())}


@router.post("/admin/tools/reload")
def reload_tools(
    _admin: dict = Depends(require_agent_admin),
    db: Session = Depends(get_db),
):
    runtime = PersonalAgentRuntime(db)
    return {
        "reloaded": True,
        "count": len(runtime.list_tools()),
        "tools": runtime.list_tools(),
    }
