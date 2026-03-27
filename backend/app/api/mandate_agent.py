"""
Mandate Agent API routes.

POST /mandate-agent/sessions                  — start a new mandate session
GET  /mandate-agent/sessions/{id}             — get session history
POST /mandate-agent/sessions/{id}/messages    — send a message
GET  /mandate-agent/sessions/{id}/mandate     — get current mandate state
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.mandate_agent.gap_analyzer import derive_mandate_state
from app.agents.mandate_agent.runtime import MandateAgentRuntime
from app.core.auth import get_current_user
from app.db.models import Conversation, Mandate, Message, User
from app.db.session import get_db
from pydantic import BaseModel, Field

router = APIRouter()


class MandateAgentSendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _serialize_message(message: Message) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "mandate_delta": message.mandate_delta,
        "completeness_after": float(message.completeness_after or 0.0),
        "gaps_remaining": message.gaps_remaining or [],
        "created_at": message.created_at,
    }


def _serialize_conversation(conv: Conversation) -> dict:
    return {
        "id": str(conv.id),
        "status": conv.status,
        "mandate_id": str(conv.mandate_id) if conv.mandate_id else None,
        "created_at": conv.created_at,
        "last_message_at": conv.last_message_at,
    }


def _serialize_mandate(mandate: Mandate) -> dict:
    return {
        "id": str(mandate.id),
        "owner_id": str(mandate.owner_id),
        "intent_type": mandate.intent_type,
        "vertical": mandate.vertical,
        "category": mandate.category,
        "hard_constraints": mandate.hard_constraints or [],
        "negotiation_range": mandate.negotiation_range or [],
        "soft_preferences": mandate.soft_preferences or [],
        "dealbreakers": mandate.dealbreakers or [],
        "autonomy_level": mandate.autonomy_level,
        "completeness_score": float(mandate.completeness_score or 0.0),
        "is_active": bool(mandate.is_active),
        "mandate_state": derive_mandate_state(mandate),
        "created_at": mandate.created_at,
        "updated_at": mandate.updated_at,
    }


@router.post("/sessions")
def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = MandateAgentRuntime(db)
    conversation, mandate, opening_msg = runtime.create_session(owner_id=current_user.id)
    return {
        "conversation": _serialize_conversation(conversation),
        "mandate": _serialize_mandate(mandate),
        "agent_message": _serialize_message(opening_msg),
    }


@router.get("/sessions/{conversation_id}")
def get_session(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = MandateAgentRuntime(db)
    conversation = runtime.get_owned_session(current_user.id, conversation_id)
    mandate = runtime.get_mandate_for_session(conversation)
    messages = runtime.get_messages(conversation.id)
    return {
        "conversation": _serialize_conversation(conversation),
        "mandate": _serialize_mandate(mandate),
        "messages": [_serialize_message(m) for m in messages],
        "total": len(messages),
    }


@router.post("/sessions/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    payload: MandateAgentSendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = MandateAgentRuntime(db)
    conversation = runtime.get_owned_session(current_user.id, conversation_id)
    mandate = runtime.get_mandate_for_session(conversation)

    (
        user_msg,
        agent_msg,
        mandate_state,
        mandate_delta,
        completeness_score,
        gaps_remaining,
        next_gap,
        is_complete,
    ) = runtime.run_turn(
        conversation=conversation,
        mandate=mandate,
        owner_id=current_user.id,
        content=payload.content,
    )

    return {
        "conversation": _serialize_conversation(conversation),
        "user_message": _serialize_message(user_msg),
        "agent_message": _serialize_message(agent_msg),
        "mandate_delta": mandate_delta,
        "mandate_state": mandate_state,
        "completeness_score": completeness_score,
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "mandate_complete": is_complete,
    }


@router.get("/sessions/{conversation_id}/mandate")
def get_mandate(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runtime = MandateAgentRuntime(db)
    conversation = runtime.get_owned_session(current_user.id, conversation_id)
    mandate = runtime.get_mandate_for_session(conversation)
    return _serialize_mandate(mandate)
