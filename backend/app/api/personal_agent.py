from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.personal_agent.runtime import PersonalAgentRuntime
from app.agents.personal_agent.schemas import (
    PersonalAgentCreateSessionRequest,
    PersonalAgentSendMessageRequest,
)
from app.core.auth import get_current_user
from app.db.models import OnboardingMessage, User
from app.db.session import get_db

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
        mandate_delta,
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
        "mandate_delta": mandate_delta,
        "persona": persona,
        "completeness_score": completeness_score,
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "elicitation_complete": is_complete,
    }
